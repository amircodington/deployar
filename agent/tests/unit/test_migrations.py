"""Schema v1 against the Compose PG16, in a throwaway `deployar_test` database (dev data is never touched)."""

import asyncio
import hashlib
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from deployar.core.config import get_settings
from deployar.models import Base

AGENT_DIR = Path(__file__).resolve().parents[2]
DEV_URL = make_url(get_settings().database_url)
TEST_URL = DEV_URL.set(database="deployar_test")
PG_TEST = TEST_URL.set(drivername="postgresql").render_as_string(hide_password=False)
PG_ADMIN = DEV_URL.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)


async def _recreate_db() -> None:
    conn = await asyncpg.connect(PG_ADMIN, timeout=3)
    try:
        await conn.execute("drop database if exists deployar_test with (force)")
        await conn.execute("create database deployar_test")
    finally:
        await conn.close()


def _alembic() -> Config:
    cfg = Config(str(AGENT_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", TEST_URL.render_as_string(hide_password=False))
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture(scope="module", autouse=True)
def schema() -> Iterator[None]:
    try:
        asyncio.run(_recreate_db())
    except (OSError, asyncpg.PostgresError) as e:
        pytest.skip(f"Compose Postgres not reachable ({e}); run `docker compose up -d`")
    cfg = _alembic()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


async def _conn() -> asyncpg.Connection:
    return await asyncpg.connect(PG_TEST)


async def test_models_match_database_columns() -> None:
    conn = await _conn()
    try:
        for table in Base.metadata.sorted_tables:
            rows = await conn.fetch(
                "select column_name, is_nullable = 'YES' as nullable from information_schema.columns "
                "where table_schema = 'public' and table_name = $1",
                table.name,
            )
            in_db = {(r["column_name"], r["nullable"]) for r in rows}
            in_model = {(c.name, bool(c.nullable)) for c in table.columns}
            assert in_db == in_model, f"{table.name}: db-only {in_db - in_model}, model-only {in_model - in_db}"
    finally:
        await conn.close()


async def _run(conn: asyncpg.Connection) -> tuple[object, object, object]:
    user = await conn.fetchval("""insert into "user" (email) values ('gate-' || gen_random_uuid() || '@t.ir')
                                  returning id""")
    lc = await conn.fetchval(
        "insert into liara_connection (user_id, token_ciphertext, key_version, token_last4) "
        "values ($1, '\\x00', 1, 'abcd') returning id",
        user,
    )
    project = await conn.fetchval(
        "insert into project (user_id, liara_connection_id, name) values ($1, $2, 'ترب‌گرد') returning id",
        user,
        lc,
    )
    run = await conn.fetchval(
        "insert into run (project_id, kind, trigger) values ($1, 'deploy', 'user_message') returning id",
        project,
    )
    return user, project, run


async def _tool_call(conn: asyncpg.Connection, run: object, status: str = "proposed", h: bytes = b"h1") -> object:
    return await conn.fetchval(
        "insert into tool_call (run_id, name, risk_class, args_hash, idempotency_key, status) "
        "values ($1, 'restart_app', 'sensitive', $2, gen_random_uuid()::text, $3) returning id",
        run,
        h,
        status,
    )


async def test_gate_rejects_sensitive_call_without_approval() -> None:
    conn = await _conn()
    try:
        _, _, run = await _run(conn)
        tc = await _tool_call(conn, run)
        for status in ("running", "succeeded"):
            with pytest.raises(asyncpg.RaiseError, match="no approved approval"):
                await conn.execute("update tool_call set status = $2 where id = $1", tc, status)
        with pytest.raises(asyncpg.RaiseError, match="no approved approval"):
            await _tool_call(conn, run, status="succeeded")  # inserted as already executed
    finally:
        await conn.close()


async def test_gate_releases_only_the_approved_args() -> None:
    conn = await _conn()
    try:
        user, project, run = await _run(conn)
        tc = await _tool_call(conn, run, status="awaiting_approval")
        await conn.execute(
            "insert into approval (tool_call_id, run_id, project_id, user_id, status, preview, args_hash, "
            "signature, decision, decided_at) values ($1, $2, $3, $4, 'approved', '{}', 'h1', 's', 'approve', now())",
            tc,
            run,
            project,
            user,
        )
        with pytest.raises(asyncpg.RaiseError):  # args changed since the approval
            await conn.execute("update tool_call set status = 'running', args_hash = 'h2' where id = $1", tc)
        await conn.execute("update tool_call set status = 'running' where id = $1", tc)
        with pytest.raises(asyncpg.RaiseError, match="args changed"):
            await conn.execute("update tool_call set args_hash = 'h2' where id = $1", tc)
        await conn.execute("update tool_call set status = 'succeeded' where id = $1", tc)
    finally:
        await conn.close()


async def test_risk_class_must_match_tool_name() -> None:
    conn = await _conn()
    try:
        _, _, run = await _run(conn)
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "insert into tool_call (run_id, name, risk_class, args_hash, idempotency_key) "
                "values ($1, 'restart_app', 'read', 'h', 'k-misclassified')",
                run,
            )
    finally:
        await conn.close()


async def test_audit_log_is_append_only_and_chained() -> None:
    conn = await _conn()
    try:
        a = await conn.fetchval("select audit_append('system', 'test.first')")
        b = await conn.fetchval("""select audit_append('user', 'test.second', p_data => '{"k": 1}')""")
        first, second = [await conn.fetchrow("select * from audit_log where id = $1", i) for i in (a, b)]
        assert second["prev_hash"] == first["row_hash"]
        assert len(second["row_hash"]) == len(hashlib.sha256().digest())
        with pytest.raises(asyncpg.RaiseError, match="append-only"):
            await conn.execute("update audit_log set action = 'test.changed' where id = $1", a)
        with pytest.raises(asyncpg.RaiseError, match="append-only"):
            await conn.execute("delete from audit_log where id = $1", a)
    finally:
        await conn.close()


def test_seed_creates_the_single_user_once() -> None:
    env = {**os.environ, "DATABASE_URL": TEST_URL.render_as_string(hide_password=False)}
    for _ in range(2):
        subprocess.run(
            ["uv", "run", "deployar-seed", "--email", "Mohammad@Deployar.ir"],
            cwd=AGENT_DIR, env=env, check=True, capture_output=True,
        )  # fmt: skip

    async def roles() -> list[str]:
        conn = await _conn()
        try:
            rows = await conn.fetch("""select role from "user" where email = 'mohammad@deployar.ir'""")  # citext
            return [r["role"] for r in rows]
        finally:
            await conn.close()

    assert asyncio.run(roles()) == ["admin"]
