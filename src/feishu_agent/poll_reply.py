from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from .auto_reply import AutoReplyWorker, MessageResourceDownloader, ReplyClient, configure_utf8_stdio, load_lark_app_id
from .cli_runner import CliRunner
from .config import AppConfig
from .harness import build_harness
from .store import SessionStore


DEFAULT_POLL_INTERVAL_SECONDS = 5
STATE_LIMIT_PER_CHAT = 500


class PollingReplyWorker:
    def __init__(
        self,
        *,
        runner: CliRunner,
        auto_reply_worker: AutoReplyWorker,
        chat_ids: list[str],
        group_chat_ids: set[str],
        state_path: Path,
        interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
        replay_latest: bool = False,
    ) -> None:
        self._runner = runner
        self._auto_reply_worker = auto_reply_worker
        self._chat_ids = chat_ids
        self._group_chat_ids = group_chat_ids
        self._state_path = state_path
        self._interval_seconds = max(1, interval_seconds)
        self._replay_latest = replay_latest
        self._seen: dict[str, list[str]] = self._load_state()

    def run_forever(self) -> None:
        print(f"Polling reply worker started. chats={', '.join(self._chat_ids)}", flush=True)
        while True:
            for chat_id in self._chat_ids:
                try:
                    self._poll_chat(chat_id)
                except Exception as exc:
                    print(f"poll chat failed: chat_id={chat_id}, error={exc}", flush=True)
            time.sleep(self._interval_seconds)

    def _poll_chat(self, chat_id: str) -> None:
        messages = self._list_messages(chat_id)
        if not messages:
            return

        seen = set(self._seen.get(chat_id) or [])
        if not seen:
            initial_seen = [str(item.get("message_id") or "") for item in messages if item.get("message_id")]
            if self._replay_latest:
                latest_user_message = next((item for item in reversed(messages) if self._should_handle_message(item)), None)
                if latest_user_message is not None:
                    message_id = str(latest_user_message.get("message_id") or "")
                    if message_id:
                        seen.discard(message_id)
                    self._handle_message(chat_id, latest_user_message)
            self._seen[chat_id] = self._trim_seen(initial_seen)
            self._save_state()
            return

        changed = False
        for message in messages:
            message_id = str(message.get("message_id") or "").strip()
            if not message_id or message_id in seen:
                continue
            if self._should_handle_message(message):
                self._handle_message(chat_id, message)
            seen.add(message_id)
            changed = True

        if changed:
            self._seen[chat_id] = self._trim_seen(list(seen))
            self._save_state()

    def _list_messages(self, chat_id: str) -> list[dict[str, Any]]:
        result = self._runner.run(
            [
                "im",
                "+chat-messages-list",
                "--as",
                "bot",
                "--chat-id",
                chat_id,
                "--page-size",
                "20",
                "--sort",
                "asc",
                "--format",
                "json",
            ]
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or "failed to list chat messages")
        payload = result.parsed_json if isinstance(result.parsed_json, dict) else {}
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        messages = data.get("messages") if isinstance(data.get("messages"), list) else []
        return [item for item in messages if isinstance(item, dict)]

    def _should_handle_message(self, message: dict[str, Any]) -> bool:
        if bool(message.get("deleted")):
            return False
        msg_type = str(message.get("msg_type") or "").strip().lower()
        if msg_type not in {"text", "file"}:
            return False
        sender = message.get("sender") if isinstance(message.get("sender"), dict) else {}
        return str(sender.get("sender_type") or "").strip().lower() != "app"

    def _handle_message(self, chat_id: str, message: dict[str, Any]) -> None:
        message_id = str(message.get("message_id") or "").strip()
        if not message_id:
            return
        chat_type = "group" if chat_id in self._group_chat_ids else "p2p"
        msg_type = str(message.get("msg_type") or "text").strip().lower() or "text"
        event = {
            "message_id": message_id,
            "chat_id": chat_id,
            "chat_type": chat_type,
            "message_type": msg_type,
            "content": str(message.get("content") or "").strip(),
            "mentions": message.get("mentions") if isinstance(message.get("mentions"), list) else [],
            "sender_type": "user",
        }
        print(f"poll handling message: chat_id={chat_id}, message_id={message_id}", flush=True)
        self._auto_reply_worker.handle_event(event)

    def _load_state(self) -> dict[str, list[str]]:
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        state: dict[str, list[str]] = {}
        for chat_id, value in payload.items():
            if isinstance(value, list):
                state[str(chat_id)] = [str(item) for item in value if str(item)]
        return state

    def _save_state(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(self._seen, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _trim_seen(message_ids: list[str]) -> list[str]:
        deduped = list(dict.fromkeys(item for item in message_ids if item))
        return deduped[-STATE_LIMIT_PER_CHAT:]


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def run() -> None:
    configure_utf8_stdio()
    config = AppConfig.from_env()
    chat_ids = split_csv(os.getenv("AUTO_REPLY_POLL_CHAT_IDS", ""))
    if not chat_ids:
        raise SystemExit("AUTO_REPLY_POLL_CHAT_IDS is empty")

    group_chat_ids = set(split_csv(os.getenv("AUTO_REPLY_POLL_GROUP_CHAT_IDS", "")))
    interval_seconds = int(os.getenv("AUTO_REPLY_POLL_INTERVAL_SECONDS", str(DEFAULT_POLL_INTERVAL_SECONDS)))
    replay_latest = os.getenv("AUTO_REPLY_POLL_REPLAY_LATEST", "false").strip().lower() in {"1", "true", "yes", "on"}

    runner = CliRunner(config.lark_cli_bin, config.command_timeout_seconds)
    store = SessionStore(config.app_db_path)
    harness = build_harness(config, store=store, runner=runner)
    auto_reply_worker = AutoReplyWorker(
        store=store,
        harness=harness,
        reply_client=ReplyClient(runner),
        group_reply_mode=config.group_reply_mode,
        app_id=load_lark_app_id(),
        bot_mention_ids=config.bot_mention_ids,
        bot_mention_names=config.bot_mention_names,
        file_downloader=MessageResourceDownloader(runner),
    )
    state_path = Path(os.getenv("AUTO_REPLY_POLL_STATE_PATH", "./data/poll-state.json")).expanduser().resolve()
    PollingReplyWorker(
        runner=runner,
        auto_reply_worker=auto_reply_worker,
        chat_ids=chat_ids,
        group_chat_ids=group_chat_ids,
        state_path=state_path,
        interval_seconds=interval_seconds,
        replay_latest=replay_latest,
    ).run_forever()


if __name__ == "__main__":
    run()
