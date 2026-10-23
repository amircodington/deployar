"""Run event bus: one Redis stream per run, replayable with Last-Event-ID (ADR 10).

Every payload is validated against its pydantic model before it is written, so the web can trust
the shapes in ARCHITECTURE.md §8.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

import redis.asyncio as aioredis
from pydantic import BaseModel, ConfigDict


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StepRef(_M):
    key: str
    title_fa: str


class RunStarted(_M):
    mode: str
    steps: list[StepRef]


class RunStatus(_M):
    status: str


class ErrorInfo(_M):
    code: str
    message_fa: str


class StepEvent(_M):
    step_id: str
    key: str
    title_fa: str
    duration_ms: int | None = None
    error: ErrorInfo | None = None


class StepProgress(_M):
    step_id: str
    text: str
    log_tail: list[str] = []


class MessageText(_M):
    message_id: str
    text: str


class ToolEvent(_M):
    tool_call_id: str | None = None
    name: str
    risk: str | None = None
    status: Literal["called", "ok", "limitation", "error"]


class Card(_M):
    card_type: str
    payload: dict[str, Any]


class ApprovalRequested(_M):
    approval_id: str
    tool: str
    summary_fa: str
    why_fa: str | None = None
    cost_delta_toman: int | None = None
    cost_source: dict[str, Any] | None = None
    changes: dict[str, Any] | None = None
    diff_url: str | None = None
    expires_at: str
    signature: str


class ApprovalResolved(_M):
    approval_id: str
    status: Literal["approved", "rejected", "expired", "invalidated", "cancelled"]
    reason_fa: str | None = None


class RunDone(_M):
    status: Literal["succeeded", "failed", "cancelled"]
    summary_fa: str | None = None


EVENT_MODELS: dict[str, type[_M]] = {
    "run.started": RunStarted,
    "run.status": RunStatus,
    "step.started": StepEvent,
    "step.done": StepEvent,
    "step.failed": StepEvent,
    "step.progress": StepProgress,
    "message.delta": MessageText,
    "message.done": MessageText,
    "tool.called": ToolEvent,
    "tool.result": ToolEvent,
    "card": Card,
    "approval.requested": ApprovalRequested,
    "approval.resolved": ApprovalResolved,
    "run.done": RunDone,
}


class Envelope(_M):
    run_id: str
    seq: int
    ts: str
    type: str
    data: dict[str, Any]


_TTL_S = 30 * 24 * 3600  # a reopened chat replays its cards from here (conversations API)
_MAXLEN = 1000


def stream_key(run_id: uuid.UUID) -> str:
    return f"stream:run:{run_id}"


class EventBus:
    def __init__(self, redis: aioredis.Redis) -> None:
        self.redis = redis

    async def publish(self, run_id: uuid.UUID, type_: str, data: dict[str, Any]) -> str:
        validated = EVENT_MODELS[type_].model_validate(data).model_dump(mode="json", exclude_none=True)
        key = stream_key(run_id)
        seq = await self.redis.incr(f"{key}:seq")
        env = Envelope(run_id=str(run_id), seq=seq, ts=datetime.now(UTC).isoformat(), type=type_, data=validated)
        entry_id = await self.redis.xadd(key, {"e": env.model_dump_json()}, maxlen=_MAXLEN, approximate=True)
        await self.redis.expire(key, _TTL_S)
        await self.redis.expire(f"{key}:seq", _TTL_S)
        return entry_id.decode() if isinstance(entry_id, bytes) else str(entry_id)

    async def read(self, run_id: uuid.UUID, after: str = "0", block_ms: int = 15000) -> list[tuple[str, Envelope]]:
        """Entries after `after` (a stream id; "0" = from the start)."""
        rows = await self.redis.xread({stream_key(run_id): after}, block=block_ms, count=100)
        out: list[tuple[str, Envelope]] = []
        for _key, entries in rows or []:
            for entry_id, fields in entries:
                raw = fields.get(b"e") or fields.get("e")
                eid = entry_id.decode() if isinstance(entry_id, bytes) else str(entry_id)
                out.append((eid, Envelope.model_validate(json.loads(raw))))
        return out
