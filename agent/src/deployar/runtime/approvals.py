"""Approval service: signed, one-time, 10-minute decisions (ARCHITECTURE.md §6.1, ADR 4–5).

Postgres is the truth; Redis only wakes the waiting gate early. The token on the card is
base64url(approval_id).base64url(HMAC-SHA256(APPROVAL_SECRET, id|tool_call_id|args_hash|user_id|expires_at)).
"""

import asyncio
import base64
import binascii
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import redis.asyncio as aioredis
from redis.exceptions import RedisError
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from deployar import messages_fa as fa
from deployar.core.errors import DeployarError
from deployar.core.ids import new_id
from deployar.core.redact import redact
from deployar.models import Approval, ToolCall

TTL = timedelta(minutes=10)
_DECISION_KEY_TTL_S = 15 * 60
_POLL_S = 1.0
# what a closed approval means for its tool call (tool_call_status has no cancelled/invalidated)
_CALL_STATUS = {"rejected": "rejected", "expired": "expired", "cancelled": "expired", "invalidated": "expired"}

Decision = Literal["approve", "reject"]


def args_hash(args: dict[str, Any]) -> bytes:
    canonical = json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).digest()


def decision_key(approval_id: uuid.UUID) -> str:
    return f"approval:{approval_id}:decision"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


@dataclass(frozen=True)
class Created:
    approval_id: uuid.UUID
    tool_call_id: uuid.UUID
    token: str
    expires_at: datetime


async def audit(session: AsyncSession, actor: str, action: str, **fields: Any) -> None:
    """Append to the hash-chained audit_log in the caller's transaction."""
    data = json.dumps(fields.pop("data", {}), ensure_ascii=False)
    await session.execute(
        text(
            "select audit_append(cast(:actor as actor_type), :action, p_actor_user_id => :user_id, "
            "p_project_id => :project_id, p_target_type => :target_type, p_target_id => :target_id, "
            "p_run_id => :run_id, p_tool_call_id => :tool_call_id, p_approval_id => :approval_id, "
            "p_data => cast(:data as jsonb))"
        ),
        {
            "actor": actor, "action": action, "data": data,
            **{k: fields.get(k) for k in (
                "user_id", "project_id", "target_type", "target_id", "run_id", "tool_call_id", "approval_id"
            )},
        },
    )  # fmt: skip


