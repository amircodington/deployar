import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from deployar.models.base import Base, id_pk, now_default, pg_enum


class RepoAnalysis(Base):
    __tablename__ = "repo_analysis"

    id: Mapped[uuid.UUID] = id_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run.id", ondelete="SET NULL"))
    commit_sha: Mapped[str]
    detector_version: Mapped[str]
    detected: Mapped[dict[str, Any]]
    summary_fa: Mapped[str | None]
    created_at: Mapped[datetime] = now_default()


class PlanProposal(Base):
    __tablename__ = "plan_proposal"

    id: Mapped[uuid.UUID] = id_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    repo_analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repo_analysis.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run.id", ondelete="SET NULL"))
    items: Mapped[list[Any]]
    app_plan_id: Mapped[str]
    app_price_monthly_rial: Mapped[int] = mapped_column(BigInteger)
    db_plan_id: Mapped[str | None]
    db_price_monthly_rial: Mapped[int | None] = mapped_column(BigInteger)
    total_monthly_rial: Mapped[int] = mapped_column(BigInteger)
    total_hourly_rial: Mapped[int] = mapped_column(BigInteger)
    balance_rial: Mapped[int | None] = mapped_column(BigInteger)
    price_source: Mapped[str]
    prices_fetched_at: Mapped[datetime]
    reasoning_fa: Mapped[str]
    alternatives: Mapped[list[Any]] = mapped_column(server_default="[]")
    status: Mapped[str] = mapped_column(pg_enum("proposal_status"), server_default="proposed")
    created_at: Mapped[datetime] = now_default()
    decided_at: Mapped[datetime | None]


class Deployment(Base):
    __tablename__ = "deployment"

    id: Mapped[uuid.UUID] = id_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"))
    tool_call_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tool_call.id", ondelete="SET NULL"))
    rolled_back_from_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("deployment.id", ondelete="SET NULL"))
    app_root: Mapped[str] = mapped_column(server_default=".")
    liara_app_name: Mapped[str]
    commit_sha: Mapped[str]
    source: Mapped[str] = mapped_column(server_default="github_tarball")
    liara_source_id: Mapped[str | None]
    liara_release_id: Mapped[str | None]
    status: Mapped[str] = mapped_column(pg_enum("deployment_status"), server_default="queued")
    build_log_tail: Mapped[str | None]
    health: Mapped[dict[str, Any] | None]
    error_fa: Mapped[str | None]
    created_at: Mapped[datetime] = now_default()
    live_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class Domain(Base):
    __tablename__ = "domain"

    id: Mapped[uuid.UUID] = id_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    hostname: Mapped[str] = mapped_column(CITEXT)
    liara_domain_id: Mapped[str | None]
    status: Mapped[str] = mapped_column(pg_enum("domain_status"), server_default="pending_dns")
    required_records: Mapped[list[Any]]
    last_check: Mapped[dict[str, Any] | None]
    last_checked_at: Mapped[datetime | None]
    verified_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = now_default()


class SecretValue(Base):
    """A value set_env may use by reference; the model only sees `id`."""

    __tablename__ = "secret_value"

    id: Mapped[uuid.UUID] = id_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    key: Mapped[str]
    ciphertext: Mapped[bytes]
    key_version: Mapped[int]
    origin: Mapped[str]
    created_at: Mapped[datetime] = now_default()
    used_at: Mapped[datetime | None]

    def __repr__(self) -> str:
        return f"<SecretValue {self.key} <encrypted>>"


class LiaraResource(Base):
    __tablename__ = "liara_resource"

    id: Mapped[uuid.UUID] = id_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("project.id", ondelete="SET NULL"))
    kind: Mapped[str]
    name: Mapped[str]
    liara_id: Mapped[str | None]
    plan_id: Mapped[str | None]
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = now_default()
