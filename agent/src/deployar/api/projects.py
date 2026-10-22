"""Values the user types for env vars go here, never into chat (ARCHITECTURE.md §9 value_refs)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from deployar import messages_fa as fa
from deployar.api.deps import get_runtime, require_user
from deployar.core.errors import DeployarError
from deployar.models import Project
from deployar.runtime.orchestrator import Runtime
from deployar.tools.registry import ToolContext
from deployar.tools.secrets import store_secret

router = APIRouter(prefix="/api/projects")


class EnvValueIn(BaseModel):
    key: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
    value: str = Field(min_length=1, max_length=8192)


@router.post("/{project_id}/env-values")
async def env_value(
    project_id: uuid.UUID,
    body: EnvValueIn,
    user_id: Annotated[uuid.UUID, Depends(require_user)],
    rt: Annotated[Runtime, Depends(get_runtime)],
) -> dict[str, str]:
    async with rt.sessions() as s:
        if await s.scalar(select(Project.id).where(Project.id == project_id, Project.user_id == user_id)) is None:
            raise DeployarError("not_found", fa.NOT_FOUND, f"project {project_id}")
    ctx = ToolContext(run_id=uuid.UUID(int=0), project_id=project_id, user_id=user_id, sessions=rt.sessions)
    ref = await store_secret(ctx, body.key, body.value, "user", project_id)
    return {"key": body.key, "value_ref": ref}
