"""can_use_tool gate: read passes, human_only never runs, sensitive waits for a signed decision (B-04)."""

import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
import redis.asyncio as aioredis
from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny, ToolPermissionContext
from pgtest import REDIS_TEST, TEST_URL_STR, fresh_schema
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_approvals import SECRET, make_ctx, sql

from deployar.runtime.approvals import ApprovalService, Created
from deployar.runtime.gate import GateContext, make_gate

RISK = {"get_logs": "read", "restart_app": "sensitive", "registrar_dns_records": "human_only"}
CTX = ToolPermissionContext(tool_use_id="tu_1")


@pytest.fixture(scope="module", autouse=True)
def schema() -> Iterator[None]:
    fresh_schema()
    yield


@pytest.fixture
async def service() -> AsyncIterator[ApprovalService]:
    engine = create_async_engine(TEST_URL_STR)
    r = aioredis.from_url(REDIS_TEST)
    yield ApprovalService(async_sessionmaker(engine, expire_on_commit=False), r, SECRET)
    await r.aclose()
    await engine.dispose()


async def gate_for(service: ApprovalService, wait_s: float = 5) -> tuple[object, GateContext, list[Created]]:
    c = await make_ctx()
    ctx = GateContext(run_id=c.run, project_id=c.project, user_id=c.user)
    requested: list[Created] = []

    async def on_requested(created: Created) -> None:
        requested.append(created)

    return make_gate(service, ctx, RISK.get, wait_s=wait_s, on_requested=on_requested), ctx, requested


async def first_request(requested: list[Created], pending: "asyncio.Task[object]") -> Created:
    for _ in range(250):
        if requested:
            return requested[0]
        if pending.done():
            pending.result()  # surfaces the gate's exception
            raise AssertionError("gate finished without requesting an approval")
        await asyncio.sleep(0.02)
    raise AssertionError("no approval requested within 5 s")


async def test_read_tool_passes_without_a_card(service: ApprovalService) -> None:
    gate, ctx, requested = await gate_for(service)
    assert isinstance(await gate("mcp__deployar__get_logs", {"since": "1h"}, CTX), PermissionResultAllow)
    assert requested == []
    assert await sql("select count(*) from approval where run_id = $1", ctx.run_id) == 0


async def test_unknown_and_builtin_tools_are_denied(service: ApprovalService) -> None:
    gate, _, _ = await gate_for(service)
    for name in ("Bash", "mcp__other__get_logs", "mcp__deployar__drop_database"):
        assert isinstance(await gate(name, {}, CTX), PermissionResultDeny)


async def test_human_only_is_always_denied_and_returns_its_guide(service: ApprovalService) -> None:
    gate, ctx, requested = await gate_for(service)
    result = await gate("mcp__deployar__registrar_dns_records", {"domain": "torobgard.ir"}, CTX)
    assert isinstance(result, PermissionResultDeny)
    assert "۱." in result.message  # the numbered Persian guide
    assert requested == []
    assert await sql("select status::text from tool_call where run_id = $1", ctx.run_id) == "limitation"
    assert await sql("select capability from limitation_event where run_id = $1", ctx.run_id) == "registrar_dns_records"


async def test_sensitive_waits_for_approve(service: ApprovalService) -> None:
    gate, ctx, requested = await gate_for(service)
    pending = asyncio.create_task(gate("mcp__deployar__restart_app", {"project": "p"}, CTX))
    created = await first_request(requested, pending)
    assert not pending.done()  # blocked until a human decides
    await service.decide(created.approval_id, ctx.user_id, "approve", created.token)
    assert isinstance(await asyncio.wait_for(pending, 5), PermissionResultAllow)


async def test_sensitive_denied_on_reject(service: ApprovalService) -> None:
    gate, ctx, requested = await gate_for(service)
    pending = asyncio.create_task(gate("mcp__deployar__restart_app", {"project": "p"}, CTX))
    created = await first_request(requested, pending)
    await service.decide(created.approval_id, ctx.user_id, "reject", created.token)
    result = await asyncio.wait_for(pending, 5)
    assert isinstance(result, PermissionResultDeny)
    assert await sql("select status::text from tool_call where id = $1", created.tool_call_id) == "rejected"


async def test_sensitive_without_decision_is_denied_and_never_runs(service: ApprovalService) -> None:
    gate, _, requested = await gate_for(service, wait_s=0.3)
    result = await gate("mcp__deployar__restart_app", {"project": "p"}, CTX)
    assert isinstance(result, PermissionResultDeny)
    created = requested[0]
    assert await sql("select status::text from approval where id = $1", created.approval_id) == "cancelled"
    assert await sql("select status::text from tool_call where id = $1", created.tool_call_id) == "expired"


async def test_gate_ids_are_uuids(service: ApprovalService) -> None:
    gate, _, requested = await gate_for(service, wait_s=0.1)
    await gate("mcp__deployar__restart_app", {"project": "p"}, CTX)
    assert isinstance(requested[0].approval_id, uuid.UUID)
