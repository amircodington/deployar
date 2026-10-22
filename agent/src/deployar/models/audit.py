import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Identity
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from deployar.models.base import Base, id_pk, now_default, pg_enum


class AuditLog(Base):
    """Read-only from Python: rows are written only by the SQL function audit_append()."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    occurred_at: Mapped[datetime] = now_default()
    actor_type: Mapped[str] = mapped_column(pg_enum("actor_type"))
    actor_user_id: Mapped[uuid.UUID | None]
    project_id: Mapped[uuid.UUID | None]
    action: Mapped[str]
    target_type: Mapped[str | None]
    target_id: Mapped[uuid.UUID | None]
    run_id: Mapped[uuid.UUID | None]
    tool_call_id: Mapped[uuid.UUID | None]
    approval_id: Mapped[uuid.UUID | None]
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None]
    data: Mapped[dict[str, Any]] = mapped_column(server_default="{}")
    prev_hash: Mapped[bytes]
    row_hash: Mapped[bytes]


class LimitationEvent(Base):
    __tablename__ = "limitation_event"

    id: Mapped[uuid.UUID] = id_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run.id", ondelete="SET NULL"))
    tool_call_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tool_call.id", ondelete="SET NULL"))
    capability: Mapped[str]
    kind: Mapped[str] = mapped_column(pg_enum("limitation_kind"))
    message_fa: Mapped[str]
    guide_key: Mapped[str | None]
    acknowledged_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = now_default()
