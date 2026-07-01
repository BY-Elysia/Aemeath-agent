from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..tool_executor import ToolExecutionRecord


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    requires_confirmation: bool


@dataclass(frozen=True)
class CapabilityContext:
    session_id: str
    source: str


class Capability(ABC):
    name: str
    description: str

    @abstractmethod
    def get_tools(self) -> list[ToolSpec]:
        raise NotImplementedError

    @abstractmethod
    def get_guidance(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def execute(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: CapabilityContext,
    ) -> tuple[dict[str, Any], ToolExecutionRecord]:
        raise NotImplementedError

