"""Liara client, read tools and the connection endpoint against recorded-shape responses (B-08)."""

import json
import uuid
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import pytest
import respx
from pgtest import PG_TEST

CASSETTES = Path(__file__).resolve().parents[1] / "cassettes" / "liara"
API = "https://api.liara.ir"
TOKEN = "liara-test-token-0123456789abcdef"  # fake


def cassette(name: str) -> Any:
    return json.loads((CASSETTES / f"{name}.json").read_text())


# --- client ------------------------------------------------------------------------------------


@respx.mock
async def test_client_trims_secrets_and_maps_errors() -> None:
    from deployar.clients.liara import LiaraClient, LiaraNotFound
    from deployar.core.errors import DeployarError

    respx.get(f"{API}/v1/projects/torob-gard").respond(json=cassette("project"))
    respx.get(f"{API}/v1/me").respond(json=cassette("me"))
    respx.get(f"{API}/v1/projects/missing").respond(404)
    billing = respx.get(f"{API}/v1/billing")
    billing.side_effect = [httpx.Response(429), httpx.Response(200, json=cassette("billing"))]

    async with LiaraClient(TOKEN, team_id="team-7") as c:
        project = await c.project("torob-gard")
        assert project["env_keys"] == ["DATABASE_URL", "DJANGO_SECRET_KEY"]
        assert "hunter2" not in json.dumps(project) and "envs" not in project
        me = await c.me_summary()
        assert "FAKE-SECRET" not in json.dumps(me) and "0011223344" not in json.dumps(me)
        assert (await c.billing())["balance"] == 2000000  # retried after 429; team credit, not personal
        with pytest.raises(LiaraNotFound):
            await c.project("missing")
    assert billing.calls[-1].request.url.params["teamID"] == "team-7"
    assert billing.calls[-1].request.headers["authorization"] == f"Bearer {TOKEN}"

    respx.get(f"{API}/v1/billing").respond(401)
    async with LiaraClient("bad-token-xxxxxxxxxxxxxxxxxxxx") as c:
        with pytest.raises(DeployarError) as e:
            await c.billing()
    assert e.value.code == "liara_unauthorized"


# --- tools -------------------------------------------------------------------------------------


async def _ctx_with_connection() -> Any:
    from deployar.core.crypto import aad_for, get_vault
    from deployar.core.db import get_sessionmaker
    from deployar.tools.registry import ToolContext

    conn = await asyncpg.connect(PG_TEST)
    try:
        user = await conn.fetchval("""insert into "user" (email) values (gen_random_uuid() || '@t.ir') returning id""")
        cid = uuid.uuid4()
        blob, version = get_vault().encrypt(TOKEN, aad_for("liara_connection", cid, user))
        await conn.execute(
            "insert into liara_connection (id, user_id, token_ciphertext, key_version, token_last4, team_id) "
            "values ($1, $2, $3, $4, 'cdef', 'team-7')",
            cid, user, blob, version,
        )  # fmt: skip
        project = await conn.fetchval(
            "insert into project (user_id, liara_connection_id, name, liara_app_name) "
            "values ($1, $2, 'ترب‌گرد', 'torob-gard') returning id",
            user, cid,
        )  # fmt: skip
        run = await conn.fetchval(
            "insert into run (project_id, kind, trigger) values ($1, 'chat', 'user_message') returning id", project
        )
    finally:
        await conn.close()
    return ToolContext(run_id=run, project_id=project, user_id=user, sessions=get_sessionmaker())


