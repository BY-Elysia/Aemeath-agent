from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .cli_runner import CliRunner
from .config import AppConfig
from .harness import AgentHarness, build_harness
from .store import SessionStore


CONFIRM_WORDS = {"确认", "/confirm", "确认执行", "执行"}
CANCEL_WORDS = {"取消", "/cancel", "取消执行"}
AT_TAG_RE = re.compile(r"<at\b[^>]*>.*?</at>", re.IGNORECASE)


class ReplyClient:
    def __init__(self, runner: CliRunner) -> None:
        self._runner = runner

    def reply_text(self, message_id: str, text: str) -> None:
        result = self._runner.run(
            [
                "im",
                "+messages-reply",
                "--message-id",
                message_id,
                "--text",
                text,
                "--as",
                "bot",
            ]
        )
        if result.returncode != 0:
            detail = result.stderr or result.stdout or "unknown error"
            raise RuntimeError(f"failed to reply message {message_id}: {detail}")


class AutoReplyWorker:
    def __init__(
        self,
        *,
        store: SessionStore,
        harness: AgentHarness,
        reply_client: ReplyClient,
        group_reply_mode: str = "off",
        app_id: str | None = None,
        bot_mention_ids: tuple[str, ...] = (),
        bot_mention_names: tuple[str, ...] = (),
    ) -> None:
        self._store = store
        self._harness = harness
        self._reply_client = reply_client
        self._group_reply_mode = group_reply_mode
        self._app_id = app_id
        self._bot_mention_ids = {item.strip() for item in bot_mention_ids if item.strip()}
        self._bot_mention_names = {item.strip() for item in bot_mention_names if item.strip()}

    def handle_event(self, event: dict[str, Any]) -> None:
        normalized = self._normalize_event(event)
        if normalized is None:
            return

        session_id = f"im-chat:{normalized['chat_id']}"
        content = normalized["content"]
        if content in CONFIRM_WORDS:
            self._handle_confirmation(normalized["message_id"], session_id, True)
            return
        if content in CANCEL_WORDS:
            self._handle_confirmation(normalized["message_id"], session_id, False)
            return

        payload = self._harness.handle_message(session_id, content, source="feishu_event").model_dump()
        self._reply_to_chat_response(normalized["message_id"], payload)

    def _handle_confirmation(self, message_id: str, session_id: str, confirm: bool) -> None:
        pending = self._store.get_latest_pending_action_for_session(session_id)
        if pending is None:
            self._reply_client.reply_text(message_id, "当前没有待确认动作。")
            return
        payload = self._harness.confirm_action(pending["action_id"], confirm).model_dump()
        text = str(payload.get("message") or ("已执行。" if confirm else "已取消。")).strip()
        self._reply_client.reply_text(message_id, text)

    def _reply_to_chat_response(self, message_id: str, payload: dict[str, Any]) -> None:
        status = str(payload.get("status") or "message")
        text = str(payload.get("message") or "").strip()
        if status == "pending_action":
            if not text:
                text = "检测到待确认动作。"
            text = f"{text}\n回复“确认”执行，回复“取消”放弃。"
        elif not text:
            text = "未获得可回复内容。"
        self._reply_client.reply_text(message_id, text)

    def _normalize_event(self, event: dict[str, Any]) -> dict[str, str] | None:
        if isinstance(event.get("event"), dict):
            return self._normalize_raw_event(event)
        return self._normalize_compact_event(event)

    def _normalize_compact_event(self, event: dict[str, Any]) -> dict[str, str] | None:
        sender_type = str(event.get("sender_type") or "").strip().lower()
        if sender_type == "app":
            return None

        chat_type = str(event.get("chat_type") or "").strip().lower()
        mentions = event.get("mentions") if isinstance(event.get("mentions"), list) else []
        if not self._should_process_group_message(chat_type, mentions, str(event.get("content") or "")):
            return None

        if str(event.get("message_type") or "").strip().lower() != "text":
            return None

        message_id = str(event.get("message_id") or "").strip()
        chat_id = str(event.get("chat_id") or "").strip()
        content = str(event.get("content") or "").strip()
        if not message_id or not chat_id or not content:
            return None

        return {
            "message_id": message_id,
            "chat_id": chat_id,
            "content": self._clean_text_content(content, mentions),
        }

    def _normalize_raw_event(self, envelope: dict[str, Any]) -> dict[str, str] | None:
        event = envelope.get("event") if isinstance(envelope.get("event"), dict) else {}
        message = event.get("message") if isinstance(event.get("message"), dict) else {}
        sender = event.get("sender") if isinstance(event.get("sender"), dict) else {}

        sender_type = str(sender.get("sender_type") or "").strip().lower()
        if sender_type == "app":
            return None

        chat_type = str(message.get("chat_type") or "").strip().lower()
        raw_content = message.get("content")
        mentions = message.get("mentions") if isinstance(message.get("mentions"), list) else []
        if not self._should_process_group_message(chat_type, mentions, str(raw_content or "")):
            return None

        message_type = str(message.get("message_type") or "").strip().lower()
        if message_type != "text":
            return None

        message_id = str(message.get("message_id") or "").strip()
        chat_id = str(message.get("chat_id") or "").strip()
        content = self._extract_text_content(raw_content, mentions)
        if not message_id or not chat_id or not content:
            return None

        return {
            "message_id": message_id,
            "chat_id": chat_id,
            "content": content,
        }

    def _should_process_group_message(
        self,
        chat_type: str,
        mentions: list[dict[str, Any]],
        raw_content: str,
    ) -> bool:
        if chat_type != "group":
            return True
        if self._group_reply_mode == "all":
            return True
        if self._group_reply_mode == "mention":
            return self._is_mentioning_me(mentions, raw_content)
        return False

    def _is_mentioning_me(self, mentions: list[dict[str, Any]], raw_content: str) -> bool:
        app_id = (self._app_id or "").strip()
        raw_content = str(raw_content or "")
        for mention in mentions:
            mention_id = str(mention.get("id") or mention.get("key") or "").strip()
            mention_name = str(mention.get("name") or "").strip()
            if app_id and mention_id == app_id:
                return True
            if mention_id and mention_id in self._bot_mention_ids:
                return True
            if mention_name and mention_name in self._bot_mention_names:
                return True
        if app_id and app_id in raw_content:
            return True
        return any(bot_id in raw_content for bot_id in self._bot_mention_ids)

    def _extract_text_content(self, raw_content: Any, mentions: list[dict[str, Any]] | None = None) -> str:
        if isinstance(raw_content, dict):
            text = raw_content.get("text")
            return self._clean_text_content(str(text or ""), mentions)
        if not isinstance(raw_content, str):
            return ""
        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError:
            return self._clean_text_content(raw_content, mentions)
        if isinstance(payload, dict):
            return self._clean_text_content(str(payload.get("text") or ""), mentions)
        return ""

    def _clean_text_content(self, text: str, mentions: list[dict[str, Any]] | None = None) -> str:
        cleaned = AT_TAG_RE.sub(" ", text)
        for mention in mentions or []:
            mention_name = str(mention.get("name") or "").strip()
            mention_key = str(mention.get("key") or "").strip()
            if mention_key:
                cleaned = re.sub(rf"^\s*{re.escape(mention_key)}\s*", " ", cleaned)
            if not mention_name:
                continue
            cleaned = re.sub(rf"^\s*@{re.escape(mention_name)}\s*", " ", cleaned)
        return " ".join(cleaned.split()).strip()


