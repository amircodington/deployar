"""POST /api/session: single-user passphrase login (BUILD.md defaults) → httpOnly cookie."""

import hmac
import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import select

from deployar import messages_fa as fa
from deployar.api.deps import COOKIE, get_redis, require_user, session_key
from deployar.core.config import get_settings
from deployar.core.db import get_sessionmaker
from deployar.core.errors import DeployarError
from deployar.models import User

router = APIRouter(prefix="/api")
_TTL_S = 30 * 24 * 3600


class SessionIn(BaseModel):
    passphrase: str


class SessionOut(BaseModel):
    user_id: str


@router.post("/session")
async def login(body: SessionIn, response: Response) -> SessionOut:
    expected = get_settings().deployar_passphrase.get_secret_value()
    if not hmac.compare_digest(body.passphrase.encode(), expected.encode()):
        raise DeployarError("bad_passphrase", fa.BAD_PASSPHRASE)
    async with get_sessionmaker()() as s:
        user_id = await s.scalar(select(User.id).order_by(User.created_at).limit(1))
    if user_id is None:
        raise DeployarError("no_user", fa.NO_USER)
    token = secrets.token_urlsafe(32)
    redis = get_redis()
    await redis.hset(session_key(token), mapping={"user_id": str(user_id)})  # type: ignore[misc]
    await redis.expire(session_key(token), _TTL_S)
    response.set_cookie(COOKIE, token, max_age=_TTL_S, httponly=True, samesite="lax", path="/")
    return SessionOut(user_id=str(user_id))


@router.get("/session")
async def me(user_id: Annotated[uuid.UUID, Depends(require_user)]) -> SessionOut:
    return SessionOut(user_id=str(user_id))
