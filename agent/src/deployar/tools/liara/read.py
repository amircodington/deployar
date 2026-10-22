"""Liara read tools (risk: read). Every value carries its source and time (hard rule 3).

The token is resolved and decrypted here, per call; it is never a tool argument or part of a result.
"""

import time
import uuid
from typing import Any

from sqlalchemy import select

from deployar import messages_fa as fa
from deployar.clients.liara import LiaraClient, LiaraNotFound
from deployar.core.crypto import aad_for, get_vault
from deployar.core.errors import DeployarError
from deployar.models import LiaraConnection, Project
from deployar.tools.registry import REGISTRY, ToolContext, deployar_tool
from deployar.tools.results import Limitation, Ok, ToolError, ToolResult

# Console prices on 2026-10-22, tier پایه (docs/evidence/liara-console-2026-10-22.md); VAT on top.
# Fallback only: live /v1/me plans are used whenever the call works (shape confirmed 2026-10-22).
STATIC_PLANS = [
    {"name": "زمین", "ram_mb": 512, "cpu": 0.5, "disk_gb": 5, "toman_month": 950_000, "toman_hour": 1_318},
    {"name": "مریخ", "ram_mb": 1024, "cpu": 1, "disk_gb": 10, "toman_month": 1_650_000, "toman_hour": 2_290},
    {"name": "مشتری", "ram_mb": 2048, "cpu": 1, "disk_gb": 20, "toman_month": 2_950_000, "toman_hour": 4_096},
    {"name": "زحل", "ram_mb": 4096, "cpu": 2, "disk_gb": 40, "toman_month": 5_300_000, "toman_hour": 7_360},
]
STATIC_SOURCE = "static:liara-console-2026-10-22"


async def liara_client(ctx: ToolContext) -> LiaraClient:
    """The user's active connection, decrypted for this call only."""
    async with ctx.sessions() as s:
        conn = await s.scalar(
            select(LiaraConnection).where(LiaraConnection.user_id == ctx.user_id, LiaraConnection.status == "active")
        )
    if conn is None:
        raise DeployarError("no_liara_connection", fa.NO_LIARA_CONNECTION)
    token = get_vault().decrypt(
        conn.token_ciphertext, conn.key_version, aad_for("liara_connection", conn.id, conn.user_id)
    )
    return LiaraClient(token, conn.team_id)


async def app_name(ctx: ToolContext, project_id: str | None) -> str:
    pid = uuid.UUID(project_id) if project_id else ctx.project_id
    if pid is None:
        raise DeployarError("app_not_created", fa.APP_NOT_CREATED)
    async with ctx.sessions() as s:
        name = await s.scalar(select(Project.liara_app_name).where(Project.id == pid, Project.user_id == ctx.user_id))
    if not name:
        raise DeployarError("app_not_created", fa.APP_NOT_CREATED)
    return name


async def _guard(call: Any) -> ToolResult:
    """Map client errors to results the model can relay (ADR 9: API gaps are results, not exceptions)."""
    try:
        result: ToolResult = await call
        return result
    except DeployarError as e:
        return ToolError(e.code, e.message_fa, retryable=e.code == "liara_unreachable")
    except LiaraNotFound:
        return ToolError("app_not_found", fa.APP_NOT_FOUND)


PROJECT = {"type": "object", "properties": {"project_id": {"type": "string"}}}


@deployar_tool("get_balance", group="liara", risk="read", description="موجودی حساب لیارا به تومان.", input_schema={
    "type": "object", "properties": {}})  # fmt: skip
