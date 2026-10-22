import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from deployar.models.base import Base, id_pk, now_default, pg_enum


class Project(Base):
    __tablename__ = "project"

    id: Mapped[uuid.UUID] = id_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    liara_connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("liara_connection.id"))
    github_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("github_connection.id", ondelete="SET NULL")
    )
    name: Mapped[str]
    repo_full_name: Mapped[str | None]
    repo_default_branch: Mapped[str | None]
    liara_app_name: Mapped[str | None]
    platform: Mapped[str | None]
    plan_id: Mapped[str | None]
    liara_db_name: Mapped[str | None]
    db_kind: Mapped[str | None]
    live_url: Mapped[str | None]
    status: Mapped[str] = mapped_column(pg_enum("project_status"), server_default="draft")
    created_at: Mapped[datetime] = now_default()
    updated_at: Mapped[datetime] = now_default()
    archived_at: Mapped[datetime | None]
    current_deployment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("deployment.id", ondelete="SET NULL", use_alter=True)
    )
    app_root: Mapped[str] = mapped_column(server_default=".")


class Conversation(Base):
    __tablename__ = "conversation"

    id: Mapped[uuid.UUID] = id_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("project.id", ondelete="SET NULL"))
    title_fa: Mapped[str | None]
    agent_session_id: Mapped[str | None]
    created_at: Mapped[datetime] = now_default()
    last_message_at: Mapped[datetime] = now_default()
    archived_at: Mapped[datetime | None]


class Message(Base):
    __tablename__ = "message"

    id: Mapped[uuid.UUID] = id_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation.id", ondelete="CASCADE"))
    seq: Mapped[int]
    role: Mapped[str] = mapped_column(pg_enum("message_role"))
    content: Mapped[list[Any]]
    model: Mapped[str | None]
    tokens_in: Mapped[int | None]
    tokens_out: Mapped[int | None]
    latency_ms: Mapped[int | None]
    created_at: Mapped[datetime] = now_default()


class Run(Base):
    __tablename__ = "run"

    id: Mapped[uuid.UUID] = id_pk()
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("conversation.id", ondelete="SET NULL"))
    triggered_by_message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("message.id", ondelete="SET NULL"))
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(pg_enum("run_kind"))
    trigger: Mapped[str] = mapped_column(pg_enum("run_trigger"))
    status: Mapped[str] = mapped_column(pg_enum("run_status"), server_default="queued")
    arq_job_id: Mapped[str | None]
    error: Mapped[dict[str, Any] | None]
    created_at: Mapped[datetime] = now_default()
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class ToolCall(Base):
    __tablename__ = "tool_call"

    id: Mapped[uuid.UUID] = id_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("message.id", ondelete="SET NULL"))
    name: Mapped[str]
    risk_class: Mapped[str] = mapped_column(pg_enum("risk_class"))
    args: Mapped[dict[str, Any]] = mapped_column(server_default="{}")
    args_hash: Mapped[bytes]
    secret_args_ciphertext: Mapped[bytes | None] = mapped_column()
    secret_key_version: Mapped[int | None]
    idempotency_key: Mapped[str] = mapped_column(unique=True)
    status: Mapped[str] = mapped_column(pg_enum("tool_call_status"), server_default="proposed")
    result_summary: Mapped[dict[str, Any] | None]
    liara_request_id: Mapped[str | None]
    http_status: Mapped[int | None]
    duration_ms: Mapped[int | None]
    error: Mapped[dict[str, Any] | None]
    created_at: Mapped[datetime] = now_default()
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class RunStep(Base):
    __tablename__ = "run_step"

    id: Mapped[uuid.UUID] = id_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"))
    seq: Mapped[int]
    key: Mapped[str]
    label_fa: Mapped[str]
    status: Mapped[str] = mapped_column(pg_enum("step_status"), server_default="pending")
    tool_call_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tool_call.id", ondelete="SET NULL"))
    detail_fa: Mapped[str | None]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class Approval(Base):
    __tablename__ = "approval"

    id: Mapped[uuid.UUID] = id_pk()
    tool_call_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tool_call.id", ondelete="CASCADE"), unique=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(pg_enum("approval_status"), server_default="pending")
    preview: Mapped[dict[str, Any]]
    args_hash: Mapped[bytes]
    signature: Mapped[bytes]
    expires_at: Mapped[datetime]
    decision: Mapped[str | None] = mapped_column(pg_enum("approval_decision"))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None]
    reject_reason_fa: Mapped[str | None]
    executed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = now_default()
