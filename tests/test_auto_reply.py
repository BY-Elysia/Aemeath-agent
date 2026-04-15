from __future__ import annotations

from pathlib import Path

from feishu_agent.auto_reply import AutoReplyWorker
from feishu_agent.schemas import ChatResponse, ConfirmActionResponse
from feishu_agent.store import SessionStore


class FakeHarness:
    def __init__(self, *, chat_responses: list[dict] | None = None, confirm_response: dict | None = None) -> None:
        self.chat_responses = chat_responses or []
        self.confirm_response = confirm_response or {"status": "executed", "message": "已执行。"}
        self.chat_calls: list[tuple[str, str]] = []
        self.confirm_calls: list[tuple[str, bool]] = []

    def handle_message(self, session_id: str, message: str, source: str) -> ChatResponse:
        self.chat_calls.append((session_id, message))
        if not self.chat_responses:
            raise AssertionError("No chat response configured")
        payload = self.chat_responses.pop(0)
        payload.setdefault("session_id", session_id)
        if payload.get("status") == "pending_action":
            pending = payload.setdefault("pending_action", {})
            pending.setdefault("summary", payload.get("message") or "待确认动作")
            pending.setdefault("args_preview", {})
        return ChatResponse(**payload)

    def confirm_action(self, action_id: str, confirm: bool) -> ConfirmActionResponse:
        self.confirm_calls.append((action_id, confirm))
        return ConfirmActionResponse(action_id=action_id, result=None, **self.confirm_response)


class FakeReplyClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def reply_text(self, message_id: str, text: str) -> None:
        self.calls.append((message_id, text))


def make_worker(
    tmp_path: Path,
    *,
    group_reply_mode: str = "off",
    app_id: str | None = "cli_a94083a8c1b99cbc",
    bot_mention_ids: tuple[str, ...] = (),
    bot_mention_names: tuple[str, ...] = (),
    harness: FakeHarness | None = None,
):
    store = SessionStore(tmp_path / "app.db")
    reply_client = FakeReplyClient()
    worker = AutoReplyWorker(
        store=store,
        harness=harness or FakeHarness(chat_responses=[{"status": "message", "message": "ok"}]),
        reply_client=reply_client,
        group_reply_mode=group_reply_mode,
        app_id=app_id,
        bot_mention_ids=bot_mention_ids,
        bot_mention_names=bot_mention_names,
    )
    return store, worker, reply_client


def test_auto_reply_handles_plain_text_message(tmp_path: Path) -> None:
    agent = FakeHarness(chat_responses=[{"status": "message", "message": "你好"}])
    _, worker, reply_client = make_worker(tmp_path, harness=agent)

    worker.handle_event(
        {
            "message_id": "om_1",
            "chat_id": "oc_1",
            "chat_type": "p2p",
            "message_type": "text",
            "content": "在吗",
            "sender_type": "user",
        }
    )

    assert agent.chat_calls == [("im-chat:oc_1", "在吗")]
    assert reply_client.calls == [("om_1", "你好")]


def test_auto_reply_returns_pending_action_hint(tmp_path: Path) -> None:
    agent = FakeHarness(
        chat_responses=[
            {
                "status": "pending_action",
                "message": "待确认：向指定飞书用户发送私聊消息。",
                "pending_action": {
                    "action_id": "a1",
                    "tool_name": "send_dm",
                },
            }
        ]
    )
    _, worker, reply_client = make_worker(tmp_path, harness=agent)

    worker.handle_event(
        {
            "message_id": "om_2",
            "chat_id": "oc_2",
            "chat_type": "p2p",
            "message_type": "text",
            "content": "给周灿宇发你好",
            "sender_type": "user",
        }
    )

    assert "回复“确认”执行" in reply_client.calls[0][1]


def test_auto_reply_can_confirm_latest_pending_action(tmp_path: Path) -> None:
    store, worker, reply_client = make_worker(
        tmp_path,
        harness=FakeHarness(confirm_response={"status": "executed", "message": "已发送消息。"}),
    )
    pending = store.create_pending_action(
        session_id="im-chat:oc_3",
        tool_name="send_dm",
        args={"user_open_id": "ou_xxx", "text": "你好", "send_as": "bot"},
        summary="待确认：向指定飞书用户发送私聊消息。",
        args_preview={"user_open_id": "ou_xxx", "text": "你好", "send_as": "bot"},
    )

    worker.handle_event(
        {
            "message_id": "om_3",
            "chat_id": "oc_3",
            "chat_type": "p2p",
            "message_type": "text",
            "content": "确认",
            "sender_type": "user",
        }
    )

    assert worker._harness.confirm_calls == [(pending["action_id"], True)]
    assert reply_client.calls == [("om_3", "已发送消息。")]


def test_auto_reply_ignores_group_message_when_group_reply_mode_off(tmp_path: Path) -> None:
    agent = FakeHarness(chat_responses=[{"status": "message", "message": "你好"}])
    _, worker, reply_client = make_worker(tmp_path, group_reply_mode="off", harness=agent)

    worker.handle_event(
        {
            "message_id": "om_4",
            "chat_id": "oc_4",
            "chat_type": "group",
            "message_type": "text",
            "content": "在吗",
            "sender_type": "user",
        }
    )

    assert agent.chat_calls == []
    assert reply_client.calls == []