async def get_balance(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        async with await liara_client(ctx) as c:
            b = await c.billing()
        return Ok({"balance_toman": b.get("balance"), "min_credit_toman": b.get("minCreditAmount")},
                  source="liara:/v1/billing")  # fmt: skip

    return await _guard(run())


@deployar_tool("list_plans", group="liara", risk="read", description="پلن‌های اپ/دیتابیس لیارا با قیمت.", input_schema={
    "type": "object", "properties": {"kind": {"type": "string", "enum": ["app", "db"]}}})  # fmt: skip
async def list_plans(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        async with await liara_client(ctx) as c:
            me = await c.me_summary()
        if me.get("plans"):
            return Ok({"plans": me["plans"], "kind": args.get("kind", "app")}, source="liara:/v1/me")
        return Ok({"plans": STATIC_PLANS, "note_fa": fa.PLANS_FROM_TABLE}, source=STATIC_SOURCE)

    return await _guard(run())


@deployar_tool("get_app_status", group="liara", risk="read", description="وضعیت، پلن و آخرین انتشار اپ.",
               input_schema=PROJECT)  # fmt: skip
async def get_app_status(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        name = await app_name(ctx, args.get("project_id"))
        async with await liara_client(ctx) as c:
            p = await c.project(name)
        keep = ("project_id", "type", "status", "scale", "planID", "hourlyPrice", "isDeployed", "zeroDowntime")
        return Ok({k: p.get(k) for k in keep}, source=f"liara:/v1/projects/{name}")

    return await _guard(run())


@deployar_tool("get_env_keys", group="liara", risk="read", description="فقط نام متغیرهای محیطی اپ (بدون مقدار).",
               input_schema=PROJECT)  # fmt: skip
async def get_env_keys(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        name = await app_name(ctx, args.get("project_id"))
        async with await liara_client(ctx) as c:
            p = await c.project(name)
        return Ok({"keys": p["env_keys"]}, source=f"liara:/v1/projects/{name}")

    return await _guard(run())


@deployar_tool("get_logs", group="liara", risk="read", description="لاگ‌های اخیر اپ (حداکثر ۵۰۰ خط).", input_schema={
    "type": "object", "properties": {"project_id": {"type": "string"}, "minutes": {"type": "integer"},
                                     "grep": {"type": "string"}}})  # fmt: skip
async def get_logs(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        name = await app_name(ctx, args.get("project_id"))
        since = int(time.time()) - 60 * int(args.get("minutes") or 60)
        async with await liara_client(ctx) as c:
            lines = await c.logs(name, since)
        if grep := args.get("grep"):
            lines = [ln for ln in lines if grep.lower() in str(ln.get("message", "")).lower()]
        tail = [{"ts": ln.get("datetime"), "type": ln.get("type"), "message": ln.get("message")} for ln in lines[-500:]]
        return Ok({"lines": tail, "count": len(lines)}, source=f"liara:/v1/projects/{name}/logs")

    return await _guard(run())


@deployar_tool("get_metrics", group="liara", risk="read", description="مصرف CPU و RAM اپ (لحظه‌ای و سری زمانی).",
               input_schema={"type": "object", "properties": {"project_id": {"type": "string"},
                                                              "minutes": {"type": "integer"}}})  # fmt: skip
async def get_metrics(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        name = await app_name(ctx, args.get("project_id"))
        since = int(time.time()) - 60 * int(args.get("minutes") or 60)
        try:
            async with await liara_client(ctx) as c:
                summary = await c.metrics_summary(name)
                memory = await c.metrics(name, "memory", since)
                cpu = await c.metrics(name, "cpu", since)
        except LiaraNotFound:
            return Limitation("metrics_unavailable", fa.METRICS_UNAVAILABLE)
        return Ok({"summary": summary, "memory": memory.get("result"), "cpu": cpu.get("result")},
                  source=f"liara:/v1/projects/{name}/metrics")  # fmt: skip

    return await _guard(run())


@deployar_tool("list_releases", group="liara", risk="read", description="انتشارهای اخیر اپ و وضعیت هر کدام.",
               input_schema={"type": "object", "properties": {"project_id": {"type": "string"},
                                                              "limit": {"type": "integer"}}})  # fmt: skip
async def list_releases(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        name = await app_name(ctx, args.get("project_id"))
        async with await liara_client(ctx) as c:
            data = await c.releases(name, int(args.get("limit") or 10))
        releases = [
            {"id": r.get("_id"), "state": r.get("state"), "created_at": r.get("createdAt"),
             "finished_at": r.get("finishedAt"), "commit": (r.get("gitInfo") or {}).get("commit")}
            for r in data.get("releases") or []
        ]  # fmt: skip
        return Ok({"current": data.get("currentRelease"), "releases": releases},
                  source=f"liara:/v1/projects/{name}/releases")  # fmt: skip

    return await _guard(run())


__all__ = ["REGISTRY"]
