"""Declarative base. Migrations are the source of truth for constraints; models mirror columns."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, LargeBinary, func, text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from deployar.core.ids import new_id
from deployar.models.enums import ENUMS


class Base(DeclarativeBase):
    type_annotation_map = {
        uuid.UUID: UUID(as_uuid=True),
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
        list[Any]: JSONB,
        bytes: LargeBinary,
    }


def pg_enum(name: str) -> ENUM:
    """Enum types are created by migration 0001."""
    return ENUM(*ENUMS[name], name=name, create_type=False)


def id_pk() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=new_id, server_default=text("uuid_generate_v7()"))


def now_default() -> Mapped[datetime]:
    return mapped_column(server_default=func.now())
