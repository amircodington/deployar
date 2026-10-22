"""Runs: start from a chat message, read state (polling fallback), cancel."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import or_, select

from deployar import messages_fa as fa
from deployar.api.deps import get_runtime, require_user
from deployar.core.errors import DeployarError
from deployar.models import Conversation, Project, Run, RunStep
from deployar.runtime.orchestrator import Runtime, start_run

router = APIRouter(prefix="/api/runs")
User = Annotated[uuid.UUID, Depends(require_user)]
Rt = Annotated[Runtime, Depends(get_runtime)]


class RunIn(BaseModel):
    text: str
    mode: str = "chat"
    project_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None


class RunCreated(BaseModel):
    run_id: str
    conversation_id: str


async def owned_run(rt: Runtime, run_id: uuid.UUID, user_id: uuid.UUID) -> Run:
    async with rt.sessions() as s:
        run = await s.scalar(
            select(Run)
            .outerjoin(Conversation, Conversation.id == Run.conversation_id)
            .outerjoin(Project, Project.id == Run.project_id)
            .where(Run.id == run_id, or_(Conversation.user_id == user_id, Project.user_id == user_id))
        )
    if run is None:
        raise DeployarError("not_found", fa.NOT_FOUND, f"run {run_id}")
    return run


@router.post("")
async def create(body: RunIn, user_id: User, rt: Rt) -> RunCreated:
    if not body.text.strip():
        raise DeployarError("empty_message", fa.EMPTY_MESSAGE)
    run_id, conversation_id = await start_run(rt, user_id, body.text, body.mode, body.project_id, body.conversation_id)
    return RunCreated(run_id=str(run_id), conversation_id=str(conversation_id))


@router.get("/{run_id}")
async def get(run_id: uuid.UUID, user_id: User, rt: Rt) -> dict[str, Any]:
    run = await owned_run(rt, run_id, user_id)
    async with rt.sessions() as s:
        steps = (await s.scalars(select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.seq))).all()
    return {
        "id": str(run.id), "kind": run.kind, "status": run.status, "error": run.error,
        "conversation_id": str(run.conversation_id) if run.conversation_id else None,
        "steps": [{"id": str(st.id), "seq": st.seq, "key": st.key, "label_fa": st.label_fa, "status": st.status,
                   "detail_fa": st.detail_fa} for st in steps],
    }  # fmt: skip


@router.post("/{run_id}/cancel")
async def cancel(run_id: uuid.UUID, user_id: User, rt: Rt) -> dict[str, str]:
    await owned_run(rt, run_id, user_id)
    task = rt.tasks.get(run_id)
    if task:
        task.cancel()
    return {"status": "cancelling" if task else "not_running"}
