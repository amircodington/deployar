"""SRE loop tools (B-16..B-19, lean): probe the site, show ranked causes, verify after the fix.

The first http_probe of a run is its "before"; verify_after_action measures again and shows both,
so a fix is never reported as done without numbers (hard rule 3).
"""

import asyncio
import statistics
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from deployar import messages_fa as fa
from deployar.clients.liara import LiaraNotFound
from deployar.tools.liara.deploy import _project
from deployar.tools.liara.read import _guard, liara_client
from deployar.tools.registry import ToolContext, deployar_tool
from deployar.tools.results import Ok, ToolError, ToolResult

# shortcut: process memory, so a before/after pair lives inside one run (approvals wait in-run); a restart of
# the agent loses it and verify then reports "no baseline". Upgrade to an incident table (B-16) if runs split.
BASELINE: dict[uuid.UUID, dict[str, Any]] = {}


async def _probe(url: str, n: int) -> dict[str, Any]:
    times: list[int] = []
    codes: dict[str, int] = {}
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as http:
        for _ in range(n):
            started = time.monotonic()
            try:
                r = await http.get(url)
                code = str(r.status_code)
            except httpx.HTTPError as e:
                code = type(e).__name__
            times.append(int((time.monotonic() - started) * 1000))
            codes[code] = codes.get(code, 0) + 1
    bad = sum(v for k, v in codes.items() if not k.isdigit() or int(k) >= 500)
    q = statistics.quantiles(times, n=20) if len(times) > 1 else times * 19
    return {"url": url, "n": n, "codes": codes, "error_rate": round(bad / n, 2),
            "p50_ms": int(statistics.median(times)), "p95_ms": int(q[18]),
            "observed_at": datetime.now(UTC).isoformat()}  # fmt: skip


async def _usage(ctx: ToolContext, app: str) -> dict[str, float | None]:
    """RAM (MB) and CPU (cores) right now, summed over applets; None when Liara gives no metrics."""
    try:
        async with await liara_client(ctx) as c:
            m = await c.metrics_summary(app)
    except LiaraNotFound:
        return {"memory_mb": None, "cpu": None}
    return {"memory_mb": round(_total(m.get("memoryUsage")) / 1_048_576), "cpu": round(_total(m.get("cpuUsage")), 2)}


def _total(rows: list[dict[str, Any]] | None) -> float:
    return sum(float((r.get("value") or [0, 0])[1]) for r in rows or [])


PROBE = {"type": "object", "properties": {"project_id": {"type": "string"}, "path": {"type": "string"},
                                          "n": {"type": "integer"}}}  # fmt: skip


@deployar_tool("http_probe", group="probe", risk="read", description=fa.HTTP_PROBE_DESC, input_schema=PROBE)
async def http_probe(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        p = await _project(ctx, args.get("project_id"))
        if not p.liara_app_name:
            return ToolError("app_not_created", fa.APP_NOT_CREATED)
        url = f"https://{p.liara_app_name}.liara.run/{str(args.get('path') or '').lstrip('/')}"
        probe = await _probe(url, max(1, min(int(args.get("n") or 5), 20)))
        snap = {**probe, **await _usage(ctx, p.liara_app_name), "app": p.liara_app_name}
        BASELINE.setdefault(ctx.run_id, snap)
        return Ok(snap, source=f"probe:{url}", observed_at=probe["observed_at"])

    return await _guard(run())


@deployar_tool("report_diagnosis", group="sre", risk="read", description=fa.DIAGNOSIS_DESC, input_schema={
    "type": "object", "required": ["symptom_fa", "hypotheses"], "properties": {
        "symptom_fa": {"type": "string"},
        "hypotheses": {"type": "array", "items": {"type": "object", "required": ["cause_fa", "likelihood"],
                                                  "properties": {
            "cause_fa": {"type": "string"}, "likelihood": {"type": "number"},
            "evidence": {"type": "array", "items": {"type": "string"}},
            "action_fa": {"type": "string"}, "action_tool": {"type": "string"}}}}}})  # fmt: skip
async def report_diagnosis(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    """The model's ranking, shown as a card; causes without evidence are kept but marked as guesses."""
    ranked = sorted(args.get("hypotheses") or [], key=lambda h: float(h.get("likelihood") or 0), reverse=True)[:5]
    for h in ranked:
        h["likelihood"] = max(0.0, min(1.0, float(h.get("likelihood") or 0)))
        h["evidence"] = [str(e)[:300] for e in h.get("evidence") or []][:4]
    if ctx.emit:
        await ctx.emit("diagnosis", {"symptom_fa": args.get("symptom_fa", ""), "hypotheses": ranked,
                                     "baseline": BASELINE.get(ctx.run_id)})  # fmt: skip
    return Ok({"ranked": [h["cause_fa"] for h in ranked]}, source="deployar:diagnosis")


@deployar_tool("verify_after_action", group="sre", risk="read", description=fa.VERIFY_DESC, input_schema={
    "type": "object", "properties": {"project_id": {"type": "string"}, "path": {"type": "string"},
                                     "wait_s": {"type": "integer"}}})  # fmt: skip
async def verify_after_action(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        before = BASELINE.get(ctx.run_id)
        if before is None:
            return ToolError("no_baseline", fa.NO_BASELINE)
        wait = args.get("wait_s")
        await asyncio.sleep(max(0, min(int(wait if wait is not None else 20), 120)))
        after = {**await _probe(before["url"], int(before["n"])), **await _usage(ctx, before["app"])}
        fixed = after["error_rate"] < before["error_rate"] or (
            after["error_rate"] == 0 and after["p50_ms"] <= before["p50_ms"] * 0.7
        )
        worse = after["error_rate"] > before["error_rate"]
        verdict = fa.VERIFIED_FIXED if fixed else fa.VERIFIED_WORSE if worse else fa.VERIFIED_SAME
        if ctx.emit:
            await ctx.emit("verify", {"before": before, "after": after, "fixed": fixed, "verdict_fa": verdict})
        return Ok({"before": before, "after": after, "fixed": fixed, "verdict_fa": verdict},
                  source=f"probe:{before['url']}", observed_at=after["observed_at"])  # fmt: skip

    return await _guard(run())
