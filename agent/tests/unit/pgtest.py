"""Throwaway `deployar_test` database on the Compose PG16 (dev data is never touched)."""

import asyncio
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from deployar.core.config import get_settings

AGENT_DIR = Path(__file__).resolve().parents[2]
DEV_URL = make_url(get_settings().database_url)
TEST_URL = DEV_URL.set(database="deployar_test")
TEST_URL_STR = TEST_URL.render_as_string(hide_password=False)
PG_TEST = TEST_URL.set(drivername="postgresql").render_as_string(hide_password=False)
PG_ADMIN = DEV_URL.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)
REDIS_TEST = "redis://localhost:6379/15"


async def _recreate_db() -> None:
    conn = await asyncpg.connect(PG_ADMIN, timeout=3)
    try:
        await conn.execute("drop database if exists deployar_test with (force)")
        await conn.execute("create database deployar_test")
    finally:
        await conn.close()


def fresh_schema(round_trip: bool = False) -> None:
    """Recreate the test database at head; skip the module if Compose Postgres is down."""
    try:
        asyncio.run(_recreate_db())
    except (OSError, asyncpg.PostgresError) as e:
        pytest.skip(f"Compose Postgres not reachable ({e}); run `docker compose up -d`")
    cfg = Config(str(AGENT_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", TEST_URL_STR)
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    if round_trip:
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
