"""POST /api/approvals/{id}/decision — the only way a human releases a sensitive tool call."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deployar.api.deps import get_runtime, require_user
from deployar.runtime.approvals import ApprovalService, Decision

router = APIRouter(prefix="/api/approvals")


class DecisionIn(BaseModel):
    decision: Decision
    signature: str
    note: str | None = None
    confirm: str | None = None  # the name the user typed, for cards that ask for it (irreversible deletes)


class DecisionOut(BaseModel):
    status: str


def get_approval_service() -> ApprovalService:
    return get_runtime().approvals


@router.post("/{approval_id}/decision")
async def decide(
    approval_id: uuid.UUID,
    body: DecisionIn,
    user_id: Annotated[uuid.UUID, Depends(require_user)],
    service: Annotated[ApprovalService, Depends(get_approval_service)],
) -> DecisionOut:
    status = await service.decide(approval_id, user_id, body.decision, body.signature, body.note, body.confirm)
    return DecisionOut(status=status)
