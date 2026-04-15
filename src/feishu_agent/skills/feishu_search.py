from __future__ import annotations

from typing import Any

from ..tool_executor import ToolExecutor
from .base import Skill, SkillContext, ToolSpec


class FeishuSearchSkill(Skill):
    name = "feishu_search"
    description = "飞书消息检索能力。"

    def __init__(self, executor: ToolExecutor) -> None:
        self._executor = executor

    def get_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="search_messages",
                description="Search Feishu messages by keyword using user identity.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search keyword."},
                        "send_as": {
                            "type": "string",
                            "enum": ["user"],
                            "default": "user",
                            "description": "Identity. Always user in v1.",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                requires_confirmation=False,
            )
        ]

    def get_guidance(self) -> str:
        return (
            "feishu_search skill:\n"
            "- 当用户要求搜索聊天记录或关键词消息时，调用 search_messages。\n"
            "- 这是只读能力，不需要确认。"
        )

    def execute(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: SkillContext,
    ):
        return self._executor.execute(tool_name, args)