def test_auto_reply_handles_group_message_when_group_reply_mode_all(tmp_path: Path) -> None:
    agent = FakeHarness(chat_responses=[{"status": "message", "message": "收到"}])
    _, worker, reply_client = make_worker(tmp_path, group_reply_mode="all", harness=agent)

    worker.handle_event(
        {
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "message": {
                    "message_id": "om_5",
                    "chat_id": "oc_5",
                    "chat_type": "group",
                    "message_type": "text",
                    "content": "{\"text\":\"大家好\"}",
                },
                "sender": {"sender_type": "user"},
            },
        }
    )

    assert agent.chat_calls == [("im-chat:oc_5", "大家好")]
    assert reply_client.calls == [("om_5", "收到")]


def test_auto_reply_handles_group_message_when_mentioning_bot(tmp_path: Path) -> None:
    agent = FakeHarness(chat_responses=[{"status": "message", "message": "我在"}])
    _, worker, reply_client = make_worker(tmp_path, group_reply_mode="mention", harness=agent)

    worker.handle_event(
        {
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "message": {
                    "message_id": "om_6",
                    "chat_id": "oc_6",
                    "chat_type": "group",
                    "message_type": "text",
                    "content": "{\"text\":\"<at user_id=\\\"cli_a94083a8c1b99cbc\\\">bot</at> 你好\"}",
                    "mentions": [{"id": "cli_a94083a8c1b99cbc", "name": "bot"}],
                },
                "sender": {"sender_type": "user"},
            },
        }
    )

    assert agent.chat_calls == [("im-chat:oc_6", "你好")]
    assert reply_client.calls == [("om_6", "我在")]


def test_auto_reply_ignores_group_message_without_mention_in_mention_mode(tmp_path: Path) -> None:
    agent = FakeHarness(chat_responses=[{"status": "message", "message": "我在"}])
    _, worker, reply_client = make_worker(tmp_path, group_reply_mode="mention", harness=agent)

    worker.handle_event(
        {
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "message": {
                    "message_id": "om_7",
                    "chat_id": "oc_7",
                    "chat_type": "group",
                    "message_type": "text",
                    "content": "{\"text\":\"大家好\"}",
                    "mentions": [],
                },
                "sender": {"sender_type": "user"},
            },
        }
    )

    assert agent.chat_calls == []
    assert reply_client.calls == []


def test_auto_reply_handles_group_message_when_mentioning_bot_open_id(tmp_path: Path) -> None:
    agent = FakeHarness(chat_responses=[{"status": "message", "message": "收到"}])
    _, worker, reply_client = make_worker(
        tmp_path,
        group_reply_mode="mention",
        bot_mention_ids=("ou_60e196601a28e03d91cf7cfbf816e3b7",),
        harness=agent,
    )

    worker.handle_event(
        {
            "message_id": "om_8",
            "chat_id": "oc_8",
            "chat_type": "group",
            "message_type": "text",
            "content": "@小爱 帮我查今天日程",
            "mentions": [
                {
                    "id": "ou_60e196601a28e03d91cf7cfbf816e3b7",
                    "key": "@_user_1",
                    "name": "小爱",
                }
            ],
            "sender_type": "user",
        }
    )

    assert agent.chat_calls == [("im-chat:oc_8", "帮我查今天日程")]
    assert reply_client.calls == [("om_8", "收到")]


def test_auto_reply_handles_group_message_when_mentioning_bot_name(tmp_path: Path) -> None:
    agent = FakeHarness(chat_responses=[{"status": "message", "message": "收到"}])
    _, worker, reply_client = make_worker(
        tmp_path,
        group_reply_mode="mention",
        bot_mention_names=("小爱",),
        harness=agent,
    )

    worker.handle_event(
        {
            "message_id": "om_9",
            "chat_id": "oc_9",
            "chat_type": "group",
            "message_type": "text",
            "content": "@小爱 帮我查今天日程",
            "mentions": [
                {
                    "id": "ou_unknown",
                    "key": "@_user_1",
                    "name": "小爱",
                }
            ],
            "sender_type": "user",
        }
    )

    assert agent.chat_calls == [("im-chat:oc_9", "帮我查今天日程")]
    assert reply_client.calls == [("om_9", "收到")]


def test_auto_reply_strips_mention_key_prefix_from_group_message(tmp_path: Path) -> None:
    agent = FakeHarness(chat_responses=[{"status": "message", "message": "收到"}])
    _, worker, reply_client = make_worker(
        tmp_path,
        group_reply_mode="mention",
        bot_mention_ids=("ou_60e196601a28e03d91cf7cfbf816e3b7",),
        harness=agent,
    )

    worker.handle_event(
        {
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "message": {
                    "message_id": "om_10",
                    "chat_id": "oc_10",
                    "chat_type": "group",
                    "message_type": "text",
                    "content": "{\"text\":\"@_user_1 帮我查今天日程\"}",
                    "mentions": [
                        {
                            "id": "ou_60e196601a28e03d91cf7cfbf816e3b7",
                            "key": "@_user_1",
                            "name": "小爱",
                        }
                    ],
                },
                "sender": {"sender_type": "user"},
            },
        }
    )

    assert agent.chat_calls == [("im-chat:oc_10", "帮我查今天日程")]
    assert reply_client.calls == [("om_10", "收到")]
