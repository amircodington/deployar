"""Connections: the Liara token is posted here directly (never via chat), checked, encrypted, stored."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from deployar import messages_fa as fa
from deployar.api.deps import get_runtime, require_user
from deployar.clients.liara import LiaraClient
from deployar.core.crypto import aad_for, get_vault
from deployar.core.errors import DeployarError
from deployar.core.ids import new_id
from deployar.models import LiaraConnection
from deployar.runtime.approvals import audit
from deployar.runtime.orchestrator import Runtime

router = APIRouter(prefix="/api/connections")


class LiaraIn(BaseModel):
    token: str = Field(min_length=20, max_length=4096)
    team_id: str | None = Field(default=None, max_length=64)


class LiaraOut(BaseModel):
    id: str
    token_last4: str
    team_id: str | None
    account: str | None
    verified_at: str


@router.post("/liara")
async def connect_liara(
    body: LiaraIn,
    user_id: Annotated[uuid.UUID, Depends(require_user)],
    rt: Annotated[Runtime, Depends(get_runtime)],
) -> LiaraOut:
    token, team_id = body.token.strip(), (body.team_id or "").strip() or None
    async with LiaraClient(token, team_id) as c:
        await c.billing()  # 401 → liara_unauthorized; the token is stored only after this succeeds
        account = (await c.me_summary()).get("email")
    conn_id, now = new_id(), datetime.now(UTC)
    blob, version = get_vault().encrypt(token, aad_for("liara_connection", conn_id, user_id))
    async with rt.sessions.begin() as s:
        # one active connection per user: the old one is revoked and its ciphertext wiped
        await s.execute(
            update(LiaraConnection)
            .where(LiaraConnection.user_id == user_id, LiaraConnection.status == "active")
            .values(status="revoked", revoked_at=now, token_ciphertext=b"")
        )
        s.add(LiaraConnection(id=conn_id, user_id=user_id, token_ciphertext=blob, key_version=version,
                              token_last4=token[-4:], team_id=team_id, liara_account_email=account,
                              last_verified_at=now))  # fmt: skip
        await s.flush()
        await audit(s, "user", "connection.created", user_id=user_id, target_type="liara_connection",
                    target_id=conn_id, data={"team": bool(team_id)})  # fmt: skip
    return LiaraOut(
        id=str(conn_id), token_last4=token[-4:], team_id=team_id, account=account, verified_at=now.isoformat()
    )


@router.get("/liara")
async def current_liara(
    user_id: Annotated[uuid.UUID, Depends(require_user)],
    rt: Annotated[Runtime, Depends(get_runtime)],
) -> LiaraOut:
    async with rt.sessions() as s:
        c = await s.scalar(
            select(LiaraConnection).where(LiaraConnection.user_id == user_id, LiaraConnection.status == "active")
        )
    if c is None:
        raise DeployarError("no_liara_connection", fa.NO_LIARA_CONNECTION)
    return LiaraOut(id=str(c.id), token_last4=c.token_last4, team_id=c.team_id, account=c.liara_account_email,
                    verified_at=(c.last_verified_at or c.created_at).isoformat())  # fmt: skip
