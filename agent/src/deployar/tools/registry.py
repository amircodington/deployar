"""Tool registry: one place that knows every tool's risk, and the wrapper every call goes through.

The wrapper writes the tool_call row, re-checks the approval for sensitive tools (second layer behind
can_use_tool; the DB trigger is the third), redacts the output before the model sees it, and turns a
Limitation into a limitation_event row.
"""

import json
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from claude_agent_sdk import McpSdkServerConfig, SdkMcpTool, create_sdk_mcp_server
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from deployar import messages_fa as fa
from deployar.core.ids import new_id
from deployar.core.redact import redact
from deployar.models import Approval, LimitationEvent, ToolCall
from deployar.runtime.approvals import args_hash
from deployar.tools.results import Limitation, Ok, ToolError, ToolResult, to_payload

Risk = Literal["read", "sensitive", "human_only"]
SERVER = "deployar"
PREFIX = f"mcp__{SERVER}__"


@dataclass(frozen=True)
class ToolContext:
    run_id: uuid.UUID
    project_id: uuid.UUID | None  # a chat run may start before any project exists
    user_id: uuid.UUID
    sessions: async_sessionmaker[AsyncSession]


ToolFn = Callable[[ToolContext, dict[str, Any]], Awaitable[ToolResult]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    group: str
    risk: Risk
    description: str
    input_schema: dict[str, Any]
    fn: ToolFn


class Registry:
    def __init__(self) -> None:
        self.specs: dict[str, ToolSpec] = {}

    def tool(
        self, name: str, *, group: str, risk: Risk, description: str, input_schema: dict[str, Any]
    ) -> Callable[[ToolFn], ToolFn]:
        if risk not in ("read", "sensitive", "human_only"):
            raise ValueError(f"{name}: unknown risk {risk!r}")  # a tool with no class fails to register

        def register(fn: ToolFn) -> ToolFn:
            if name in self.specs:
                raise ValueError(f"tool {name} is already registered")
            self.specs[name] = ToolSpec(name, group, risk, description, input_schema, fn)
            return fn

        return register

    def risk_of(self, name: str) -> str | None:
        spec = self.specs.get(name)
        return spec.risk if spec else None

    def allowed_tools(self) -> list[str]:
        """Read tools only: any sensitive tool here would skip can_use_tool (B-00 finding)."""
        return [PREFIX + s.name for s in self.specs.values() if s.risk == "read"]

    def sdk_server(self, ctx: ToolContext) -> McpSdkServerConfig:
        tools: list[SdkMcpTool[Any]] = []
        for spec in self.specs.values():

            async def handler(args: dict[str, Any], _name: str = spec.name) -> dict[str, Any]:
                return await self.run(ctx, _name, args)

            tools.append(SdkMcpTool(spec.name, spec.description, spec.input_schema, handler))
        return create_sdk_mcp_server(SERVER, tools=tools)

    async def run(self, ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
        spec = self.specs[name]
        if spec.risk == "human_only":
            # can_use_tool already denies these; reaching here means the gate was bypassed.
            result: ToolResult = Limitation(name, fa.GUIDES.get(name, fa.TOOL_NOT_ALLOWED), kind="human_only")
            await self._record(ctx, spec, args, None, result, 0)
            return _mcp(result)

        tool_call_id = await (
            self._release(ctx, spec, args) if spec.risk == "sensitive" else self._start(ctx, spec, args)
        )
        if tool_call_id is None:
            return _mcp(ToolError("approval_missing", fa.APPROVAL_MISSING))
        started = time.monotonic()
        try:
            result = await spec.fn(ctx, args)
        except Exception as e:  # a tool bug must not leave a row running or crash the agent loop
            result = ToolError("tool_crashed", fa.TOOL_CRASHED, retryable=False)
            await self._record(ctx, spec, args, tool_call_id, result, _ms(started), crash=repr(e))
            return _mcp(result)
        await self._record(ctx, spec, args, tool_call_id, result, _ms(started))
        return _mcp(result)

    async def _start(self, ctx: ToolContext, spec: ToolSpec, args: dict[str, Any]) -> uuid.UUID:
        tool_call_id = new_id()
        async with ctx.sessions.begin() as s:
            s.add(
                ToolCall(
                    id=tool_call_id, run_id=ctx.run_id, name=spec.name, risk_class=spec.risk, args=redact(args),
                    args_hash=args_hash(args), idempotency_key=f"{ctx.run_id}:{spec.name}:{tool_call_id}",
                    status="running", started_at=datetime.now(UTC),
                )
            )  # fmt: skip
        return tool_call_id

    async def _release(self, ctx: ToolContext, spec: ToolSpec, args: dict[str, Any]) -> uuid.UUID | None:
        """Second layer: run only if this run holds an approved, unused approval for exactly these args."""
        async with ctx.sessions.begin() as s:
            tool_call_id = await s.scalar(
                select(ToolCall.id)
                .join(Approval, Approval.tool_call_id == ToolCall.id)
                .where(
                    ToolCall.run_id == ctx.run_id,
                    ToolCall.name == spec.name,
                    ToolCall.args_hash == args_hash(args),
                    ToolCall.status == "awaiting_approval",
                    Approval.status == "approved",
                    Approval.args_hash == ToolCall.args_hash,
                )
                .order_by(ToolCall.created_at.desc())
                .limit(1)
                .with_for_update()
            )
            if tool_call_id is None:
                return None
            # The DB trigger checks the approval again on this transition.
            await s.execute(
                update(ToolCall).where(ToolCall.id == tool_call_id).values(status="running", started_at=func.now())
            )
        return tool_call_id

    async def _record(
        self,
        ctx: ToolContext,
        spec: ToolSpec,
        args: dict[str, Any],
        tool_call_id: uuid.UUID | None,
        result: ToolResult,
        duration_ms: int,
        crash: str | None = None,
    ) -> None:
        status = {Ok: "succeeded", Limitation: "limitation", ToolError: "failed"}[type(result)]
        summary = redact(_summary(result))
        async with ctx.sessions.begin() as s:
            if tool_call_id is None:  # human_only reached directly
                tool_call_id = new_id()
                s.add(
                    ToolCall(
                        id=tool_call_id, run_id=ctx.run_id, name=spec.name, risk_class=spec.risk, args=redact(args),
                        args_hash=args_hash(args), idempotency_key=f"{ctx.run_id}:{spec.name}:{tool_call_id}",
                        status="limitation", result_summary=summary,
                    )
                )  # fmt: skip
                await s.flush()
            else:
                error = redact({"code": result.code, "message_fa": result.message_fa, "detail": crash}) if isinstance(
                    result, ToolError
                ) else None  # fmt: skip
                await s.execute(
                    update(ToolCall)
                    .where(ToolCall.id == tool_call_id)
                    .values(status=status, result_summary=summary, error=error, duration_ms=duration_ms,
                            finished_at=func.now())
                )  # fmt: skip
                if spec.risk == "sensitive":
                    await s.execute(
                        update(Approval)
                        .where(Approval.tool_call_id == tool_call_id)
                        .values(status="executed" if isinstance(result, Ok) else "failed", executed_at=func.now())
                    )
            if isinstance(result, Limitation):
                s.add(
                    LimitationEvent(
                        user_id=ctx.user_id, project_id=ctx.project_id, run_id=ctx.run_id, tool_call_id=tool_call_id,
                        capability=result.code, kind=result.kind, message_fa=result.message_fa,
                        guide_key=spec.name if result.kind == "human_only" else None,
                    )
                )  # fmt: skip


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _summary(result: ToolResult) -> dict[str, Any]:
    """Small: status, source, size. Raw payloads stay out of the database (DATA-MODEL.md, tool_call)."""
    if isinstance(result, Ok):
        return {"status": "ok", "source": result.source, "bytes": len(json.dumps(result.data, default=str))}
    return {"status": to_payload(result)["status"], "code": result.code}


def _mcp(result: ToolResult) -> dict[str, Any]:
    payload = redact(to_payload(result))
    out: dict[str, Any] = {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, default=str)}]}
    if not isinstance(result, Ok):
        out["is_error"] = isinstance(result, ToolError)
    return out


REGISTRY = Registry()
deployar_tool = REGISTRY.tool
