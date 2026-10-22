import uuid
from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from deployar.models.base import Base, id_pk, now_default, pg_enum


class User(Base):
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = id_pk()
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    display_name: Mapped[str | None]
    role: Mapped[str] = mapped_column(pg_enum("user_role"), server_default="member")
    locale: Mapped[str] = mapped_column(server_default="fa-IR")
    created_at: Mapped[datetime] = now_default()
    last_seen_at: Mapped[datetime | None]
    deleted_at: Mapped[datetime | None]


class LiaraConnection(Base):
    __tablename__ = "liara_connection"

    id: Mapped[uuid.UUID] = id_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(server_default="Liara")
    token_ciphertext: Mapped[bytes] = mapped_column()
    key_version: Mapped[int]
    token_last4: Mapped[str]
    liara_account_email: Mapped[str | None]
    team_id: Mapped[str | None]
    status: Mapped[str] = mapped_column(pg_enum("connection_status"), server_default="active")
    expires_at: Mapped[datetime | None]
    last_verified_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = now_default()
    revoked_at: Mapped[datetime | None]


class GithubConnection(Base):
    __tablename__ = "github_connection"

    id: Mapped[uuid.UUID] = id_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    token_ciphertext: Mapped[bytes] = mapped_column()
    key_version: Mapped[int]
    token_last4: Mapped[str]
    account_login: Mapped[str]
    status: Mapped[str] = mapped_column(pg_enum("connection_status"), server_default="active")
    expires_at: Mapped[datetime | None]
    last_verified_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = now_default()
    revoked_at: Mapped[datetime | None]
