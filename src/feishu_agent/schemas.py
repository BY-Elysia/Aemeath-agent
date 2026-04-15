from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=10000)


class PendingActionView(BaseModel):
    action_id: str
    tool_name: str
    summary: str
    args_preview: dict[str, Any]


class ChatResponse(BaseModel):
    status: Literal["message", "pending_action", "error"]
    session_id: str
    message: str | None = None
    pending_action: PendingActionView | None = None


class ConfirmActionRequest(BaseModel):
    confirm: bool


class ConfirmActionResponse(BaseModel):
    status: Literal["executed", "cancelled", "error"]
    action_id: str
    message: str
    result: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    ok: bool
    config_errors: list[str]
    lark_cli_bin: str
    db_path: str

