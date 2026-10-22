"""propose_plan (read): price the latest repo analysis on Liara plans, with the balance next to it."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update

from deployar import messages_fa as fa
from deployar.models import PlanProposal, RepoAnalysis
from deployar.runtime.plan import catalogue, choose, totals
from deployar.tools.liara.read import STATIC_PLANS, _guard, liara_client
from deployar.tools.registry import ToolContext, deployar_tool
from deployar.tools.results import Ok, ToolError, ToolResult


@deployar_tool("propose_plan", group="liara", risk="read", description=fa.PROPOSE_PLAN_DESC,
               input_schema={"type": "object", "properties": {}})  # fmt: skip
async def propose_plan(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if ctx.project_id is None:
        return ToolError("no_project", fa.NO_PROJECT)
    async with ctx.sessions() as s:
        analysis = await s.scalar(
            select(RepoAnalysis).where(RepoAnalysis.project_id == ctx.project_id)
            .order_by(RepoAnalysis.created_at.desc()).limit(1)
        )  # fmt: skip
    if analysis is None:
        return ToolError("no_analysis", fa.NO_ANALYSIS)

    async def run() -> ToolResult:
        async with await liara_client(ctx) as c:
            me = await c.me_summary()
            billing = await c.billing()
        fetched_at = datetime.now(UTC)
        plans, source = catalogue(STATIC_PLANS, me.get("plans"))
        db_plans, _ = catalogue(STATIC_PLANS, me.get("plans"), kind="databases")
        items = choose(analysis.detected, plans, db_plans)
        if not items:
            return ToolError("nothing_to_price", fa.WARN_NO_APP)
        balance = billing.get("balance")
        balance_toman = int(balance) if isinstance(balance, int | float) else None
        tot = totals(items, balance_toman)
        app0 = next(i for i in items if i["kind"] == "app")
        db = next((i for i in items if i["kind"] == "db"), None)
        reasoning = "؛ ".join(f"{i.get('root') or i.get('engine')}: {i['plan_name']} ({i['why']})" for i in items)
        async with ctx.sessions.begin() as s:
            await s.execute(
                update(PlanProposal)
                .where(PlanProposal.project_id == ctx.project_id, PlanProposal.status == "proposed")
                .values(status="superseded", decided_at=fetched_at)
            )
            proposal = PlanProposal(
                project_id=ctx.project_id, repo_analysis_id=analysis.id, run_id=ctx.run_id, items=items,
                app_plan_id=app0["plan_id"] or app0["plan_name"], app_price_monthly_rial=app0["toman_month"] * 10,
                db_plan_id=(db["plan_id"] or db["plan_name"]) if db else None,
                db_price_monthly_rial=db["toman_month"] * 10 if db else None,
                total_monthly_rial=tot["toman_month"] * 10, total_hourly_rial=tot["toman_hour"] * 10,
                balance_rial=balance_toman * 10 if balance_toman is not None else None, price_source=source,
                prices_fetched_at=fetched_at, reasoning_fa=reasoning,
            )  # fmt: skip
            s.add(proposal)
            await s.flush()
            proposal_id = proposal.id
        payload = {"proposal_id": str(proposal_id), "items": items, "totals": tot, "balance_toman": balance_toman,
                   "price_source": source, "prices_fetched_at": fetched_at.isoformat(),
                   "plan_ids_confirmed": all(i["plan_id"] for i in items),
                   "note_fa": None if source.startswith("liara:") else fa.PLANS_FROM_TABLE}  # fmt: skip
        return Ok(payload, source=source, card=("plan_proposal", payload))

    return await _guard(run())
