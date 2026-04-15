from __future__ import annotations

from pathlib import Path

from feishu_agent.ark_client import ArkResponse, FunctionCall
from feishu_agent.config import AppConfig
from feishu_agent.errors import ToolExecutionError
from feishu_agent.harness import AgentHarness
from feishu_agent.skills import DEFAULT_ENABLED_SKILLS, load_skills
from feishu_agent.store import SessionStore


class FakeArkClient:
    def __init__(self, responses: list[ArkResponse]) -> None:
        self._responses = responses
        self.prompts: list[str] = []
        self.tools: list[list[dict]] = []

    def create_response(self, prompt: str, tools: list[dict]) -> ArkResponse:
        self.prompts.append(prompt)
        self.tools.append(tools)
        if not self._responses:
            raise AssertionError("No more fake Ark responses configured")
        return self._responses.pop(0)


class FakeToolExecutor:
    def __init__(self, results: dict[str, dict] | None = None, errors: dict[str, ToolExecutionError] | None = None) -> None:
        self.results = results or {}
        self.errors = errors or {}
        self.calls: list[tuple[str, dict]] = []

    def execute(self, tool_name: str, args: dict):
        self.calls.append((tool_name, args))
        if tool_name in self.errors:
            raise self.errors[tool_name]
        result = self.results[tool_name]
        record = type(
            "Record",
            (),
            {
                "command": ["lark-cli", tool_name],
                "stdout": "{}",
                "stderr": "",
                "duration_ms": 1,
            },
        )()
        return result, record


def make_config(tmp_path: Path, *, enabled_skills: tuple[str, ...] = DEFAULT_ENABLED_SKILLS) -> AppConfig:
    return AppConfig(
        ark_api_key="test-key",
        ark_base_url="https://ark.cn-beijing.volces.com/api/v3",
        ark_model="ep-test",
        lark_cli_bin="lark-cli",
        app_db_path=tmp_path / "app.db",
        command_timeout_seconds=10,
        max_history_messages=20,
        max_tool_round_trips=4,
        feishu_agent_base_url="http://127.0.0.1:8000",
        auto_reply_p2p_only=True,
        group_reply_mode="off",
        bot_mention_ids=(),
        bot_mention_names=(),
        agent_persona="aemeath",
        enabled_skills=enabled_skills,
    )


def make_harness(
    tmp_path: Path,
    *,
    ark_responses: list[ArkResponse],
    results: dict[str, dict] | None = None,
    errors: dict[str, ToolExecutionError] | None = None,
    enabled_skills: tuple[str, ...] = DEFAULT_ENABLED_SKILLS,
):
    config = make_config(tmp_path, enabled_skills=enabled_skills)
    store = SessionStore(config.app_db_path)
    ark = FakeArkClient(ark_responses)
    executor = FakeToolExecutor(results=results, errors=errors)
    harness = AgentHarness(
        config=config,
        store=store,
        ark_client=ark,
        tool_executor=executor,
        skills=load_skills(enabled_skills, executor),
    )
    return harness, store, ark, executor


def test_read_tool_then_answer(tmp_path: Path) -> None:
    harness, store, _, executor = make_harness(
        tmp_path,
        ark_responses=[
            ArkResponse(
                text=None,
                function_calls=[FunctionCall(name="search_user", arguments={"name": "周灿宇"})],
                raw={},
            ),
            ArkResponse(text="找到 1 个匹配用户：周灿宇。", function_calls=[], raw={}),
        ],
        results={
            "search_user": {
                "matches": [{"name": "周灿宇", "open_id": "ou_xxx"}],
                "has_more": False,
                "page_token": "",
            }
        },
    )

    response = harness.handle_message("s1", "帮我找一下周灿宇", source="shell")

    assert response.status == "message"
    assert response.message == "找到 1 个匹配用户：周灿宇。"
    assert executor.calls == [("search_user", {"name": "周灿宇"})]
    messages = store.get_messages("s1", 10)
    assert [m["role"] for m in messages] == ["user", "assistant"]


def test_write_tool_returns_pending_action_and_confirm_executes(tmp_path: Path) -> None:
    harness, _, _, executor = make_harness(
        tmp_path,
        ark_responses=[
            ArkResponse(
                text=None,
                function_calls=[
                    FunctionCall(
                        name="send_dm",
                        arguments={"user_open_id": "ou_xxx", "text": "你好", "send_as": "bot"},
                    )
                ],
                raw={},
            )
        ],
        results={
            "send_dm": {
                "message_id": "om_123",
                "chat_id": "oc_123",
                "create_time": "2026-04-13 12:00:00",
            }
        },
    )

    response = harness.handle_message("s2", "给周灿宇发你好", source="shell")

    assert response.status == "pending_action"
    assert response.pending_action is not None
    assert response.pending_action.tool_name == "send_dm"
    assert executor.calls == []

    confirm_response = harness.confirm_action(response.pending_action.action_id, True)
    assert confirm_response.status == "executed"
    assert confirm_response.result == {
        "message_id": "om_123",
        "chat_id": "oc_123",
        "create_time": "2026-04-13 12:00:00",
    }
    assert executor.calls == [("send_dm", {"user_open_id": "ou_xxx", "text": "你好", "send_as": "bot"})]


