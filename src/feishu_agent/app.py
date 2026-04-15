from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .config import AppConfig
from .errors import PendingActionError
from .harness import AgentHarness, build_harness
from .schemas import (
    ChatRequest,
    ChatResponse,
    ConfirmActionRequest,
    ConfirmActionResponse,
    HealthResponse,
)


def build_service(config: AppConfig) -> AgentHarness:
    return build_harness(config)


def create_app(config: AppConfig | None = None) -> FastAPI:
    app_config = config or AppConfig.from_env()
    harness = build_service(app_config)
    app = FastAPI(title="Feishu Agent", version="0.1.0")
    app.state.config = app_config
    app.state.harness = harness
    app.state.service = harness

    @app.get("/healthz", response_model=HealthResponse)
    def healthcheck() -> HealthResponse:
        runtime_harness: AgentHarness = app.state.harness
        return runtime_harness.healthcheck()

    @app.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        if app_config.validate():
            raise HTTPException(status_code=500, detail={"config_errors": app_config.validate()})
        runtime_harness: AgentHarness = app.state.harness
        return runtime_harness.handle_message(request.session_id, request.message, source="http")

    @app.post("/actions/{action_id}/confirm", response_model=ConfirmActionResponse)
    def confirm_action(action_id: str, request: ConfirmActionRequest) -> ConfirmActionResponse:
        try:
            runtime_harness: AgentHarness = app.state.harness
            return runtime_harness.confirm_action(action_id, request.confirm)
        except PendingActionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app


def run() -> None:
    import uvicorn

    uvicorn.run("feishu_agent.app:create_app", factory=True, host="127.0.0.1", port=8000, reload=False)