def load_lark_app_id(config_path: str | None = None) -> str | None:
    path = Path(config_path or "~/.lark-cli/config.json").expanduser()
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    apps = payload.get("apps")
    if not isinstance(apps, list) or not apps:
        return None
    app_id = apps[0].get("appId")
    return str(app_id).strip() if app_id else None


def run() -> None:
    config = AppConfig.from_env()
    runner = CliRunner(config.lark_cli_bin, config.command_timeout_seconds)
    store = SessionStore(config.app_db_path)
    harness = build_harness(config, store=store, runner=runner)
    worker = AutoReplyWorker(
        store=store,
        harness=harness,
        reply_client=ReplyClient(runner),
        group_reply_mode=config.group_reply_mode,
        app_id=load_lark_app_id(),
        bot_mention_ids=config.bot_mention_ids,
        bot_mention_names=config.bot_mention_names,
    )
    command = [
        config.lark_cli_bin,
        "event",
        "+subscribe",
        "--event-types",
        "im.message.receive_v1",
        "--quiet",
        "--as",
        "bot",
    ]
    print("Feishu Agent Auto Reply")
    print(f"服务地址: {config.feishu_agent_base_url}")
    print(f"监听命令: {' '.join(command)}")
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        bufsize=1,
    ) as process:
        if process.stdout is None:
            raise SystemExit("无法读取事件订阅输出。")
        try:
            for line in process.stdout:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    print(f"忽略无法解析的事件: {raw}")
                    continue
                try:
                    worker.handle_event(event)
                except Exception as exc:
                    print(f"处理事件失败: {exc}")
        except KeyboardInterrupt:
            process.terminate()
        raise SystemExit(process.wait())
