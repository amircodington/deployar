"""Saved chats: the list (all, or one app's), and one chat's turns so the page can reopen and continue it."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select

from deployar import messages_fa as fa
from deployar.api.deps import get_runtime, require_user
from deployar.core.errors import DeployarError
from deployar.models import Conversation, Message, Project, Run
from deployar.runtime.orchestrator import Runtime

router = APIRouter(prefix="/api/conversations")
User = Annotated[uuid.UUID, Depends(require_user)]
Rt = Annotated[Runtime, Depends(get_runtime)]


@router.get("")
async def list_(user_id: User, rt: Rt, app: str | None = None) -> dict[str, Any]:
    """Newest first. With ?app=<Liara app name>: only that app's chats, plus its project_id for a new one."""
    async with rt.sessions() as s:
        q = (
            select(Conversation, Project.liara_app_name)
            .outerjoin(Project, Project.id == Conversation.project_id)
            .where(Conversation.user_id == user_id, Conversation.archived_at.is_(None))
            .order_by(Conversation.last_message_at.desc())
            .limit(50)
        )
        project_id = None
        if app:
            project_id = await s.scalar(select(Project.id).where(
                Project.user_id == user_id, Project.liara_app_name == app, Project.archived_at.is_(None))
                .order_by(Project.updated_at.desc()).limit(1))  # fmt: skip
            q = q.where(Project.liara_app_name == app)
        rows = (await s.execute(q)).all()
    return {
        "project_id": str(project_id) if project_id else None,
        "items": [{"id": str(c.id), "title_fa": c.title_fa, "app": name,
                   "project_id": str(c.project_id) if c.project_id else None,
                   "last_message_at": c.last_message_at.isoformat()} for c, name in rows],
    }  # fmt: skip


@router.get("/{conversation_id}")
async def get(conversation_id: uuid.UUID, user_id: User, rt: Rt) -> dict[str, Any]:
    """Each turn: the user's text, its run (whose saved events replay the cards), and the answer text as a
    fallback once those events have expired."""
    async with rt.sessions() as s:
        conv = await s.scalar(
            select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        )
        if conv is None:
            raise DeployarError("not_found", fa.NOT_FOUND, f"conversation {conversation_id}")
        msgs = (await s.scalars(
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.seq))).all()  # fmt: skip
        runs = {r.triggered_by_message_id: r for r in (await s.scalars(
            select(Run).where(Run.conversation_id == conversation_id))).all()}  # fmt: skip
    turns: list[dict[str, Any]] = []
    for m in msgs:
        text = " ".join(p.get("text_fa", "") for p in m.content if isinstance(p, dict))
        if m.role == "user":
            run = runs.get(m.id)
            turns.append({"text": text, "run_id": str(run.id) if run else None,
                          "status": run.status if run else None, "answer": None})  # fmt: skip
        elif m.role == "assistant" and turns and turns[-1]["answer"] is None:
            turns[-1]["answer"] = text
    return {"id": str(conv.id), "title_fa": conv.title_fa,
            "project_id": str(conv.project_id) if conv.project_id else None, "turns": turns}  # fmt: skip
