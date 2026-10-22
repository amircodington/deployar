"""Orchestrator: a user message becomes a run with a planned checklist, driven by the LLM.

Runs execute as asyncio tasks inside the agent process (the Claude login lives on the host; the arq
worker stays LLM-free, ADR 7). Everything the user sees goes through the event bus.
"""

import asyncio
import re
import uuid
from dataclasses import dataclass, field
from importlib import resources
from types import ModuleType
from typing import Any

from claude_agent_sdk import PermissionResult, ToolPermissionContext
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from deployar import messages_fa as fa
from deployar.core.errors import DeployarError
from deployar.core.ids import new_id
from deployar.llm.client import Done, LLMClient, TextDelta, ToolResult, ToolUse
from deployar.models import Approval, Conversation, Message, Project, Run, RunStep
from deployar.runtime.approvals import ApprovalService, Created
from deployar.runtime.events import EventBus
from deployar.runtime.gate import PREFIX, GateContext, make_gate
from deployar.runtime.modes import chat, deploy, incident
from deployar.tools.registry import Registry, ToolContext

MODES: dict[str, ModuleType] = {"chat": chat, "deploy": deploy, "sre": incident}
# a repo link or a "put it online" ask starts a deploy run, a symptom starts an incident; anything else is a chat
INCIDENT_HINT = re.compile(r"کند|خطا|ارور|۵۰۰|\b500\b|قطع|نمی‌آید|نمیاد|down|crash|error|slow|timeout|مشکل", re.I)
DEPLOY_HINT = re.compile(r"github\.com/|بالا بیاو?ر|آنلاین کن|دیپلوی|deploy|منتشر کن|بساز|ادامه بده", re.I)


@dataclass
class Runtime:
    sessions: async_sessionmaker[AsyncSession]
    bus: EventBus
    approvals: ApprovalService
    llm: LLMClient
    registry: Registry
    tasks: dict[uuid.UUID, "asyncio.Task[None]"] = field(default_factory=dict)


def _prompt(mode: ModuleType) -> str:
    return resources.files("deployar.runtime.prompts").joinpath(mode.PROMPT_FILE).read_text(encoding="utf-8")


