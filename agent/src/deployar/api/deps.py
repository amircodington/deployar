"""Shared FastAPI dependencies: the process-wide runtime and the signed-in user."""

import base64
import hashlib
import uuid
from functools import lru_cache
from typing import cast

import redis.asyncio as aioredis
from fastapi import Request

from deployar import messages_fa as fa
from deployar.core.config import get_settings
from deployar.core.db import get_sessionmaker
from deployar.core.errors import DeployarError
from deployar.llm.claude_backend import ClaudeBackend
from deployar.llm.fake_backend import FakeBackend, demo_registry
from deployar.runtime.approvals import ApprovalService
from deployar.runtime.events import EventBus
from deployar.runtime.orchestrator import Runtime
from deployar.tools.github import analyze as _github_analyze  # noqa: F401  registers analyze_repo
from deployar.tools.liara import read as _liara_read  # noqa: F401  registers the Liara read tools
from deployar.tools.registry import REGISTRY

COOKIE = "deployar_session"


@lru_cache
def get_redis() -> aioredis.Redis:
    return cast(aioredis.Redis, aioredis.from_url(get_settings().redis_url))  # type: ignore[no-untyped-call]


@lru_cache
def get_runtime() -> Runtime:
    s = get_settings()
    sessions = get_sessionmaker()
    approvals = ApprovalService(sessions, get_redis(), base64.b64decode(s.approval_secret.get_secret_value()))
    if s.llm_backend == "fake":
        return Runtime(sessions, EventBus(get_redis()), approvals, FakeBackend(delay_s=0.8), demo_registry())
    return Runtime(sessions, EventBus(get_redis()), approvals, ClaudeBackend(), REGISTRY)


def session_key(token: str) -> str:
    return f"auth:sess:{hashlib.sha256(token.encode()).hexdigest()}"


async def require_user(request: Request) -> uuid.UUID:
    token = request.cookies.get(COOKIE)
    if token:
        user_id = await get_redis().hget(session_key(token), "user_id")  # type: ignore[misc]
        if user_id:
            return uuid.UUID(user_id.decode() if isinstance(user_id, bytes) else user_id)
    raise DeployarError("unauthorized", fa.UNAUTHORIZED)
