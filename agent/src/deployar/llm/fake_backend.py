"""LLM_BACKEND=fake: a scripted turn through the real gate, registry and event bus.

For UI work and contract tests without spending Claude usage. Never the default.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from claude_agent_sdk import PermissionResultAllow, ToolPermissionContext

from deployar.llm.client import Done, LLMEvent, TextDelta, ToolResult, ToolUse
from deployar.runtime.gate import CanUseTool
from deployar.tools.registry import PREFIX, Registry, ToolContext
from deployar.tools.results import Ok
from deployar.tools.results import ToolResult as ToolOutcome

SCRIPT = [("get_logs", {"since": "1h"}), ("restart_app", {"project": "demo"})]


class FakeBackend:
    def __init__(self, delay_s: float = 0.0) -> None:
        self.delay_s = delay_s  # lets the UI show the stream arriving piece by piece

    async def run(
        self,
        *,
        prompt: str,
        system_prompt: str,
        registry: Registry,
        tool_ctx: ToolContext,
        can_use_tool: CanUseTool,
        max_turns: int,
        resume: str | None = None,
    ) -> AsyncIterator[LLMEvent]:
        yield TextDelta("لاگ‌ها را نگاه می‌کنم و اگر لازم بود ری‌استارت را پیشنهاد می‌دهم.")
        for i, (name, args) in enumerate(SCRIPT):
            await asyncio.sleep(self.delay_s)
            yield ToolUse(f"tu{i}", PREFIX + name, args)
            perm = await can_use_tool(PREFIX + name, args, ToolPermissionContext(tool_use_id=f"tu{i}"))
            if isinstance(perm, PermissionResultAllow):
                out = await registry.run(tool_ctx, name, args)
                yield ToolResult(f"tu{i}", json.loads(out["content"][0]["text"])["status"])
            else:
                yield ToolResult(f"tu{i}", "error")
        await asyncio.sleep(self.delay_s)
        yield TextDelta("کار تمام شد. لاگ‌ها سالم بود و ری‌استارت طبق تصمیم تو انجام شد یا انجام نشد.")
        yield Done(session_id=None, model="fake")


def demo_registry() -> Registry:
    """Two fake tools whose names exist in the DB risk table (one read, one sensitive)."""
    reg = Registry()

    @reg.tool("get_logs", group="liara", risk="read", description="fake logs", input_schema={"since": str})
    async def get_logs(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
        return Ok({"lines": ["boot ok", "GET /api/health 200"]}, source="fake:logs")

    @reg.tool("restart_app", group="liara", risk="sensitive", description="fake restart", input_schema={"project": str})
    async def restart_app(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
        return Ok({"restarted": args["project"]}, source="fake:restart")

    return reg
