"""Domain (B-14) and the two steps only the user can do: top-up and the registrar's DNS panel.

add_domain asks Liara for the domain and returns the record the user must set; registrar_dns_records
and top_up_balance are human_only, so the gate denies them and the UI shows their steps as a card.
"""

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update

from deployar import messages_fa as fa
from deployar.models import Domain
from deployar.tools.liara.deploy import _project
from deployar.tools.liara.read import _guard, liara_client
from deployar.tools.registry import ToolContext, deployar_tool
from deployar.tools.results import Ok, ToolError, ToolResult

HOST = re.compile(r"^([a-z0-9-]+\.)+[a-z]{2,}$")


def _records(domain: str, cname: str | None) -> list[dict[str, str]]:
    target = cname or "—"
    # a subdomain takes a CNAME; an apex domain can't, so the user's DNS host needs ALIAS/ANAME (or Liara DNS)
    kind = "CNAME" if domain.count(".") >= 2 else "ALIAS/ANAME"
    return [{"type": kind, "name": domain, "value": target}]


@deployar_tool("add_domain", group="liara", risk="sensitive", description=fa.ADD_DOMAIN_DESC,
               preview=lambda a: {"title_fa": f"اتصال دامنه‌ی {a.get('domain')} به اپ",
                                  "why_fa": a.get("reason_fa")},
               input_schema={"type": "object", "required": ["domain"], "properties": {
                   "domain": {"type": "string"}, "project_id": {"type": "string"},
                   "reason_fa": {"type": "string"}}})  # fmt: skip
async def add_domain(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        domain = str(args["domain"]).strip().lower().removeprefix("https://").removeprefix("http://").strip("/")
        if not HOST.match(domain):
            return ToolError("bad_domain", fa.BAD_DOMAIN)
        p = await _project(ctx, args.get("project_id"))
        if not p.liara_app_name:
            return ToolError("app_not_created", fa.APP_NOT_CREATED)
        async with await liara_client(ctx) as c:
            domain_id = await c.add_domain(domain, p.liara_app_name)
            check = await c.check_domain(domain_id) if domain_id else {}
        records = _records(domain, check.get("CNameRecord"))
        async with ctx.sessions.begin() as s:
            s.add(Domain(project_id=p.id, hostname=domain, liara_domain_id=domain_id, required_records=records,
                         last_check=check, last_checked_at=datetime.now(UTC)))  # fmt: skip
        return Ok({"domain": domain, "records": records, "status": check.get("status"),
                   "next": "registrar_dns_records"}, source="liara:POST /v1/domains")  # fmt: skip

    return await _guard(run())


@deployar_tool("check_dns", group="liara", risk="read", description=fa.CHECK_DNS_DESC, input_schema={
    "type": "object", "required": ["domain"], "properties": {"domain": {"type": "string"}}})  # fmt: skip
async def check_dns(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        domain = str(args["domain"]).strip().lower()
        async with ctx.sessions() as s:
            row = await s.scalar(select(Domain).where(Domain.hostname == domain).order_by(Domain.created_at.desc()))
        if row is None or not row.liara_domain_id:
            return ToolError("domain_unknown", fa.DOMAIN_UNKNOWN)
        async with await liara_client(ctx) as c:
            check = await c.check_domain(row.liara_domain_id)
        ok = str(check.get("status", "")).upper() in ("OK", "ACTIVE", "VERIFIED", "CONNECTED")
        now = datetime.now(UTC)
        async with ctx.sessions.begin() as s:
            await s.execute(update(Domain).where(Domain.id == row.id).values(
                last_check=check, last_checked_at=now, status="active" if ok else "pending_dns",
                verified_at=now if ok else None))  # fmt: skip
        return Ok({"domain": domain, "connected": ok, "status": check.get("status"),
                   "certificate": check.get("certificatesStatus"), "records": row.required_records},
                  source=f"liara:/v1/domains/{row.liara_domain_id}/check", observed_at=now.isoformat())  # fmt: skip

    return await _guard(run())


async def _never(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    raise AssertionError("human_only tools never run")  # the gate and the registry both refuse them


deployar_tool("top_up_balance", group="liara", risk="human_only", description=fa.TOP_UP_DESC, input_schema={
    "type": "object", "properties": {"amount_toman": {"type": "integer"}}})(_never)  # fmt: skip
deployar_tool("registrar_dns_records", group="liara", risk="human_only", description=fa.REGISTRAR_DESC, input_schema={
    "type": "object", "required": ["domain"], "properties": {"domain": {"type": "string"}, "records": {
        "type": "array", "items": {"type": "object"}}}})(_never)  # fmt: skip
