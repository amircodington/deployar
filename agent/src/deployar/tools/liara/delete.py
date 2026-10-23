"""Irreversible deletes (sensitive): a red card that unlocks only when the user types the name (checked in the
decision API, not only in the page), then the list is read again to show it is really gone."""

import asyncio
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update

from deployar import messages_fa as fa
from deployar.clients.liara import LiaraClient, LiaraNotFound
from deployar.models import Project
from deployar.tools.liara.read import _guard, liara_client
from deployar.tools.registry import ToolContext, deployar_tool
from deployar.tools.results import Ok, ToolError, ToolResult

VERIFY_TRIES, VERIFY_WAIT_S = 6, 5.0  # Liara removes it within seconds; give up (and say so) after ~30 s


def _danger(kind_fa: str, name: str, why: str | None) -> dict[str, Any]:
    return {"title_fa": f"حذف {kind_fa} {name} از لیارا (برگشت‌ناپذیر)", "why_fa": why, "danger": True,
            "confirm_text": name, "changes": {"delete": name}}  # fmt: skip


async def _gone(lister: Any, match: Any) -> bool:
    for attempt in range(VERIFY_TRIES):
        if not any(match(x) for x in await lister()):
            return True
        if attempt + 1 < VERIFY_TRIES:
            await asyncio.sleep(VERIFY_WAIT_S)
    return False


@deployar_tool("delete_app", group="liara", risk="sensitive", description=fa.DELETE_APP_DESC,
               preview=lambda a: _danger("اپ", str(a.get("app", "")), a.get("reason_fa")),
               input_schema={"type": "object", "required": ["app"], "properties": {
                   "app": {"type": "string"}, "reason_fa": {"type": "string"}}})  # fmt: skip
async def delete_app(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        name = str(args["app"])
        async with await liara_client(ctx) as c:
            try:
                before = await c.project(name)
            except LiaraNotFound:
                return ToolError("app_not_found", fa.APP_NOT_FOUND)
            linked = await _linked_databases(c, name)  # read before the app (and its env) is gone
            await c.delete_app(name)
            gone = await _gone(c.projects, lambda x: x.get("project_id") == name or x.get("name") == name)
        async with ctx.sessions.begin() as s:  # Deployar's own record of it is archived, never kept as live
            await s.execute(update(Project).where(Project.user_id == ctx.user_id, Project.liara_app_name == name)
                            .values(archived_at=datetime.now(UTC)))  # fmt: skip
        out = {"app": name, "deleted": True, "verified_gone": gone, "linked_databases": linked,
               "was": {k: before.get(k) for k in ("planID", "type", "status", "scale")}}  # fmt: skip
        if not gone:
            out["note_fa"] = fa.DELETED_NOT_YET
        elif linked:
            out["note_fa"] = fa.LINKED_DBS.format(dbs="، ".join(linked))
        return Ok(out, source=f"liara:DELETE /v1/projects/{name} + GET /v1/projects")

    return await _guard(run())


async def _linked_databases(c: LiaraClient, app: str) -> list[str]:
    """Databases this app uses: their hostname appears in one of its env values (DATABASE_URL and the like).
    The values stay here; only hostnames go back to the model."""
    values = " ".join(e["value"] for e in await c.env_pairs(app))
    return [str(d["hostname"]) for d in await c.databases() if d.get("hostname") and str(d["hostname"]) in values]


@deployar_tool("list_databases", group="liara", risk="read", description=fa.LIST_DBS_DESC,
               input_schema={"type": "object", "properties": {}})  # fmt: skip
async def list_databases(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        async with await liara_client(ctx) as c:
            dbs = await c.databases()
        keep = ("type", "planID", "status", "version")  # never credentials: the list carries root_password
        return Ok({"databases": [{"database": d.get("hostname"), "id": d.get("_id"), **{k: d.get(k) for k in keep}}
                                 for d in dbs]}, source="liara:/v1/databases")  # fmt: skip

    return await _guard(run())


def _db_match(key: str) -> Any:
    return lambda d: key in (d.get("_id"), d.get("hostname"), d.get("name"))


async def _find_db(c: LiaraClient, key: str) -> dict[str, Any] | None:
    return next((d for d in await c.databases() if _db_match(key)(d)), None)


@deployar_tool("delete_database", group="liara", risk="sensitive", description=fa.DELETE_DB_DESC,
               preview=lambda a: _danger("دیتابیس", str(a.get("database", "")), a.get("reason_fa")),
               input_schema={"type": "object", "required": ["database"], "properties": {
                   "database": {"type": "string"}, "reason_fa": {"type": "string"}}})  # fmt: skip
async def delete_database(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        key = str(args["database"])
        async with await liara_client(ctx) as c:
            db = await _find_db(c, key)
            if db is None:
                return ToolError("db_not_found", fa.DB_NOT_FOUND)
            await c.delete_database(str(db["_id"]))
            gone = await _gone(c.databases, _db_match(str(db["_id"])))
        out = {"database": key, "deleted": True, "verified_gone": gone,
               "was": {k: db.get(k) for k in ("type", "planID", "status")}}  # fmt: skip
        if not gone:
            out["note_fa"] = fa.DELETED_NOT_YET
        return Ok(out, source=f"liara:DELETE /v1/databases/{db['_id']} + GET /v1/databases")

    return await _guard(run())
