from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from feishu_agent.app import create_app
from feishu_agent.config import AppConfig
from feishu_agent.schemas import ChatResponse, ConfirmActionResponse, PendingActionView


class StubService:
    def handle_message(self, session_id: str, message: str, source: str) -> ChatResponse:
        return ChatResponse(status="message", session_id=session_id, message=f"echo:{message}")

    def confirm_action(self, action_id: str, confirm: bool) -> ConfirmActionResponse:
        status = "executed" if confirm else "cancelled"
        message = "ok" if confirm else "cancelled"
        return ConfirmActionResponse(status=status, action_id=action_id, message=message, result=None)

    def healthcheck(self):
        from feishu_agent.schemas import HealthResponse

        return HealthResponse(ok=True, config_errors=[], lark_cli_bin="lark-cli", db_path="/tmp/test.db")


def make_config(tmp_path: Path) -> AppConfig:
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
        enabled_skills=("conversation", "feishu_contact"),
    )


def test_app_routes_use_state_service(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path))
    app.state.harness = StubService()
    client = TestClient(app)

    response = client.post("/chat", json={"session_id": "abc", "message": "hello"})
    assert response.status_code == 200
    assert response.json()["message"] == "echo:hello"

    confirm = client.post("/actions/action-1/confirm", json={"confirm": True})
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "executed"


def test_healthcheck(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path))
    client = TestClient(app)

    response = client.get("/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["config_errors"] == []
