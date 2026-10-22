"""can_use_tool: the code half of hard rule 1 (the DB trigger is the other half).

read → allow; human_only → deny with its guide (recorded as a limitation); sensitive → signed
approval, wait, revalidate; anything else (built-ins, other MCP servers, unknown names) → deny.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from claude_agent_sdk import PermissionResult, PermissionResultAllow, PermissionResultDeny, ToolPermissionContext

from deployar import messages_fa as fa
from deployar.core.ids import new_id
from deployar.core.redact import redact
from deployar.models import LimitationEvent, ToolCall
from deployar.runtime.approvals import ApprovalService, Created, args_hash

PREFIX = "mcp__deployar__"

RiskOf = Callable[[str], str | None]
CanUseTool = Callable[[str, dict[str, Any], ToolPermissionContext], Awaitable[PermissionResult]]


@dataclass(frozen=True)
class GateContext:
    run_id: uuid.UUID
    project_id: uuid.UUID | None
    user_id: uuid.UUID


async def _record_limitation(service: ApprovalService, ctx: GateContext, name: str, args: dict[str, Any]) -> None:
    async with service.sessions.begin() as s:
        tool_call_id = new_id()
        s.add(
            ToolCall(
                id=tool_call_id, run_id=ctx.run_id, name=name, risk_class="human_only", args=redact(args),
                args_hash=args_hash(args), idempotency_key=f"{ctx.run_id}:{name}:{tool_call_id}", status="limitation",
            )
        )  # fmt: skip
        await s.flush()
        s.add(
            LimitationEvent(
                user_id=ctx.user_id, project_id=ctx.project_id, run_id=ctx.run_id, tool_call_id=tool_call_id,
                capability=name, kind="human_only", message_fa=fa.GUIDES[name], guide_key=name,
            )
        )  # fmt: skip


def make_gate(
    service: ApprovalService,
    ctx: GateContext,
    risk_of: RiskOf,
    *,
    wait_s: float = 600,
    on_requested: Callable[[Created], Awaitable[None]] | None = None,
    preview_for: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
) -> CanUseTool:
    """One gate per run. `on_requested` pushes the approval card (event bus, B-06)."""

    async def gate(tool_name: str, args: dict[str, Any], _context: ToolPermissionContext) -> PermissionResult:
        name = tool_name.removeprefix(PREFIX) if tool_name.startswith(PREFIX) else None
        risk = risk_of(name) if name else None
        if name is None or risk is None:
            return PermissionResultDeny(message=fa.TOOL_NOT_ALLOWED)
        if risk == "read":
            return PermissionResultAllow()
        if risk == "human_only":
            await _record_limitation(service, ctx, name, args)
            return PermissionResultDeny(message=fa.GUIDES[name])
        if risk != "sensitive" or ctx.project_id is None:  # an approval always belongs to a project
            return PermissionResultDeny(message=fa.TOOL_NOT_ALLOWED)

        preview = preview_for(name, args) if preview_for else {"tool": name}
        created = await service.create(ctx.run_id, ctx.project_id, ctx.user_id, name, args, preview)
        if on_requested:
            await on_requested(created)
        status = await service.wait(created.approval_id, timeout_s=wait_s)
        if status == "approved" and await service.revalidate(created.approval_id, args):
            return PermissionResultAllow()
        if status == "approved":
            status = "invalidated"
        return PermissionResultDeny(message=fa.DENIED.get(status, fa.DENIED["cancelled"]))

    return gate
