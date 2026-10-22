"""Approval service: signed, one-time, 10-minute decisions with Postgres as truth (B-04)."""

import base64
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass

import asyncpg
import pytest
import redis.asyncio as aioredis
from pgtest import PG_TEST, REDIS_TEST, TEST_URL_STR, fresh_schema
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from deployar.core.errors import DeployarError
from deployar.runtime.approvals import ApprovalService, decision_key

SECRET = os.urandom(32)
ARGS = {"project": "torob-gard", "plan": "mars"}


@pytest.fixture(scope="module", autouse=True)
def schema() -> Iterator[None]:
    fresh_schema()
    yield


@dataclass
class Ctx:
    user: uuid.UUID
    project: uuid.UUID
    run: uuid.UUID


async def make_ctx() -> Ctx:
    conn = await asyncpg.connect(PG_TEST)
    try:
        user = await conn.fetchval("""insert into "user" (email) values (gen_random_uuid() || '@t.ir') returning id""")
        lc = await conn.fetchval(
            "insert into liara_connection (user_id, token_ciphertext, key_version, token_last4) "
            "values ($1, '\\x00', 1, 'abcd') returning id",
            user,
        )
        project = await conn.fetchval(
            "insert into project (user_id, liara_connection_id, name) values ($1, $2, 'p') returning id", user, lc
        )
        run = await conn.fetchval(
            "insert into run (project_id, kind, trigger) values ($1, 'sre', 'user_message') returning id", project
        )
        return Ctx(user, project, run)
    finally:
        await conn.close()


async def sql(query: str, *args: object) -> object:
    conn = await asyncpg.connect(PG_TEST)
    try:
        return await conn.fetchval(query, *args)
    finally:
        await conn.close()


@pytest.fixture
async def service() -> AsyncIterator[ApprovalService]:
    engine = create_async_engine(TEST_URL_STR)
    r = aioredis.from_url(REDIS_TEST)
    yield ApprovalService(async_sessionmaker(engine, expire_on_commit=False), r, SECRET)
    await r.aclose()
    await engine.dispose()


async def test_approve_releases_the_call(service: ApprovalService) -> None:
    ctx = await make_ctx()
    c = await service.create(ctx.run, ctx.project, ctx.user, "resize_plan", ARGS, {"tool": "resize_plan"})
    assert await sql("select status::text from tool_call where id = $1", c.tool_call_id) == "awaiting_approval"
    assert await service.decide(c.approval_id, ctx.user, "approve", c.token) == "approved"
    assert await service.wait(c.approval_id, timeout_s=1) == "approved"
    assert await service.revalidate(c.approval_id, ARGS)
    # the database gate now lets the call start
    await sql("update tool_call set status = 'running' where id = $1", c.tool_call_id)
    actions = await sql(
        "select array_agg(action order by id)::text from audit_log where approval_id = $1", c.approval_id
    )
    assert actions == "{approval.requested,approval.decided}"


async def test_reject_is_final(service: ApprovalService) -> None:
    ctx = await make_ctx()
    c = await service.create(ctx.run, ctx.project, ctx.user, "restart_app", ARGS, {})
    assert await service.decide(c.approval_id, ctx.user, "reject", c.token, reason="نه") == "rejected"
    assert await service.wait(c.approval_id, timeout_s=1) == "rejected"
    with pytest.raises(asyncpg.RaiseError):
        await sql("update tool_call set status = 'running' where id = $1", c.tool_call_id)


async def test_expired_decision_is_denied(service: ApprovalService) -> None:
    ctx = await make_ctx()
    c = await service.create(ctx.run, ctx.project, ctx.user, "restart_app", ARGS, {})
    # move the 10-minute window into the past; expires_at is signed, so re-sign like the card would have been
    expires_at = await sql(
        "update approval set created_at = now() - interval '11 minutes', expires_at = now() - interval '1 minute' "
        "where id = $1 returning expires_at",
        c.approval_id,
    )
    h = await sql("select args_hash from approval where id = $1", c.approval_id)
    sig = service._sign(c.approval_id, c.tool_call_id, h, ctx.user, expires_at)  # type: ignore[arg-type]
    token = f"{c.token.split('.')[0]}.{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"
    with pytest.raises(DeployarError) as e:
        await service.decide(c.approval_id, ctx.user, "approve", token)
    assert e.value.code == "approval_not_pending"
    assert await service.wait(c.approval_id, timeout_s=0.2) == "expired"


async def test_replayed_decision_is_denied(service: ApprovalService) -> None:
    ctx = await make_ctx()
    c = await service.create(ctx.run, ctx.project, ctx.user, "restart_app", ARGS, {})
    await service.decide(c.approval_id, ctx.user, "reject", c.token)
    with pytest.raises(DeployarError) as e:
        await service.decide(c.approval_id, ctx.user, "approve", c.token)  # second click, same token
    assert e.value.code == "approval_not_pending"
    assert await sql("select status::text from approval where id = $1", c.approval_id) == "rejected"


