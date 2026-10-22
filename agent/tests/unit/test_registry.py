"""Tool registry: records tool_call rows, redacts output, re-checks approvals inside the tool (B-05)."""

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import redis.asyncio as aioredis
from pgtest import REDIS_TEST, TEST_URL_STR, fresh_schema
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_approvals import SECRET, make_ctx, sql

from deployar.core.redact import register_secret
from deployar.runtime.approvals import ApprovalService
from deployar.tools.registry import Registry, ToolContext
from deployar.tools.results import Limitation, Ok, ToolResult


@pytest.fixture(scope="module", autouse=True)
def schema() -> Iterator[None]:
    fresh_schema()
    yield


@pytest.fixture
async def sessions() -> AsyncIterator[async_sessionmaker[Any]]:
    engine = create_async_engine(TEST_URL_STR)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def fake_registry(calls: list[str]) -> Registry:
    reg = Registry()

    @reg.tool("get_logs", group="liara", risk="read", description="fake logs", input_schema={"since": str})
    async def get_logs(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        calls.append("get_logs")
        if args["since"] == "never":
            return Limitation("log_retention_over_7d", "لاگ قدیمی‌تر از ۷ روز در دسترس نیست.")
        return Ok(
            {"lines": ["boot ok", "DATABASE_URL=postgres://app:hunter2@db:5432/x", "token liara-secret-abcdef12"]},
            source="liara:logs",
        )

    @reg.tool("restart_app", group="liara", risk="sensitive", description="fake restart", input_schema={"project": str})
    async def restart_app(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        calls.append("restart_app")
        return Ok({"restarted": args["project"]}, source="liara:restart")

    return reg


async def tool_ctx(sessions: async_sessionmaker[Any]) -> ToolContext:
    c = await make_ctx()
    return ToolContext(run_id=c.run, project_id=c.project, user_id=c.user, sessions=sessions)


def text_of(result: dict[str, Any]) -> str:
    return "".join(block["text"] for block in result["content"])


async def test_secret_looking_output_is_redacted_before_the_model(sessions: async_sessionmaker[Any]) -> None:
    register_secret("liara-secret-abcdef12")  # as the vault does on decrypt
    calls: list[str] = []
    ctx = await tool_ctx(sessions)
    result = await fake_registry(calls).run(ctx, "get_logs", {"since": "1h"})
    out = text_of(result)
    assert "hunter2" not in out and "liara-secret-abcdef12" not in out
    assert "boot ok" in out and json.loads(out)["source"] == "liara:logs"
    row = await sql("select status::text || ':' || coalesce(result_summary::text, '') from tool_call where run_id = $1",
                    ctx.run_id)  # fmt: skip
    assert str(row).startswith("succeeded:") and "hunter2" not in str(row)


async def test_sensitive_tool_called_directly_refuses(sessions: async_sessionmaker[Any]) -> None:
    calls: list[str] = []
    ctx = await tool_ctx(sessions)
    result = await fake_registry(calls).run(ctx, "restart_app", {"project": "p"})
    assert result["is_error"] is True
    assert json.loads(text_of(result))["code"] == "approval_missing"
    assert calls == []  # the tool body never ran
    assert await sql("select count(*) from tool_call where run_id = $1 and status = 'running'", ctx.run_id) == 0


async def test_sensitive_tool_runs_with_an_approved_approval(sessions: async_sessionmaker[Any]) -> None:
    calls: list[str] = []
    ctx = await tool_ctx(sessions)
    r = aioredis.from_url(REDIS_TEST)
    service = ApprovalService(sessions, r, SECRET)
    args = {"project": "p"}
    created = await service.create(ctx.run_id, ctx.project_id, ctx.user_id, "restart_app", args, {})
    await service.decide(created.approval_id, ctx.user_id, "approve", created.token)
    result = await fake_registry(calls).run(ctx, "restart_app", args)
    await r.aclose()
    assert result.get("is_error") is not True and calls == ["restart_app"]
    assert await sql("select status::text from tool_call where id = $1", created.tool_call_id) == "succeeded"
    assert await sql("select status::text from approval where id = $1", created.approval_id) == "executed"
    # the same approval cannot release a second call
    again = await fake_registry(calls).run(ctx, "restart_app", args)
    assert again["is_error"] is True and calls == ["restart_app"]


async def test_limitation_writes_the_event(sessions: async_sessionmaker[Any]) -> None:
    ctx = await tool_ctx(sessions)
    result = await fake_registry([]).run(ctx, "get_logs", {"since": "never"})
    body = json.loads(text_of(result))
    assert body["status"] == "limitation" and body["code"] == "log_retention_over_7d"
    assert await sql("select capability from limitation_event where run_id = $1", ctx.run_id) == "log_retention_over_7d"
    assert await sql("select status::text from tool_call where run_id = $1", ctx.run_id) == "limitation"


async def test_sdk_server_exposes_the_tools(sessions: async_sessionmaker[Any]) -> None:
    ctx = await tool_ctx(sessions)
    reg = fake_registry([])
    server = reg.sdk_server(ctx)
    assert server["name"] == "deployar"
    assert reg.risk_of("restart_app") == "sensitive" and reg.risk_of("nope") is None
    assert reg.allowed_tools() == ["mcp__deployar__get_logs"]  # read tools only (B-00 finding)


def test_registry_rejects_bad_definitions() -> None:
    reg = Registry()

    async def f(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        return Ok({})

    reg.tool("get_logs", group="liara", risk="read", description="x", input_schema={})(f)
    with pytest.raises(ValueError):
        reg.tool("get_logs", group="liara", risk="read", description="x", input_schema={})(f)
    with pytest.raises(ValueError):
        reg.tool("get_balance", group="liara", risk="risky", description="x", input_schema={})(f)  # type: ignore[arg-type]


def test_tool_context_ids_are_uuids() -> None:
    ctx = ToolContext(run_id=uuid.uuid4(), project_id=uuid.uuid4(), user_id=uuid.uuid4(), sessions=None)  # type: ignore[arg-type]
    assert isinstance(ctx.run_id, uuid.UUID)
