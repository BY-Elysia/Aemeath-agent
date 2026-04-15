from __future__ import annotations

from feishu_agent.cli_runner import CommandResult
from feishu_agent.tool_executor import ToolExecutor


class DummyRunner:
    def run(self, args):
        raise AssertionError("not used")


def test_map_bot_availability_error() -> None:
    executor = ToolExecutor(DummyRunner())
    result = CommandResult(
        command=["lark-cli", "im", "+messages-send"],
        returncode=1,
        stdout='{"ok": false, "error": {"type": "api_error", "code": 230013, "message": "HTTP 400: Bot has NO availability to this user."}}',
        stderr="",
        duration_ms=5,
        parsed_json={"ok": False, "error": {"type": "api_error", "code": 230013, "message": "HTTP 400: Bot has NO availability to this user."}},
    )

    error = executor._map_error(result.parsed_json, result)
    assert error.category == "bot_availability"
    assert "availability" in error.message.lower()


def test_map_missing_scope_error() -> None:
    executor = ToolExecutor(DummyRunner())
    result = CommandResult(
        command=["lark-cli", "im", "+messages-search"],
        returncode=3,
        stdout='{"ok": false, "error": {"type": "missing_scope", "message": "missing required scope(s): search:message"}}',
        stderr="",
        duration_ms=5,
        parsed_json={"ok": False, "error": {"type": "missing_scope", "message": "missing required scope(s): search:message"}},
    )

    error = executor._map_error(result.parsed_json, result)
    assert error.category == "permission_denied"


def test_normalize_search_user_reads_data_wrapper() -> None:
    executor = ToolExecutor(DummyRunner())
    payload = executor._normalize_search_user(
        {
            "ok": True,
            "identity": "user",
            "data": {
                "users": [
                    {
                        "name": "周灿宇",
                        "open_id": "ou_xxx",
                        "email": "a@example.com",
                    }
                ],
                "has_more": False,
                "page_token": "",
            },
        }
    )

    assert payload["matches"] == [
        {
            "name": "周灿宇",
            "open_id": "ou_xxx",
            "email": "a@example.com",
            "mobile": None,
            "department": None,
            "enterprise_email": None,
        }
    ]


def test_normalize_search_messages_reads_data_wrapper() -> None:
    executor = ToolExecutor(DummyRunner())
    payload = executor._normalize_search_messages(
        {
            "ok": True,
            "identity": "user",
            "data": {
                "messages": [{"message_id": "om_xxx", "content": "你好"}],
                "total": 1,
                "has_more": False,
                "page_token": "",
            },
        }
    )

    assert payload["total"] == 1
    assert payload["messages"][0]["message_id"] == "om_xxx"
