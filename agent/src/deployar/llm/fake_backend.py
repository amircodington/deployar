"""LLM_BACKEND=fake: a scripted turn through the real gate, registry and event bus.

For UI work and contract tests without spending Claude usage. Never the default.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from claude_agent_sdk import PermissionResultAllow, ToolPermissionContext

from deployar.llm.client import Done, LLMEvent, TextDelta, ToolResult, ToolUse
from deployar.runtime.gate import CanUseTool
from deployar.tools.project import ensure_project, project_of
from deployar.tools.registry import PREFIX, Registry, ToolContext
from deployar.tools.results import Ok
from deployar.tools.results import ToolResult as ToolOutcome

SCRIPT: list[tuple[str, dict[str, Any]]] = [("get_logs", {"since": "1h"}), ("restart_app", {"project": "demo"})]
# a deploy ask walks the deploy cards (approval, build progress, live URL) without Liara or Claude
DEPLOY_SCRIPT: list[tuple[str, dict[str, Any]]] = [
    ("analyze_repo", {"repo": "amircodington/torob-gard"}),
    ("create_app", {"app_root": "api", "platform": "docker", "plan_id": "ir-medium", "reason_fa": "اپ api ترب‌گرد"}),
    ("request_env_values", {"keys": [{"key": "BOXAPI_KEY", "hint_fa": "کلید سرویس جستجو"}]}),
    ("deploy_release", {"reason_fa": "انتشار آخرین commit"}),
    ("watch_deployment", {}),
]


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
        deploying = "deploy" in system_prompt.lower() or "بالا" in prompt
        script = DEPLOY_SCRIPT if deploying else SCRIPT
        yield TextDelta("مخزن را می‌خوانم و اپ را روی لیارا می‌سازم." if deploying else
                        "لاگ‌ها را نگاه می‌کنم و اگر لازم بود ری‌استارت را پیشنهاد می‌دهم.")  # fmt: skip
        for i, (name, args) in enumerate(script):
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

    @reg.tool("analyze_repo", group="github", risk="read", description="fake analysis", input_schema={})
    async def analyze_repo(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
        await ensure_project(ctx, args["repo"], "main")  # a real draft row, so approvals have a project
        return Ok({"apps": ["api", "web"]}, source="fake:github")

    def app_card(a: dict[str, Any]) -> dict[str, Any]:
        source = {"source": "fake:/v1/me", "observed_at": "2026-10-22T10:00:00+00:00"}
        return {"title_fa": "ساخت اپ torob-gard-api روی لیارا (ir-medium)", "why_fa": a.get("reason_fa"),
                "cost_delta_toman": 1_650_000, "cost_source": source}  # fmt: skip

    @reg.tool(
        "create_app", group="liara", risk="sensitive", description="fake create", input_schema={}, preview=app_card
    )
    async def create_app(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
        return Ok({"app": "torob-gard-api"}, source="fake:create")

    @reg.tool("request_env_values", group="liara", risk="read", description="fake env form", input_schema={})
    async def request_env_values(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
        pid = await project_of(ctx)
        if ctx.emit and pid:
            await ctx.emit("env_request", {"project_id": str(pid), "keys": args["keys"]})
        return Ok({"waiting_for_user": [k["key"] for k in args["keys"]]}, source="fake:form")

    @reg.tool(
        "deploy_release",
        group="liara",
        risk="sensitive",
        description="fake deploy",
        input_schema={},
        preview=lambda a: {"title_fa": "انتشار main روی لیارا", "why_fa": a.get("reason_fa")},
    )
    async def deploy_release(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
        return Ok({"deployment_id": "demo", "release_id": "rel-demo"}, source="fake:deploy")

    @reg.tool("watch_deployment", group="liara", risk="read", description="fake watch", input_schema={})
    async def watch_deployment(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
        log = ["Step 1/6 : FROM python:3.13-slim", "Step 2/6 : RUN apt-get install -y gdal-bin",
               "Step 4/6 : RUN pip install -r requirements.txt", "Successfully tagged torob-gard-api:latest",
               "Pushing... 100%", "Starting gunicorn 23.0"]  # fmt: skip
        for i, state in enumerate(["QUEUED", "BUILDING", "BUILDING", "PUSHING", "DEPLOYING", "READY"]):
            if ctx.emit:
                await ctx.emit("deploy_progress", {"deployment_id": "demo", "app": "torob-gard-api", "state": state,
                                                   "log_tail": log[: i + 1]})  # fmt: skip
            await asyncio.sleep(0.9)
        if ctx.emit:
            await ctx.emit("live_url", {"url": "https://torob-gard-api.liara.run", "app": "torob-gard-api",
                                        "commit": "8c17bc2", "status": 200, "ms": 184,
                                        "observed_at": datetime.now(UTC).isoformat()})  # fmt: skip
        return Ok({"state": "READY"}, source="fake:watch")

    return reg
