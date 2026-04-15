from __future__ import annotations

from typing import Callable

from ..tool_executor import ToolExecutor
from .base import Skill
from .conversation import ConversationSkill
from .feishu_calendar import FeishuCalendarSkill
from .feishu_contact import FeishuContactSkill
from .feishu_docs import FeishuDocsSkill
from .feishu_im import FeishuImSkill
from .feishu_search import FeishuSearchSkill


SkillFactory = Callable[[ToolExecutor], Skill]


def _conversation_factory(_: ToolExecutor) -> Skill:
    return ConversationSkill()


SKILL_FACTORIES: dict[str, SkillFactory] = {
    "conversation": _conversation_factory,
    "feishu_contact": FeishuContactSkill,
    "feishu_im": FeishuImSkill,
    "feishu_calendar": FeishuCalendarSkill,
    "feishu_docs": FeishuDocsSkill,
    "feishu_search": FeishuSearchSkill,
}


DEFAULT_ENABLED_SKILLS: tuple[str, ...] = (
    "conversation",
    "feishu_contact",
    "feishu_im",
    "feishu_calendar",
    "feishu_docs",
    "feishu_search",
)


def load_skills(names: tuple[str, ...], executor: ToolExecutor) -> list[Skill]:
    skills: list[Skill] = []
    for raw_name in names:
        name = raw_name.strip()
        if not name:
            continue
        factory = SKILL_FACTORIES.get(name)
        if factory is None:
            raise ValueError(f"unknown skill: {name}")
        skills.append(factory(executor))
    return skills