async def start_run(
    rt: Runtime,
    user_id: uuid.UUID,
    text: str,
    mode: str | None = None,
    project_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    mode = mode or (
        "deploy" if "github.com/" in text or (DEPLOY_HINT.search(text) and not INCIDENT_HINT.search(text))
        else "sre" if INCIDENT_HINT.search(text)
        else "chat"
    )  # fmt: skip
    if mode not in MODES:
        raise DeployarError("unknown_mode", fa.UNKNOWN_MODE, mode)
    spec = MODES[mode]
    run_id = new_id()
    async with rt.sessions.begin() as s:
        if (
            project_id is not None
            and await s.scalar(select(Project.id).where(Project.id == project_id, Project.user_id == user_id)) is None
        ):
            raise DeployarError("not_found", fa.NOT_FOUND, f"project {project_id}")
        if conversation_id is None:
            conversation_id = new_id()
            s.add(Conversation(id=conversation_id, user_id=user_id, project_id=project_id, title_fa=text[:60]))
            await s.flush()
        else:
            conv = await s.scalar(
                select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
            )
            if conv is None:
                raise DeployarError("not_found", fa.NOT_FOUND, f"conversation {conversation_id}")
            project_id = project_id or conv.project_id  # a chat that analyzed a repo keeps working on it
        message_id = await _add_message(s, conversation_id, "user", text)
        s.add(Run(id=run_id, project_id=project_id, conversation_id=conversation_id,
                  triggered_by_message_id=message_id, kind=spec.MODE, trigger="user_message"))  # fmt: skip
        await s.flush()
        for seq, step in enumerate(spec.STEPS, 1):
            s.add(RunStep(run_id=run_id, seq=seq, key=step["key"], label_fa=step["label_fa"]))
    task = asyncio.create_task(_execute(rt, run_id, user_id, project_id, conversation_id, text, spec))
    rt.tasks[run_id] = task
    task.add_done_callback(lambda _t: rt.tasks.pop(run_id, None))
    return run_id, conversation_id


async def _add_message(s: AsyncSession, conversation_id: uuid.UUID, role: str, text: str, **extra: Any) -> uuid.UUID:
    seq = (await s.scalar(select(func.max(Message.seq)).where(Message.conversation_id == conversation_id)) or 0) + 1
    message_id = new_id()
    s.add(Message(id=message_id, conversation_id=conversation_id, seq=seq, role=role,
                  content=[{"type": "text", "text_fa": text}], **extra))  # fmt: skip
    await s.execute(update(Conversation).where(Conversation.id == conversation_id).values(last_message_at=func.now()))
    return message_id


async def _set_run(rt: Runtime, run_id: uuid.UUID, **values: Any) -> None:
    async with rt.sessions.begin() as s:
        await s.execute(update(Run).where(Run.id == run_id).values(**values))


async def _set_step(rt: Runtime, step: RunStep, status: str) -> None:
    times = {"started_at": func.now()} if status == "running" else {"finished_at": func.now()}
    async with rt.sessions.begin() as s:
        await s.execute(update(RunStep).where(RunStep.id == step.id).values(status=status, **times))


async def _advance(
    rt: Runtime, run_id: uuid.UUID, steps: list[RunStep], spec: ModuleType, current: RunStep, tool: str
) -> tuple[RunStep, dict[str, str]] | None:
    """Move the checklist to the step that owns this tool; steps never move backwards."""
    owner = next((i for i, st in enumerate(spec.STEPS) if tool in st.get("tools", ())), None)
    at = steps.index(current)
    if owner is None or owner <= at:
        return None
    for st in steps[at:owner]:
        await _set_step(rt, st, "done")
        await rt.bus.publish(run_id, "step.done", {"step_id": str(st.id), "key": st.key, "title_fa": st.label_fa})
    nxt = steps[owner]
    ref = {"step_id": str(nxt.id), "key": nxt.key, "title_fa": nxt.label_fa}
    await _set_step(rt, nxt, "running")
    await rt.bus.publish(run_id, "step.started", ref)
    return nxt, ref


async def _execute(
    rt: Runtime,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    project_id: uuid.UUID | None,
    conversation_id: uuid.UUID,
    text: str,
    spec: ModuleType,
) -> None:
    async with rt.sessions() as s:
        steps = list((await s.scalars(select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.seq))).all())
        resume = await s.scalar(select(Conversation.agent_session_id).where(Conversation.id == conversation_id))
    step = steps[0]
    step_ref = {"step_id": str(step.id), "key": step.key, "title_fa": step.label_fa}
    message_id = str(new_id())
    try:
        await _set_run(rt, run_id, status="running", started_at=func.now())
        await rt.bus.publish(run_id, "run.started", {
            "mode": spec.MODE, "steps": [{"key": st.key, "title_fa": st.label_fa} for st in steps],
        })  # fmt: skip
        await _set_step(rt, step, "running")
        await rt.bus.publish(run_id, "step.started", step_ref)

        last: dict[str, Created] = {}

        async def on_requested(created: Created) -> None:
            last["created"] = created
            async with rt.sessions() as s:
                preview = await s.scalar(select(Approval.preview).where(Approval.id == created.approval_id)) or {}
            await _set_run(rt, run_id, status="awaiting_approval")
            await rt.bus.publish(run_id, "run.status", {"status": "awaiting_approval"})
            await rt.bus.publish(run_id, "approval.requested", {
                "approval_id": str(created.approval_id), "tool": preview.get("tool", ""),
                "summary_fa": preview.get("title_fa") or preview.get("tool", ""), "why_fa": preview.get("why_fa"),
                "cost_delta_toman": preview.get("cost_delta_toman"), "cost_source": preview.get("cost_source"),
                "changes": preview.get("changes"),
                "expires_at": created.expires_at.isoformat(), "signature": created.token,
            })  # fmt: skip

        gate = make_gate(rt.approvals, GateContext(run_id, project_id, user_id), rt.registry.risk_of,
                         on_requested=on_requested, preview_for=rt.registry.preview_of)  # fmt: skip

        async def can_use_tool(name: str, args: dict[str, Any], ctx: ToolPermissionContext) -> PermissionResult:
            last.clear()
            result = await gate(name, args, ctx)
            short = name.removeprefix(PREFIX)
            if rt.registry.risk_of(short) == "human_only":  # denied by the gate; the user gets the steps as a card
                await rt.bus.publish(run_id, "card", {"card_type": "human_only", "payload": {
                    "task": short, "steps_fa": fa.HUMAN_STEPS.get(short, []), "records": args.get("records"),
                    "check_fa": fa.CHECK_AGAIN.get(short, "").format(domain=args.get("domain", ""))}})  # fmt: skip
            if created := last.get("created"):
                async with rt.sessions() as s:
                    status = await s.scalar(select(Approval.status).where(Approval.id == created.approval_id))
                await rt.bus.publish(run_id, "approval.resolved", {
                    "approval_id": str(created.approval_id), "status": status,
                    "reason_fa": getattr(result, "message", None),
                })  # fmt: skip
                await _set_run(rt, run_id, status="running")
                await rt.bus.publish(run_id, "run.status", {"status": "running"})
            return result

        tool_names: dict[str, str] = {}
        parts: list[str] = []
        done: Done | None = None

        async def emit(card_type: str, payload: dict[str, Any]) -> None:
            await rt.bus.publish(run_id, "card", {"card_type": card_type, "payload": payload})

        tool_ctx = ToolContext(run_id, project_id, user_id, rt.sessions, emit)
        async for ev in rt.llm.run(prompt=text, system_prompt=_prompt(spec), registry=rt.registry,
                                   tool_ctx=tool_ctx, can_use_tool=can_use_tool, max_turns=spec.MAX_TURNS,
                                   resume=resume):  # fmt: skip
            if isinstance(ev, TextDelta):
                parts.append(ev.text)
                await rt.bus.publish(run_id, "message.delta", {"message_id": message_id, "text": ev.text})
            elif isinstance(ev, ToolUse):
                name = ev.name.removeprefix(PREFIX)
                tool_names[ev.id] = name
                step, step_ref = await _advance(rt, run_id, steps, spec, step, name) or (step, step_ref)
                await rt.bus.publish(run_id, "tool.called",
                                     {"name": name, "risk": rt.registry.risk_of(name), "status": "called"})  # fmt: skip
            elif isinstance(ev, ToolResult):
                name = tool_names.get(ev.tool_use_id, "unknown")
                status = ev.status if ev.status in ("ok", "limitation", "error") else "error"
                await rt.bus.publish(run_id, "tool.result",
                                     {"name": name, "risk": rt.registry.risk_of(name), "status": status})  # fmt: skip
            elif isinstance(ev, Done):
                done = ev

        answer = "\n\n".join(parts)
        async with rt.sessions.begin() as s:
            await _add_message(s, conversation_id, "assistant", answer, model=done.model if done else None)
            if done and done.session_id:
                await s.execute(update(Conversation).where(Conversation.id == conversation_id)
                                .values(agent_session_id=done.session_id))  # fmt: skip
        await rt.bus.publish(run_id, "message.done", {"message_id": message_id, "text": answer})
        if done is None or done.is_error:
            raise DeployarError("llm_failed", fa.LLM_FAILED, (done.error or "") if done else "no result")
        await _set_step(rt, step, "done")
        await rt.bus.publish(run_id, "step.done", step_ref)
        for later in steps[steps.index(step) + 1 :]:  # not reached this run (e.g. waiting for the user's yes)
            await _set_step(rt, later, "skipped")
        await _set_run(rt, run_id, status="succeeded", finished_at=func.now())
        await rt.bus.publish(run_id, "run.done", {"status": "succeeded"})
    except asyncio.CancelledError:
        await _set_run(rt, run_id, status="cancelled", finished_at=func.now())
        await rt.bus.publish(run_id, "run.done", {"status": "cancelled", "summary_fa": fa.RUN_CANCELLED})
        raise
    except Exception as e:
        err = e if isinstance(e, DeployarError) else DeployarError("run_crashed", fa.RUN_CRASHED, repr(e))
        await _set_step(rt, step, "failed")
        await rt.bus.publish(
            run_id, "step.failed", {**step_ref, "error": {"code": err.code, "message_fa": err.message_fa}}
        )
        await _set_run(rt, run_id, status="failed", finished_at=func.now(),
                       error={"code": err.code, "message_fa": err.message_fa})  # fmt: skip
        await rt.bus.publish(run_id, "run.done", {"status": "failed", "summary_fa": err.message_fa})
