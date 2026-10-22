"""POST /api/approvals/{id}/decision — the only way a human releases a sensitive tool call."""

import base64
import uuid
from functools import lru_cache
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from deployar import messages_fa as fa
from deployar.core.config import get_settings
from deployar.core.db import get_sessionmaker
from deployar.core.errors import DeployarError
from deployar.models import User
from deployar.runtime.approvals import ApprovalService, Decision

router = APIRouter(prefix="/api/approvals")


class DecisionIn(BaseModel):
    decision: Decision
    signature: str
    note: str | None = None


class DecisionOut(BaseModel):
    status: str


@lru_cache
def get_approval_service() -> ApprovalService:
    s = get_settings()
    secret = base64.b64decode(s.approval_secret.get_secret_value())
    return ApprovalService(get_sessionmaker(), aioredis.from_url(s.redis_url), secret)  # type: ignore[no-untyped-call]


async def current_user_id() -> uuid.UUID:
    # shortcut: single-user MVP, the one seeded user; replace with the session cookie from POST /api/session (B-06).
    async with get_sessionmaker()() as s:
        user_id = await s.scalar(select(User.id).order_by(User.created_at).limit(1))
    if user_id is None:
        raise DeployarError("no_user", fa.NO_USER)
    return user_id


@router.post("/{approval_id}/decision")
async def decide(
    approval_id: uuid.UUID,
    body: DecisionIn,
    user_id: Annotated[uuid.UUID, Depends(current_user_id)],
    service: Annotated[ApprovalService, Depends(get_approval_service)],
) -> DecisionOut:
    return DecisionOut(status=await service.decide(approval_id, user_id, body.decision, body.signature, body.note))
