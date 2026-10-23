"""Read tools that keep a deploy run honest: follow the build to a live URL, and ask for env values.

watch_deployment runs inside the run (ADR 12) so the checklist, the build-log card and the live URL
reach the same SSE stream the user is watching.
"""

import asyncio
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select, update

from deployar import messages_fa as fa
from deployar.core.redact import redact
from deployar.models import Deployment, Project
from deployar.tools.liara.read import _guard, liara_client
from deployar.tools.project import project_of
from deployar.tools.registry import ToolContext, deployar_tool
from deployar.tools.results import Ok, ToolError, ToolResult

POLL_S = 5.0
TAIL = 40
FAILED = {"FAILED", "TIMEDOUT", "UNHEALTHY", "CANCELED"}
STATUS = {"QUEUED": "building", "BUILDING": "building", "PUSHING": "building", "PUSHED": "releasing",
          "DEPLOYING": "releasing", "READY": "health_check"}  # fmt: skip
# first match wins; the log tail is shown either way
REASONS = [
    ("out of memory", fa.BUILD_OOM), ("killed", fa.BUILD_OOM), ("npm err", fa.BUILD_DEPS),
    ("err_pnpm", fa.BUILD_DEPS), ("modulenotfounderror", fa.BUILD_DEPS), ("no matching distribution", fa.BUILD_DEPS),
    ("dockerfile", fa.BUILD_DOCKERFILE), ("port", fa.BUILD_PORT), ("unhealthy", fa.BUILD_PORT),
]  # fmt: skip


def reason_fa(state: str, tail: list[str]) -> str:
    text = " ".join(tail[-15:]).lower() + " " + state.lower()
    return next((msg for needle, msg in REASONS if needle in text), fa.BUILD_FAILED)


async def probe(url: str, tries: int = 3) -> dict[str, Any]:
    """GET the live URL a few times; any answer below 500 means the app is up."""
    last: dict[str, Any] = {"ok": False, "status": None, "ms": None}
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as http:
        for _ in range(tries):
            started = time.monotonic()
            try:
                r = await http.get(url)
                last = {
                    "ok": r.status_code < 500,
                    "status": r.status_code,
                    "ms": int((time.monotonic() - started) * 1000),
                }
                if last["ok"]:
                    return last
            except httpx.HTTPError as e:
                last = {"ok": False, "status": None, "ms": None, "error": type(e).__name__}
            await asyncio.sleep(3)
    return last


WATCH_SCHEMA = {
    "type": "object",
    "properties": {"deployment_id": {"type": "string"}, "max_wait_s": {"type": "integer"}},
}


@deployar_tool("watch_deployment", group="liara", risk="read", description=fa.WATCH_DESC, input_schema=WATCH_SCHEMA)
async def watch_deployment(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        async with ctx.sessions() as s:
            q = (
                select(Deployment)
                .join(Project, Project.id == Deployment.project_id)
                .where(Project.user_id == ctx.user_id)
            )
            # the id deploy_release returned (or Liara's release id), else this run's latest, else the user's latest
            did = str(args.get("deployment_id") or "")
            try:
                q = q.where(Deployment.id == uuid.UUID(did)) if did else q
            except ValueError:
                q = q.where(Deployment.liara_release_id == did)
            latest = q.order_by(Deployment.created_at.desc()).limit(1)
            d = None if did else await s.scalar(latest.where(Deployment.run_id == ctx.run_id))
            d = d or await s.scalar(latest)
        if d is None or not d.liara_release_id:
            return ToolError("no_deployment", fa.NO_DEPLOYMENT)
        url = f"https://{d.liara_app_name}.liara.run"
        deadline = time.monotonic() + min(int(args.get("max_wait_s") or 300), 600)
        lines: list[str] = []
        since: str | None = None
        state = ""
        async with await liara_client(ctx) as c:
            while True:
                state = str((await c.release(d.liara_release_id)).get("state") or "").upper()
                logs = await c.build_logs(d.liara_release_id, since)
                for out in logs.get("buildOutput") or []:
                    lines.extend(str(out.get("line", "")).rstrip("\n").splitlines())
                    since = out.get("createdAt") or since
                lines = [str(redact(ln)) for ln in lines[-TAIL:]]
                await _set(ctx, d.id, STATUS.get(state, "failed" if state in FAILED else "building"))
                if ctx.emit:
                    progress = {"deployment_id": str(d.id), "app": d.liara_app_name, "state": state or "QUEUED",
                                "log_tail": lines[-12:]}  # fmt: skip
                    await ctx.emit("deploy_progress", progress)
                if state == "READY" or state in FAILED or time.monotonic() > deadline:
                    break
                await asyncio.sleep(POLL_S)

        if state in FAILED:
            why = reason_fa(state, lines)
            await _set(
                ctx, d.id, "failed", build_log_tail="\n".join(lines), error_fa=why, finished_at=datetime.now(UTC)
            )
            return Ok({"state": state, "reason_fa": why, "log_tail": lines[-15:]}, source="liara:/v1/releases")
        if state != "READY":
            return Ok({"state": state or "QUEUED", "still_building": True, "log_tail": lines[-5:]},
                      source="liara:/v1/releases")  # fmt: skip

        health = await probe(url)
        now = datetime.now(UTC)
        up = bool(health["ok"])
        await _set(ctx, d.id, "live" if up else "failed", health=health, live_at=now if up else None,
                   finished_at=now, error_fa=None if up else fa.HEALTH_FAILED)  # fmt: skip
        if health["ok"]:
            async with ctx.sessions.begin() as s:
                await s.execute(update(Project).where(Project.id == d.project_id)
                                .values(live_url=url, current_deployment_id=d.id))  # fmt: skip
            if ctx.emit:
                await ctx.emit("live_url", {"url": url, "app": d.liara_app_name, "commit": d.commit_sha[:7],
                                            "status": health["status"], "ms": health["ms"],
                                            "observed_at": now.isoformat()})  # fmt: skip
        return Ok({"state": state, "url": url, "health": health}, source=f"probe:{url}", observed_at=now.isoformat())

    return await _guard(run())


async def _set(ctx: ToolContext, deployment_id: uuid.UUID, status: str, **values: Any) -> None:
    async with ctx.sessions.begin() as s:
        await s.execute(update(Deployment).where(Deployment.id == deployment_id).values(status=status, **values))


@deployar_tool("request_env_values", group="liara", risk="read", description=fa.REQUEST_ENV_DESC, input_schema={
    "type": "object", "required": ["keys"], "properties": {
        "project_id": {"type": "string"},
        "keys": {"type": "array", "items": {"type": "object", "required": ["key"], "properties": {
            "key": {"type": "string"}, "hint_fa": {"type": "string"}}}}}})  # fmt: skip
async def request_env_values(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    """Shows a form card; values go from the form to /api/projects/{id}/env-values, never through chat."""
    pid = args.get("project_id") or await project_of(ctx)
    if pid is None:
        return ToolError("no_project", fa.NO_PROJECT)
    keys = [{"key": str(k["key"]), "hint_fa": k.get("hint_fa")} for k in args.get("keys") or []]
    if ctx.emit:
        await ctx.emit("env_request", {"project_id": str(pid), "keys": keys})
    return Ok({"waiting_for_user": [k["key"] for k in keys], "note_fa": fa.ENV_WAITING}, source="deployar:form")
