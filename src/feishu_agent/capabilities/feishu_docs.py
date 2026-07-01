from __future__ import annotations

from typing import Any

from ..tool_executor import ToolExecutor
from .base import Capability, CapabilityContext, ToolSpec


class FeishuDocsCapability(Capability):
    name = "feishu_docs"
    description = "飞书文档创建能力。"

    def __init__(self, executor: ToolExecutor) -> None:
        self._executor = executor

    def get_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="create_doc",
                description="Create a Feishu document from Markdown using bot identity, with optional local images/files.",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Document title."},
                        "markdown": {"type": "string", "description": "Markdown body."},
                        "media_files": {
                            "type": "array",
                            "description": "Optional local images or files to insert into the document after Markdown creation.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string", "description": "Local file path."},
                                    "type": {
                                        "type": "string",
                                        "enum": ["image", "file"],
                                        "default": "image",
                                        "description": "Media block type.",
                                    },
                                    "caption": {"type": "string", "description": "Optional image/file caption."},
                                    "align": {
                                        "type": "string",
                                        "enum": ["left", "center", "right"],
                                        "default": "center",
                                        "description": "Image alignment.",
                                    },
                                },
                                "required": ["path"],
                                "additionalProperties": False,
                            },
                        },
                        "send_as": {
                            "type": "string",
                            "enum": ["bot"],
                            "default": "bot",
                            "description": "Identity. Docs and media are created by bot; lark-cli grants the current CLI user access.",
                        },
                    },
                    "required": ["title", "markdown"],
                    "additionalProperties": False,
                },
                requires_confirmation=True,
            )
        ]

    def get_guidance(self) -> str:
        return (
            "feishu_docs capability:\n"
            "- 创建文档前要先明确标题和正文内容。\n"
            "- 如需把本地图片或文件写入文档，给 create_doc 传 media_files；图片会在正文创建后插入飞书文档。\n"
            "- create_doc 属于写操作，必须进入确认流。"
        )

    def execute(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: CapabilityContext,
    ):
        return self._executor.execute(tool_name, args)
