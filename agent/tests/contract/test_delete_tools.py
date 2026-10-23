"""Irreversible deletes: approval only, the typed name is checked by the decision API itself, and the tool reads
the list again to show the app or database is really gone."""

import base64
from typing import Any

import pytest
import redis.asyncio as aioredis
import respx
from pgtest import REDIS_TEST
from test_deploy_tools import approve
from test_liara_client import API, _ctx_with_connection, _payload


async def _service() -> Any:
    from deployar.core.config import get_settings
    from deployar.runtime.approvals import ApprovalService

    return ApprovalService(_ctx.sessions, aioredis.from_url(REDIS_TEST),
                           base64.b64decode(get_settings().approval_secret.get_secret_value()))  # fmt: skip


_ctx: Any = None


async def test_the_decision_api_refuses_a_delete_without_the_typed_name() -> None:
    global _ctx
    from deployar.core.errors import DeployarError
    from deployar.tools.liara import delete  # noqa: F401
    from deployar.tools.registry import REGISTRY

    _ctx = await _ctx_with_connection()
    preview = REGISTRY.preview_of("delete_app", {"app": "shop"})
    assert preview["danger"] is True and preview["confirm_text"] == "shop"
    svc = await _service()
    created = await svc.create(_ctx.run_id, _ctx.project_id, _ctx.user_id, "delete_app", {"app": "shop"}, preview)
    for wrong in (None, "", "sho", "Shop"):
        with pytest.raises(DeployarError) as e:
            await svc.decide(created.approval_id, _ctx.user_id, "approve", created.token, confirm=wrong)
        assert e.value.code == "approval_confirm_mismatch"
    assert await svc.decide(created.approval_id, _ctx.user_id, "approve", created.token, confirm=" shop ") == "approved"
    await svc.redis.aclose()


@respx.mock
async def test_delete_app_removes_it_and_checks_the_list_again() -> None:
    from deployar.tools.liara import delete  # noqa: F401
    from deployar.tools.registry import REGISTRY

    env = [{"key": "DATABASE_URL", "value": "postgresql://root:Pw-2@torob-db:5432/postgres"}]
    respx.get(f"{API}/v1/projects/torob-gard").respond(json={"project": {"planID": "small-g2", "type": "docker",
                                                                          "envs": env}})  # fmt: skip
    respx.get(f"{API}/v1/databases").respond(json={"databases": [{"_id": "d1", "hostname": "torob-db"},
                                                                 {"_id": "d2", "hostname": "other-db"}]})  # fmt: skip
    gone = respx.delete(f"{API}/v1/projects/torob-gard").respond(200)
    respx.get(f"{API}/v1/projects").respond(json={"projects": [{"project_id": "other-app"}]})
    ctx = await _ctx_with_connection()
    args = {"app": "torob-gard"}
    assert _payload(await REGISTRY.run(ctx, "delete_app", args))["code"] == "approval_missing"  # never without a yes
    assert not gone.called
    await approve(ctx, "delete_app", args)
    out = _payload(await REGISTRY.run(ctx, "delete_app", args))
    assert out["status"] == "ok" and out["data"]["verified_gone"] is True and out["data"]["was"]["planID"] == "small-g2"
    assert gone.called and out["data"]["linked_databases"] == ["torob-db"]  # only the one in its env, offered next
    assert "Pw-2" not in str(out)


@respx.mock
async def test_delete_database_finds_it_by_name_and_never_returns_its_password() -> None:
    from deployar.tools.liara import delete  # noqa: F401
    from deployar.tools.registry import REGISTRY

    db = {"_id": "db-9", "hostname": "shop-db", "type": "postgres", "planID": "small-g2", "root_password": "Pw-1"}
    lists = respx.get(f"{API}/v1/databases")
    lists.side_effect = [respx.MockResponse(json={"databases": [db]}), respx.MockResponse(json={"databases": []})]
    gone = respx.delete(f"{API}/v1/databases/db-9").respond(200)
    ctx = await _ctx_with_connection()
    args = {"database": "shop-db"}
    await approve(ctx, "delete_database", args)
    out = await REGISTRY.run(ctx, "delete_database", args)
    data = _payload(out)["data"]
    assert data["verified_gone"] is True and gone.called and "Pw-1" not in str(out)


@respx.mock
async def test_an_app_deployar_has_no_record_of_gets_a_project_when_its_chat_opens() -> None:
    import asyncpg
    from pgtest import PG_TEST

    from deployar.api.conversations import _adopt
    from deployar.api.deps import get_runtime

    respx.get(f"{API}/v1/projects/legacy-shop").respond(json={"project": {"type": "docker", "planID": "small-g2"}})
    respx.get(f"{API}/v1/projects/not-mine").respond(404)
    ctx = await _ctx_with_connection()
    pid = await _adopt(get_runtime(), ctx.user_id, "legacy-shop")
    assert pid is not None and await _adopt(get_runtime(), ctx.user_id, "not-mine") is None
    conn = await asyncpg.connect(PG_TEST)
    try:
        row = await conn.fetchrow("select liara_app_name, platform, plan_id from project where id = $1", pid)
    finally:
        await conn.close()
    assert dict(row) == {"liara_app_name": "legacy-shop", "platform": "docker", "plan_id": "small-g2"}


@respx.mock
async def test_list_databases_shows_names_never_passwords() -> None:
    from deployar.tools.liara import delete  # noqa: F401
    from deployar.tools.registry import REGISTRY

    respx.get(f"{API}/v1/databases").respond(
        json={
            "databases": [
                {"_id": "d1", "hostname": "shop-db", "type": "postgres", "planID": "small-g2", "root_password": "Pw-3"}
            ]
        }
    )
    ctx = await _ctx_with_connection()
    out = await REGISTRY.run(ctx, "list_databases", {})
    assert _payload(out)["data"]["databases"][0]["database"] == "shop-db" and "Pw-3" not in str(out)