class ApprovalService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], redis: aioredis.Redis, secret: bytes) -> None:
        self.sessions = sessions
        self.redis = redis
        self._secret = secret

    def _sign(
        self, approval_id: uuid.UUID, tool_call_id: uuid.UUID, h: bytes, user_id: uuid.UUID, expires_at: datetime
    ) -> bytes:
        stamp = expires_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        msg = f"{approval_id}|{tool_call_id}|{h.hex()}|{user_id}|{stamp}"
        return hmac.new(self._secret, msg.encode(), hashlib.sha256).digest()

    async def create(
        self,
        run_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        tool_name: str,
        args: dict[str, Any],
        preview: dict[str, Any],
    ) -> Created:
        """Record the sensitive call as awaiting approval and issue its signed approval."""
        h = args_hash(args)
        now = datetime.now(UTC)
        expires_at = now + TTL
        tool_call_id, approval_id = new_id(), new_id()
        signature = self._sign(approval_id, tool_call_id, h, user_id, expires_at)
        async with self.sessions.begin() as s:
            # A retry after reject/expiry is a new call with a new approval (DATA-MODEL.md, approval.status).
            prefix = f"{run_id}:{tool_name}:{h.hex()[:16]}"
            tries = await s.scalar(
                select(func.count())
                .select_from(ToolCall)
                .where(ToolCall.idempotency_key.startswith(prefix, autoescape=True))
            )
            s.add(
                ToolCall(
                    id=tool_call_id, run_id=run_id, name=tool_name, risk_class="sensitive", args=redact(args),
                    args_hash=h, idempotency_key=f"{prefix}:{tries + 1}" if tries else prefix,
                    status="awaiting_approval",
                )
            )  # fmt: skip
            await s.flush()
            s.add(
                Approval(
                    id=approval_id, tool_call_id=tool_call_id, run_id=run_id, project_id=project_id,
                    user_id=user_id, preview=preview, args_hash=h, signature=signature,
                    expires_at=expires_at, created_at=now,
                )
            )  # fmt: skip
            await s.flush()
            await audit(
                s, "agent", "approval.requested", user_id=user_id, project_id=project_id, run_id=run_id,
                tool_call_id=tool_call_id, approval_id=approval_id, target_type="approval",
                target_id=approval_id, data={"tool": tool_name},
            )  # fmt: skip
        return Created(approval_id, tool_call_id, f"{_b64(approval_id.bytes)}.{_b64(signature)}", expires_at)

    def _token_ok(self, a: Approval, user_id: uuid.UUID, token: str) -> bool:
        try:
            id_part, sig_part = token.split(".")
            if _unb64(id_part) != a.id.bytes:
                return False
            given = _unb64(sig_part)
        except (ValueError, binascii.Error):
            return False
        # Recomputed with the caller's user_id, so another user's click fails like a forged one.
        return hmac.compare_digest(given, self._sign(a.id, a.tool_call_id, a.args_hash, user_id, a.expires_at))

    async def decide(
        self, approval_id: uuid.UUID, user_id: uuid.UUID, decision: Decision, token: str, reason: str | None = None
    ) -> str:
        status = {"approve": "approved", "reject": "rejected"}[decision]
        async with self.sessions.begin() as s:
            a = await s.get(Approval, approval_id)
            if a is None or not self._token_ok(a, user_id, token):
                raise DeployarError("approval_bad_signature", fa.APPROVAL_BAD_SIGNATURE, str(approval_id))
            # One-time use: only one request can win this conditional update.
            won = await s.scalar(
                update(Approval)
                .where(
                    Approval.id == approval_id,
                    Approval.user_id == user_id,
                    Approval.status == "pending",
                    Approval.expires_at > func.now(),
                )
                .values(status=status, decision=decision, decided_by=user_id, decided_at=func.now(),
                        reject_reason_fa=reason)
                .returning(Approval.tool_call_id)
            )  # fmt: skip
            if won is None:
                raise DeployarError("approval_not_pending", fa.APPROVAL_NOT_PENDING, str(approval_id))
            if status == "rejected":
                await s.execute(update(ToolCall).where(ToolCall.id == won).values(status="rejected"))
            await audit(
                s, "user", "approval.decided", user_id=user_id, project_id=a.project_id, run_id=a.run_id,
                tool_call_id=won, approval_id=approval_id, target_type="approval", target_id=approval_id,
                data={"decision": decision},
            )  # fmt: skip
        try:
            key = decision_key(approval_id)
            await self.redis.lpush(key, status)  # type: ignore[misc]  # redis-py stubs mix sync/async
            await self.redis.expire(key, _DECISION_KEY_TTL_S)
        except (RedisError, OSError):
            pass  # Postgres already has the decision; wait() falls back to reading it.
        return status

    async def _status(self, approval_id: uuid.UUID) -> tuple[str, bool]:
        async with self.sessions() as s:
            row = (
                await s.execute(
                    select(Approval.status, Approval.expires_at <= func.now()).where(Approval.id == approval_id)
                )
            ).one()
            return str(row[0]), bool(row[1])

    async def _close(self, approval_id: uuid.UUID, status: str, only_if: str) -> str:
        async with self.sessions.begin() as s:
            tool_call_id = await s.scalar(
                update(Approval)
                .where(Approval.id == approval_id, Approval.status == only_if)
                .values(status=status)
                .returning(Approval.tool_call_id)
            )
            if tool_call_id is not None:
                await s.execute(update(ToolCall).where(ToolCall.id == tool_call_id).values(status=_CALL_STATUS[status]))
        return (await self._status(approval_id))[0]

    async def wait(self, approval_id: uuid.UUID, timeout_s: float) -> str:
        """Block until decided or timed out; Postgres decides the answer, Redis only wakes us early."""
        deadline = time.monotonic() + timeout_s
        while True:
            status, expired = await self._status(approval_id)
            if status != "pending":
                return status
            if expired:
                return await self._close(approval_id, "expired", only_if="pending")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return await self._close(approval_id, "cancelled", only_if="pending")
            try:
                # Float timeout is valid on Redis >= 6; the stub says int, and int 0 would block forever.
                await self.redis.blpop([decision_key(approval_id)], timeout=min(remaining, _POLL_S))  # type: ignore[arg-type,misc]
            except (RedisError, OSError):
                await asyncio.sleep(min(remaining, _POLL_S))  # Redis down: keep polling Postgres

    async def revalidate(self, approval_id: uuid.UUID, args: dict[str, Any]) -> bool:
        """Right before execution: still approved and the args are the ones the user saw."""
        async with self.sessions() as s:
            a = await s.get(Approval, approval_id)
            if a is None or a.status != "approved":
                return False
            if hmac.compare_digest(a.args_hash, args_hash(args)):
                return True
        await self._close(approval_id, "invalidated", only_if="approved")
        return False
