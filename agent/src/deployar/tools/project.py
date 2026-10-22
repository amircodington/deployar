"""The project a tool acts on: the run's own, which analyze_repo sets when a chat starts without one."""

import uuid

from sqlalchemy import select, update

from deployar.models import Conversation, LiaraConnection, Project, Run
from deployar.tools.registry import ToolContext


async def project_of(ctx: ToolContext) -> uuid.UUID | None:
    if ctx.project_id:
        return ctx.project_id
    async with ctx.sessions() as s:
        pid: uuid.UUID | None = await s.scalar(select(Run.project_id).where(Run.id == ctx.run_id))
    return pid


async def ensure_project(ctx: ToolContext, repo_full_name: str, default_branch: str) -> uuid.UUID | None:
    """Binds the run (and its conversation) to a draft project for this repo; None without a Liara connection."""
    if pid := await project_of(ctx):
        return pid
    async with ctx.sessions.begin() as s:
        conn = await s.scalar(
            select(LiaraConnection.id).where(LiaraConnection.user_id == ctx.user_id, LiaraConnection.status == "active")
        )
        if conn is None:
            return None
        pid = await s.scalar(
            select(Project.id)
            .where(Project.user_id == ctx.user_id, Project.repo_full_name == repo_full_name, Project.app_root == ".",
                   Project.archived_at.is_(None))
            .order_by(Project.created_at)
            .limit(1)
        )  # fmt: skip
        if pid is None:
            project = Project(user_id=ctx.user_id, liara_connection_id=conn, name=repo_full_name.split("/")[-1],
                              repo_full_name=repo_full_name, repo_default_branch=default_branch)  # fmt: skip
            s.add(project)
            await s.flush()
            pid = project.id
        await s.execute(update(Run).where(Run.id == ctx.run_id).values(project_id=pid))
        conv = await s.scalar(select(Run.conversation_id).where(Run.id == ctx.run_id))
        if conv:
            await s.execute(
                update(Conversation)
                .where(Conversation.id == conv, Conversation.project_id.is_(None))
                .values(project_id=pid)
            )
    return pid