def test_tool_error_becomes_structured_message(tmp_path: Path) -> None:
    harness, _, _, _ = make_harness(
        tmp_path,
        ark_responses=[
            ArkResponse(
                text=None,
                function_calls=[FunctionCall(name="list_agenda", arguments={"date": "2026-04-13", "send_as": "user"})],
                raw={},
            )
        ],
        errors={
            "list_agenda": ToolExecutionError(
                "permission_denied",
                "App scope not enabled: required scope calendar:calendar.event:read",
                detail={"command": ["lark-cli", "calendar"], "duration_ms": 1},
            )
        },
    )

    response = harness.handle_message("s4", "看下我今天日程", source="shell")

    assert response.status == "error"
    assert "权限不足" in response.message


def test_search_user_unique_match_can_promote_to_pending_send(tmp_path: Path) -> None:
    harness, _, _, _ = make_harness(
        tmp_path,
        ark_responses=[
            ArkResponse(
                text=None,
                function_calls=[FunctionCall(name="search_user", arguments={"name": "周灿宇"})],
                raw={},
            )
        ],
        results={
            "search_user": {
                "matches": [{"name": "周灿宇", "open_id": "ou_xxx"}],
                "has_more": False,
                "page_token": "",
            }
        },
    )

    response = harness.handle_message("s5", "给周灿宇发你好", source="shell")

    assert response.status == "pending_action"
    assert response.pending_action is not None
    assert response.pending_action.tool_name == "send_dm"
    assert response.pending_action.args_preview["user_open_id"] == "ou_xxx"
    assert response.pending_action.args_preview["text"] == "你好"


def test_search_user_unique_match_does_not_short_circuit_when_user_is_asking_for_composed_message(tmp_path: Path) -> None:
    harness, _, _, executor = make_harness(
        tmp_path,
        ark_responses=[
            ArkResponse(
                text=None,
                function_calls=[FunctionCall(name="search_user", arguments={"name": "白洋"})],
                raw={},
            ),
            ArkResponse(
                text=None,
                function_calls=[
                    FunctionCall(
                        name="send_dm",
                        arguments={
                            "user_open_id": "ou_baiyang",
                            "text": "你好，我是爱弥斯，飞行雪绒。现在由我来帮你处理飞书里的消息、日程和文档。",
                            "send_as": "bot",
                        },
                    )
                ],
                raw={},
            ),
        ],
        results={
            "search_user": {
                "matches": [{"name": "白洋", "open_id": "ou_baiyang"}],
                "has_more": False,
                "page_token": "",
            }
        },
    )

    response = harness.handle_message("s6", "给白洋发信息介绍一下你自己", source="shell")

    assert response.status == "pending_action"
    assert response.pending_action is not None
    assert response.pending_action.tool_name == "send_dm"
    assert response.pending_action.args_preview["user_open_id"] == "ou_baiyang"
    assert "爱弥斯" in response.pending_action.args_preview["text"]
    assert executor.calls == [("search_user", {"name": "白洋"})]


def test_disabling_skill_removes_tool_from_model_surface(tmp_path: Path) -> None:
    enabled_skills = tuple(skill for skill in DEFAULT_ENABLED_SKILLS if skill != "feishu_docs")
    harness, _, ark, _ = make_harness(
        tmp_path,
        enabled_skills=enabled_skills,
        ark_responses=[ArkResponse(text="你好", function_calls=[], raw={})],
    )

    harness.handle_message("s7", "你好", source="shell")

    tool_names = {tool["name"] for tool in ark.tools[0]}
    assert "create_doc" not in tool_names


def test_prompt_contains_persona_policy_and_skill_guidance(tmp_path: Path) -> None:
    harness, _, ark, _ = make_harness(
        tmp_path,
        ark_responses=[ArkResponse(text="你好呀", function_calls=[], raw={})],
    )

    harness.handle_message("s8", "你好", source="shell")

    prompt = ark.prompts[0]
    assert "你是爱弥斯" in prompt
    assert "【Policy】" in prompt
    assert "feishu_im skill" in prompt
