"""Dashboard and monitor reads for the UI. Same read-only Liara calls as the tools, no LLM in between.

Every block carries its source and time (hard rule 3); a failing Liara call becomes an error block, not a 500.
"""

import asyncio
import time
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import select

from deployar import messages_fa as fa
from deployar.api.deps import get_runtime, require_user
from deployar.clients.liara import LiaraNotFound
from deployar.core.errors import DeployarError
from deployar.models import GithubConnection, LiaraConnection
from deployar.runtime.orchestrator import Runtime
from deployar.tools.liara.read import liara_client_for

router = APIRouter(prefix="/api")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _err(e: DeployarError) -> dict[str, str]:
    return {"code": e.code, "message_fa": e.message_fa}


@router.get("/dashboard")
async def dashboard(
    user_id: Annotated[uuid.UUID, Depends(require_user)],
    rt: Annotated[Runtime, Depends(get_runtime)],
) -> dict[str, Any]:
    async with rt.sessions() as s:
        lc = await s.scalar(
            select(LiaraConnection).where(LiaraConnection.user_id == user_id, LiaraConnection.status == "active")
        )
        gc = await s.scalar(
            select(GithubConnection).where(GithubConnection.user_id == user_id, GithubConnection.status == "active")
        )
    github = gc and {"login": gc.account_login, "token_last4": gc.token_last4,
                     "verified_at": (gc.last_verified_at or gc.created_at).isoformat()}  # fmt: skip
    liara: dict[str, Any] | None = None
    if lc:
        liara = {"token_last4": lc.token_last4, "team_id": lc.team_id, "account": lc.liara_account_email,
                 "verified_at": (lc.last_verified_at or lc.created_at).isoformat()}  # fmt: skip
        try:
            async with await liara_client_for(rt.sessions, user_id) as c:
                billing, projects = await asyncio.gather(c.billing(), c.projects())  # Liara is ~3s away
            liara["balance"] = {"toman": billing.get("balance"), "source": "liara:/v1/billing", "observed_at": _now()}
            liara["apps"] = {
                "items": [
                    {
                        "name": p.get("project_id"),
                        "type": p.get("type"),
                        "status": p.get("status"),
                        "plan": p.get("planID"),
                        "deployed": p.get("isDeployed"),
                    }
                    for p in projects
                ],  # fmt: skip
                "source": "liara:/v1/projects",
                "observed_at": _now(),
            }
        except DeployarError as e:
            liara["error"] = _err(e)
    return {"liara": liara, "github": github, "observed_at": _now()}


def _series(data: dict[str, Any]) -> list[list[float]]:
    """Liara gives one series per applet; the UI shows the app as a whole, so values are summed per timestamp."""
    acc: dict[int, float] = {}
    for applet in data.get("result") or []:
        for ts, v in applet.get("values") or []:
            acc[int(ts)] = acc.get(int(ts), 0.0) + float(v)
    return [[ts, acc[ts]] for ts in sorted(acc)]


@router.get("/apps/{name}/monitor")
async def monitor(
    user_id: Annotated[uuid.UUID, Depends(require_user)],
    rt: Annotated[Runtime, Depends(get_runtime)],
    name: Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")],
    minutes: Annotated[int, Query(ge=5, le=1440)] = 60,
) -> dict[str, Any]:
    since = int(time.time()) - 60 * minutes
    base = f"liara:/v1/projects/{name}"
    out: dict[str, Any] = {"name": name, "minutes": minutes, "observed_at": _now()}
    async with await liara_client_for(rt.sessions, user_id) as c:
        try:
            p = await c.project(name)
        except LiaraNotFound as e:
            raise DeployarError("app_not_found", fa.APP_NOT_FOUND) from e
        out["status"] = {"status": p.get("status"), "plan": p.get("planID"), "scale": p.get("scale"),
                         "type": p.get("type"), "source": base}  # fmt: skip
        lines = await c.logs(name, since)
        out["logs"] = {"lines": [{"ts": ln.get("datetime"), "type": ln.get("type"), "message": ln.get("message")}
                                 for ln in lines[-300:]], "source": f"liara:/v2/projects/{name}/logs"}  # fmt: skip
        try:
            memory = _series(await c.metrics(name, "memory", since))
            cpu = _series(await c.metrics(name, "cpu", since))
            out["metrics"] = {"memory": memory, "cpu": cpu, "source": f"{base}/metrics"}
        except LiaraNotFound:
            out["metrics"] = None  # the UI shows a LimitationNote
        rel = await c.releases(name, 5)
        out["releases"] = {"current": rel.get("currentRelease"), "source": f"{base}/releases", "items": [
            {"id": r.get("_id"), "state": r.get("state"), "created_at": r.get("createdAt")}
            for r in rel.get("releases") or []]}  # fmt: skip
    return out
