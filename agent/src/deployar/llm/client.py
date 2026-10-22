"""LLMClient seam (decision #2): the Claude Agent SDK today, BoxAPI later by env var."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

from deployar.runtime.gate import CanUseTool
from deployar.tools.registry import Registry, ToolContext


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolUse:
    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    tool_use_id: str
    status: str  # ok | limitation | error


@dataclass(frozen=True)
class Done:
    session_id: str | None
    is_error: bool = False
    error: str | None = None
    model: str | None = None


LLMEvent = TextDelta | ToolUse | ToolResult | Done


class LLMClient(Protocol):
    def run(
        self,
        *,
        prompt: str,
        system_prompt: str,
        registry: Registry,
        tool_ctx: ToolContext,
        can_use_tool: CanUseTool,
        max_turns: int,
        resume: str | None = None,
    ) -> AsyncIterator[LLMEvent]: ...
