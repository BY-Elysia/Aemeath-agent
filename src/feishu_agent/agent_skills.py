from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AGENT_SKILLS_ROOT = PROJECT_ROOT / ".agents" / "skills"
DEFAULT_ENABLED_AGENT_SKILLS: tuple[str, ...] = ("feishu-agent-workflows",)
MAX_AGENT_SKILL_CHARS = 12000


@dataclass(frozen=True)
class AgentSkillDocument:
    name: str
    description: str
    body: str
    path: Path


def load_agent_skill_documents(
    names: tuple[str, ...],
    *,
    root: Path = DEFAULT_AGENT_SKILLS_ROOT,
) -> list[AgentSkillDocument]:
    documents: list[AgentSkillDocument] = []
    for raw_name in names:
        name = raw_name.strip()
        if not name:
            continue
        path = root / name / "SKILL.md"
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8")
        metadata, body = _split_frontmatter(raw)
        documents.append(
            AgentSkillDocument(
                name=str(metadata.get("name") or name),
                description=str(metadata.get("description") or ""),
                body=_truncate(body.strip(), MAX_AGENT_SKILL_CHARS),
                path=path,
            )
        )
    return documents


def format_agent_skill_guidance(documents: list[AgentSkillDocument]) -> list[str]:
    return [
        f"agent skill: {document.name}\n"
        f"description: {document.description}\n\n"
        f"{document.body}"
        for document in documents
    ]


def _split_frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    value = markdown.strip()
    if not value.startswith("---"):
        return {}, value
    match = re.match(r"^---\s*\n(?P<meta>.*?)\n---\s*\n(?P<body>.*)$", value, flags=re.DOTALL)
    if not match:
        return {}, value

    metadata: dict[str, str] = {}
    for line in match.group("meta").splitlines():
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        metadata[key.strip()] = raw_value.strip().strip("'\"")
    return metadata, match.group("body")


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n\n[Agent skill guidance truncated]"