async def test_tampered_signature_is_denied(service: ApprovalService) -> None:
    ctx = await make_ctx()
    c = await service.create(ctx.run, ctx.project, ctx.user, "restart_app", ARGS, {})
    id_part, sig_part = c.token.split(".")
    sig = bytearray(base64.urlsafe_b64decode(sig_part + "=="))
    sig[0] ^= 1
    forged = f"{id_part}.{base64.urlsafe_b64encode(bytes(sig)).decode().rstrip('=')}"
    for token in (forged, "garbage", f"{id_part}."):
        with pytest.raises(DeployarError) as e:
            await service.decide(c.approval_id, ctx.user, "approve", token)
        assert e.value.code == "approval_bad_signature"
    assert await sql("select status::text from approval where id = $1", c.approval_id) == "pending"


async def test_token_of_another_approval_is_denied(service: ApprovalService) -> None:
    ctx = await make_ctx()
    a = await service.create(ctx.run, ctx.project, ctx.user, "restart_app", ARGS, {})
    b = await service.create(ctx.run, ctx.project, ctx.user, "resize_plan", ARGS, {})
    with pytest.raises(DeployarError) as e:
        await service.decide(a.approval_id, ctx.user, "approve", b.token)
    assert e.value.code == "approval_bad_signature"


async def test_wrong_user_is_denied(service: ApprovalService) -> None:
    ctx, other = await make_ctx(), await make_ctx()
    c = await service.create(ctx.run, ctx.project, ctx.user, "restart_app", ARGS, {})
    with pytest.raises(DeployarError) as e:
        await service.decide(c.approval_id, other.user, "approve", c.token)
    assert e.value.code == "approval_bad_signature"
    assert await sql("select status::text from approval where id = $1", c.approval_id) == "pending"


async def test_args_changed_after_approval_invalidates(service: ApprovalService) -> None:
    ctx = await make_ctx()
    c = await service.create(ctx.run, ctx.project, ctx.user, "resize_plan", ARGS, {})
    await service.decide(c.approval_id, ctx.user, "approve", c.token)
    assert not await service.revalidate(c.approval_id, {**ARGS, "plan": "pluto"})
    assert await sql("select status::text from approval where id = $1", c.approval_id) == "invalidated"
    with pytest.raises(asyncpg.RaiseError):
        await sql("update tool_call set status = 'running' where id = $1", c.tool_call_id)


async def test_lost_redis_push_resolves_from_postgres(service: ApprovalService) -> None:
    ctx = await make_ctx()
    c = await service.create(ctx.run, ctx.project, ctx.user, "restart_app", ARGS, {})
    await service.decide(c.approval_id, ctx.user, "approve", c.token)
    await service.redis.delete(decision_key(c.approval_id))  # the push never arrived
    assert await service.wait(c.approval_id, timeout_s=0.5) == "approved"


async def test_wait_with_redis_down_still_reads_postgres(service: ApprovalService) -> None:
    ctx = await make_ctx()
    c = await service.create(ctx.run, ctx.project, ctx.user, "restart_app", ARGS, {})
    await service.decide(c.approval_id, ctx.user, "approve", c.token)
    service.redis = aioredis.from_url("redis://localhost:1/0")  # nothing listens here
    assert await service.wait(c.approval_id, timeout_s=0.5) == "approved"


async def test_retry_after_reject_gets_a_new_call(service: ApprovalService) -> None:
    ctx = await make_ctx()
    a = await service.create(ctx.run, ctx.project, ctx.user, "restart_app", ARGS, {})
    await service.decide(a.approval_id, ctx.user, "reject", a.token)
    b = await service.create(ctx.run, ctx.project, ctx.user, "restart_app", ARGS, {})  # same args again
    assert b.tool_call_id != a.tool_call_id


def test_decision_endpoint_maps_errors() -> None:
    from fastapi.testclient import TestClient

    from deployar.api.approvals import current_user_id, get_approval_service
    from deployar.main import app

    class FakeService:
        async def decide(
            self, approval_id: uuid.UUID, user_id: uuid.UUID, decision: str, token: str, note: object
        ) -> str:
            if token == "replayed":
                raise DeployarError("approval_not_pending", "x")
            if token != "good":
                raise DeployarError("approval_bad_signature", "x")
            return "approved"

    app.dependency_overrides[current_user_id] = lambda: uuid.uuid4()
    app.dependency_overrides[get_approval_service] = FakeService
    try:
        client = TestClient(app)
        url = f"/api/approvals/{uuid.uuid4()}/decision"
        assert client.post(url, json={"decision": "approve", "signature": "good"}).json() == {"status": "approved"}
        assert client.post(url, json={"decision": "approve", "signature": "forged"}).status_code == 403
        r = client.post(url, json={"decision": "approve", "signature": "replayed"})
        assert r.status_code == 409 and r.json()["error"]["code"] == "approval_not_pending"
        assert client.post(url, json={"decision": "maybe", "signature": "good"}).status_code == 422
    finally:
        app.dependency_overrides.clear()
