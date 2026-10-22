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
    (
        "registrar_dns_records",
        {
            "domain": "shop.torobgard.ir",
            "records": [{"type": "CNAME", "name": "shop.torobgard.ir", "value": "torob-gard-api.liara.run"}],
        },
    ),
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
        incident = "SRE" in system_prompt
        deploying = not incident and ("deploy" in system_prompt.lower() or "بالا" in prompt)
        script = INCIDENT_SCRIPT if incident else DEPLOY_SCRIPT if deploying else SCRIPT
        yield TextDelta("اول اندازه می‌گیرم و لاگ و متریک را می‌خوانم." if incident else
                        "مخزن را می‌خوانم و اپ را روی لیارا می‌سازم." if deploying else
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


INCIDENT_SCRIPT: list[tuple[str, dict[str, Any]]] = [
    ("http_probe", {"path": "/api/products"}),
    ("get_logs", {"since": "30m"}),
    ("report_diagnosis", {}),
    ("resize_plan", {"plan_id": "ir-medium", "reason_fa": "۳ بار OOM در ۳۰ دقیقه؛ RAM از ۵۱۲ به ۱۰۲۴"}),
    ("verify_after_action", {}),
]
BEFORE = {"url": "https://torob-gard-api.liara.run/api/products", "codes": {"200": 3, "502": 2}, "error_rate": 0.4,
          "p50_ms": 4180, "p95_ms": 6900, "memory_mb": 498, "observed_at": "2026-10-22T09:14:02+00:00"}  # fmt: skip


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

    @reg.tool("registrar_dns_records", group="liara", risk="human_only", description="fake registrar", input_schema={})
    async def registrar_dns_records(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
        raise AssertionError("human_only never runs")

    @reg.tool("http_probe", group="probe", risk="read", description="fake probe", input_schema={})
    async def http_probe(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
        await ensure_project(ctx, "amircodington/torob-gard", "main")
        return Ok(BEFORE, source=f"probe:{BEFORE['url']}")

    @reg.tool("report_diagnosis", group="sre", risk="read", description="fake diagnosis", input_schema={})
    async def report_diagnosis(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
        hyps = [
            {"cause_fa": "کمبود RAM؛ اپ ۳ بار از حافظه بیرون زده", "likelihood": 0.72, "action_fa": "پلن ۱ گیگ",
             "evidence": ["09:12:44 Worker (pid:42) was sent SIGKILL! Perhaps out of memory?", "memory 498/512 MB"]},
            {"cause_fa": "کوئری کند در /api/products", "likelihood": 0.41, "action_fa": "صفحه‌بندی کوئری",
             "evidence": ["GET /api/products 200 4180ms"]},
            {"cause_fa": "محدودیت CPU", "likelihood": 0.1, "evidence": ["cpu 0.21 of 0.5"]},
        ]  # fmt: skip
        if ctx.emit:
            await ctx.emit("diagnosis", {"symptom_fa": "سایت کند است", "hypotheses": hyps, "baseline": BEFORE})
        return Ok({"ranked": [h["cause_fa"] for h in hyps]}, source="fake:diagnosis")

    @reg.tool(
        "resize_plan",
        group="liara",
        risk="sensitive",
        description="fake resize",
        input_schema={},
        preview=lambda a: {**app_card(a), "title_fa": "تغییر پلن اپ به ir-medium", "cost_delta_toman": 700_000},
    )
    async def resize_plan(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
        return Ok({"from": "ir-small", "to": "ir-medium"}, source="fake:resize")

    @reg.tool("verify_after_action", group="sre", risk="read", description="fake verify", input_schema={})
    async def verify_after_action(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
        await asyncio.sleep(1.5)
        after = {**BEFORE, "codes": {"200": 5}, "error_rate": 0.0, "p50_ms": 320, "p95_ms": 540, "memory_mb": 610,
                 "observed_at": datetime.now(UTC).isoformat()}  # fmt: skip
        if ctx.emit:
            verdict = "بهتر شد: نرخ خطا از ۴۰٪ به صفر و p50 از ۴٫۲ ثانیه به ۳۲۰ میلی‌ثانیه رسید."
            await ctx.emit("verify", {"before": BEFORE, "after": after, "fixed": True, "verdict_fa": verdict})
        return Ok({"fixed": True}, source="fake:verify")

    return reg
