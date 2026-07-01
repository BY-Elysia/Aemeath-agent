from __future__ import annotations

from typing import Any, Callable

from ..tool_executor import ToolExecutor
from .base import Capability
from .conversation import ConversationCapability
from .feishu_calendar import FeishuCalendarCapability
from .feishu_contact import FeishuContactCapability
from .feishu_docs import FeishuDocsCapability
from .feishu_im import FeishuImCapability
from .feishu_search import FeishuSearchCapability
from .paper_reader import PaperReaderCapability


CapabilityFactory = Callable[[ToolExecutor, Any], Capability]


def _conversation_factory(_: ToolExecutor, __: Any = None) -> Capability:
    return ConversationCapability()


def _paper_reader_factory(executor: ToolExecutor, config: Any) -> Capability:
    if config is None:
        raise ValueError("paper_reader capability requires AppConfig")
    return PaperReaderCapability(config, executor)


CAPABILITY_FACTORIES: dict[str, CapabilityFactory] = {
    "conversation": _conversation_factory,
    "feishu_contact": lambda executor, _config: FeishuContactCapability(executor),
    "feishu_im": lambda executor, _config: FeishuImCapability(executor),
    "feishu_calendar": lambda executor, _config: FeishuCalendarCapability(executor),
    "feishu_docs": lambda executor, _config: FeishuDocsCapability(executor),
    "feishu_search": lambda executor, _config: FeishuSearchCapability(executor),
    "paper_reader": _paper_reader_factory,
}


DEFAULT_ENABLED_CAPABILITIES: tuple[str, ...] = (
    "conversation",
    "feishu_contact",
    "feishu_im",
    "feishu_calendar",
    "feishu_docs",
    "feishu_search",
    "paper_reader",
)


def load_capabilities(names: tuple[str, ...], executor: ToolExecutor, config: Any = None) -> list[Capability]:
    capabilities: list[Capability] = []
    for raw_name in names:
        name = raw_name.strip()
        if not name:
            continue
        factory = CAPABILITY_FACTORIES.get(name)
        if factory is None:
            raise ValueError(f"unknown capability: {name}")
        capabilities.append(factory(executor, config))
    return capabilities