def _payload(out: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(out["content"][0]["text"])
    return payload


@respx.mock
async def test_every_read_tool_against_its_cassette() -> None:
    from deployar.tools.liara import read  # noqa: F401  registers the tools
    from deployar.tools.registry import REGISTRY

    respx.get(f"{API}/v1/billing").respond(json=cassette("billing"))
    respx.get(f"{API}/v1/me").respond(json=cassette("me"))
    respx.get(f"{API}/v1/projects/torob-gard").respond(json=cassette("project"))
    respx.get(f"{API}/v2/projects/torob-gard/logs").respond(json=cassette("logs"))
    respx.get(f"{API}/v1/projects/torob-gard/releases").respond(json=cassette("releases"))
    respx.get(f"{API}/v1/projects/torob-gard/metrics/summary").respond(json=cassette("metrics_summary"))
    respx.get(url__regex=rf"{API}/v1/projects/torob-gard/metrics/(memory|cpu)").respond(json=cassette("metrics_series"))
    ctx = await _ctx_with_connection()

    results = {name: _payload(await REGISTRY.run(ctx, name, args)) for name, args in [
        ("get_balance", {}), ("list_plans", {"kind": "app"}), ("get_app_status", {}), ("get_env_keys", {}),
        ("get_logs", {"minutes": 30, "grep": "timeout"}), ("get_metrics", {"minutes": 60}), ("list_releases", {}),
    ]}  # fmt: skip
    for name, p in results.items():
        assert p["status"] == "ok", (name, p)
        assert p["source"].startswith("liara:") and p["observed_at"], name  # hard rule 3
    assert results["get_balance"]["data"]["balance_toman"] == 2000000
    assert results["get_env_keys"]["data"]["keys"] == ["DATABASE_URL", "DJANGO_SECRET_KEY"]
    assert results["get_app_status"]["data"]["planID"] == "mars"
    assert [ln["message"] for ln in results["get_logs"]["data"]["lines"]] == ["WORKER TIMEOUT (pid:42)"]
    assert results["list_releases"]["data"]["current"] == "r2"
    everything = json.dumps(results)
    for secret in ("hunter2", "django-insecure", "FAKE-SECRET", "0011223344", TOKEN):
        assert secret not in everything


@respx.mock
async def test_metrics_gap_is_a_limitation_and_missing_app_an_error() -> None:
    from deployar.tools.liara import read  # noqa: F401
    from deployar.tools.registry import REGISTRY

    respx.get(f"{API}/v1/projects/torob-gard/metrics/summary").respond(404)
    ctx = await _ctx_with_connection()
    assert _payload(await REGISTRY.run(ctx, "get_metrics", {}))["code"] == "metrics_unavailable"

    respx.get(f"{API}/v1/projects/torob-gard").respond(404)
    assert _payload(await REGISTRY.run(ctx, "get_app_status", {}))["code"] == "app_not_found"


# --- connection endpoint -----------------------------------------------------------------------


@respx.mock
async def test_pasting_a_token_validates_and_stores_it_encrypted() -> None:
    from deployar.main import app

    respx.get(f"{API}/v1/billing").respond(json=cassette("billing"))
    respx.get(f"{API}/v1/me").respond(json=cassette("me"))
    conn = await asyncpg.connect(PG_TEST)
    await conn.execute("""insert into "user" (email) values ('owner@deployar.ir') on conflict do nothing""")
    await conn.close()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post("/api/session", json={"passphrase": "p"})
        assert login.status_code == 200
        user_id = uuid.UUID(login.json()["user_id"])  # single-user MVP: the first user
        r = await client.post("/api/connections/liara", json={"token": TOKEN, "team_id": "team-7"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["token_last4"] == "cdef" and body["account"] == "owner@example.com"
        assert TOKEN not in r.text
        assert (await client.get("/api/connections/liara")).json()["token_last4"] == "cdef"

        respx.get(f"{API}/v1/billing").respond(401)
        bad = await client.post("/api/connections/liara", json={"token": "x" * 30})
        assert bad.status_code == 400 and bad.json()["error"]["code"] == "liara_unauthorized"

    conn = await asyncpg.connect(PG_TEST)
    try:
        rows = await conn.fetch(
            "select token_ciphertext, status::text from liara_connection where user_id = $1", user_id
        )
    finally:
        await conn.close()
    active = [r for r in rows if r["status"] == "active"]
    assert len(active) == 1 and TOKEN.encode() not in active[0]["token_ciphertext"]
