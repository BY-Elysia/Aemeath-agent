from __future__ import annotations

from typing import Any

from ..tool_executor import ToolExecutor
from .base import Skill, SkillContext, ToolSpec


class FeishuImSkill(Skill):
    name = "feishu_im"
    description = "飞书即时通讯发送能力。"

    def __init__(self, executor: ToolExecutor) -> None:
        self._executor = executor

    def get_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="send_dm",
                description="Send a direct Feishu message to a user by open_id. Use bot identity only.",
                parameters={
                    "type": "object",
                    "properties": {
                        "user_open_id": {"type": "string", "description": "Feishu user open_id."},
                        "text": {"type": "string", "description": "Message content to send."},
                        "send_as": {
                            "type": "string",
                            "enum": ["bot"],
                            "description": "Sending identity. Always bot in v1.",
                            "default": "bot",
                        },
                    },
                    "required": ["user_open_id", "text"],
                    "additionalProperties": False,
                },
                requires_confirmation=True,
            )
        ]

    def get_guidance(self) -> str:
        return (
            "feishu_im skill:\n"
            "- send_dm 只能用于机器人身份的私聊发送。\n"
            "- 当用户意图是“给某人发消息”，且已拿到唯一 open_id 时，调用 send_dm。\n"
            "- 所有消息发送都要走确认流，不能直接宣称已经发出。"
        )

    def execute(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: SkillContext,
    ):
        return self._executor.execute(tool_name, args)
