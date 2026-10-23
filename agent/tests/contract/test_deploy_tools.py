"""Sensitive deploy tools (B-11): approval-only, DATABASE_URL never reaches a result, row or preview (canary)."""

import base64
import io
import json
import tarfile
from typing import Any

import asyncpg
import httpx
import redis.asyncio as aioredis
import respx
from pgtest import PG_TEST, REDIS_TEST
from test_liara_client import API, _ctx_with_connection, _payload

GH = "https://api.github.com"
SHA = "a1b2c3d" + "0" * 33
CANARY = "CanaryPw-7f3e9a1c55"  # the DB root password; must only ever reach Liara's update-envs body


async def approve(ctx: Any, name: str, args: dict[str, Any]) -> None:
    from deployar.core.config import get_settings
    from deployar.runtime.approvals import ApprovalService

    r = aioredis.from_url(REDIS_TEST)
    service = ApprovalService(ctx.sessions, r, base64.b64decode(get_settings().approval_secret.get_secret_value()))
    created = await service.create(ctx.run_id, ctx.project_id, ctx.user_id, name, args, {"tool": name})
    await service.decide(created.approval_id, ctx.user_id, "approve", created.token)
    await r.aclose()


def tarball(files: dict[str, str]) -> bytes:
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as t:
        for path, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(f"amox-torob-gard-{SHA[:7]}/{path}")
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    return out.getvalue()


def names(tar_gz: bytes) -> list[str]:
    with tarfile.open(fileobj=io.BytesIO(tar_gz), mode="r:gz") as t:
        return sorted(t.getnames())


def test_repack_keeps_only_the_app_root() -> None:
    from deployar.tools.liara.deploy import repack

    src = tarball({"api/Dockerfile": "FROM python", "api/app/main.py": "x", "web/package.json": "{}",
                   ".git/config": "x", "README.md": "hi"})  # fmt: skip
    assert names(repack(src, "api")) == ["Dockerfile", "app/main.py"]
    assert "web/package.json" in names(repack(src, ".")) and ".git/config" not in names(repack(src, "."))


@respx.mock
async def test_sensitive_tools_refuse_without_approval() -> None:
    from deployar.tools.liara import deploy  # noqa: F401
    from deployar.tools.registry import REGISTRY

    create = respx.post(f"{API}/v1/projects").respond(200)
    ctx = await _ctx_with_connection()
    args = {"app_root": ".", "platform": "docker", "plan_id": "ir-medium"}
    out = await REGISTRY.run(ctx, "create_app", args)
    assert out["is_error"] and _payload(out)["code"] == "approval_missing"
    assert not create.called  # nothing reached Liara


@respx.mock
async def test_create_app_adopts_the_users_existing_app_on_409() -> None:
    from deployar.tools.liara import deploy  # noqa: F401
    from deployar.tools.registry import REGISTRY

    respx.get(f"{API}/v1/networks").respond(json={"networks": [{"_id": "net-1", "name": "deployar"}]})
    respx.post(f"{API}/v1/projects").respond(409, json={"message": "project exists"})
    mine = respx.get(f"{API}/v1/projects/shop").respond(json={"project": {"name": "shop"}})
    ctx = await _ctx_with_connection()
    args = {"app_root": ".", "name": "shop", "platform": "docker", "plan_id": "small-g2"}
    await approve(ctx, "create_app", args)
    out = _payload(await REGISTRY.run(ctx, "create_app", args))
    assert out["status"] == "ok" and out["data"]["already_existed"] is True and mine.called  # Deployar's data was reset


@respx.mock
async def test_database_url_goes_to_set_env_only_as_ciphertext() -> None:
    from deployar.tools.liara import deploy  # noqa: F401
    from deployar.tools.registry import REGISTRY

    nets = respx.get(f"{API}/v1/networks")
    nets.side_effect = [httpx.Response(200, json={"networks": []}),
                        httpx.Response(200, json={"networks": [{"_id": "net-1", "name": "deployar"}]})]  # fmt: skip
    respx.post(f"{API}/v1/networks").respond(200)
    respx.get(f"{API}/v1/me").respond(json={"user": {}, "databaseVersions": {"postgres": [
        {"value": "16.14", "postgisValue": "3.6"}, {"value": "17.6"}]}})  # fmt: skip
    created = respx.post(f"{API}/v1/databases").respond(json={"databaseID": "db-9"})
    db_row = {"status": "RUNNING", "hostname": "torob-gard-db", "port": 31234, "internalPort": 5432, "username": "root",
              "root_password": CANARY}  # fmt: skip
    respx.get(f"{API}/v1/databases/db-9").respond(json={"database": db_row})
    respx.get(f"{API}/v1/projects/torob-gard").respond(json={"project": {"envs": [{"key": "KEEP", "value": "1"}]}})
    envs = respx.post(f"{API}/v1/projects/update-envs").respond(200)

    ctx = await _ctx_with_connection()
    db_args = {"kind": "postgres", "plan_id": "ir-small"}
    await approve(ctx, "create_database", db_args)
    db_out = await REGISTRY.run(ctx, "create_database", db_args)
    db = _payload(db_out)
    assert db["status"] == "ok", db
    assert json.loads(created.calls[0].request.content)["network"] == "net-1"
    assert json.loads(created.calls[0].request.content)["version"] == "16.14"  # the one with PostGIS
    assert json.loads(created.calls[0].request.content)["bundlePlanID"] == "default"  # Liara 400s without it
    ref = db["data"]["value_ref"]
    assert ref.startswith("secret:") and CANARY not in json.dumps(db_out)

    env_args = {"vars": [{"key": "DATABASE_URL", "value_ref": ref}, {"key": "DJANGO_SECRET_KEY", "generate": True}]}
    await approve(ctx, "set_env", env_args)
    env_out = await REGISTRY.run(ctx, "set_env", env_args)
    assert _payload(env_out)["data"]["keys_set"] == ["DATABASE_URL", "DJANGO_SECRET_KEY"]
    sent = {v["key"]: v["value"] for v in json.loads(envs.calls[0].request.content)["variables"]}
    assert sent["DATABASE_URL"] == f"postgresql://root:{CANARY}@torob-gard-db:5432/postgres"
    assert sent["KEEP"] == "1" and len(sent["DJANGO_SECRET_KEY"]) > 40  # merged, not replaced
    assert CANARY not in json.dumps(env_out)

    conn = await asyncpg.connect(PG_TEST)
    try:  # the canary is nowhere in what the model or the audit trail can read
        q = "select args::text, coalesce(result_summary::text, '') s from tool_call where run_id = $1"
        rows = await conn.fetch(q, ctx.run_id)
        previews = await conn.fetch("select preview::text from approval where run_id = $1", ctx.run_id)
        stored = await conn.fetchval("select ciphertext from secret_value where key = 'DATABASE_URL' limit 1")
    finally:
        await conn.close()
    assert rows and all(CANARY not in r["args"] + r["s"] for r in rows)
    assert all(CANARY not in p["preview"] for p in previews)
    assert CANARY.encode() not in stored

    plain = {"vars": [{"key": "API_TOKEN", "value": "typed-in-chat"}]}
    await approve(ctx, "set_env", plain)
    assert _payload(await REGISTRY.run(ctx, "set_env", plain))["code"] == "plain_secret"


@respx.mock
async def test_deploy_release_uploads_the_app_folder_and_records_a_deployment() -> None:
    from deployar.tools.liara import deploy  # noqa: F401
    from deployar.tools.registry import REGISTRY

    respx.get(f"{GH}/repos/amox/torob-gard/commits/main").respond(json={"sha": SHA})
    respx.get(f"{GH}/repos/amox/torob-gard/tarball/{SHA}").respond(
        content=tarball({"Dockerfile": "FROM python", "manage.py": "x"}))  # fmt: skip
    upload = respx.post(f"{API}/v2/projects/torob-gard/sources").respond(json={"sourceID": "src-1"})
    release = respx.post(f"{API}/v2/projects/torob-gard/releases").respond(json={"releaseID": "rel-1"})

    ctx = await _ctx_with_connection()
    conn = await asyncpg.connect(PG_TEST)
    await conn.execute("update project set repo_full_name = 'amox/torob-gard', repo_default_branch = 'main', "
                       "platform = 'docker' where id = $1", ctx.project_id)  # fmt: skip
    await conn.close()

    await approve(ctx, "deploy_release", {})
    out = _payload(await REGISTRY.run(ctx, "deploy_release", {}))
    assert out["status"] == "ok", out
    assert out["data"]["release_id"] == "rel-1" and out["data"]["commit"] == SHA[:7]
    body = upload.calls[0].request.content
    archive = body[body.index(b"\x1f\x8b") : body.rindex(b"\r\n--")]  # the multipart part holding the gzip
    assert names(archive) == ["Dockerfile", "manage.py"]
    sent = json.loads(release.calls[0].request.content)
    assert sent["sourceID"] == "src-1" and sent["type"] == "docker" and sent["gitInfo"]["commit"] == SHA
    assert sent["build"] == {"location": "germany"}  # builds outside Iran, where apt and pypi answer

    conn = await asyncpg.connect(PG_TEST)
    try:
        status = await conn.fetchval("select status::text from deployment where liara_release_id = 'rel-1'")
    finally:
        await conn.close()
    assert status == "building"


async def test_user_env_values_are_posted_straight_to_the_vault() -> None:
    from deployar.main import app

    conn = await asyncpg.connect(PG_TEST)
    await conn.execute("""insert into "user" (email) values ('owner@deployar.ir') on conflict do nothing""")
    await conn.close()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post("/api/session", json={"passphrase": "p"})
        user_id = login.json()["user_id"]
        conn = await asyncpg.connect(PG_TEST)
        lc = await conn.fetchval("select id from liara_connection where user_id = $1 and status = 'active'", user_id)
        insert = (
            "insert into liara_connection (user_id, token_ciphertext, key_version, token_last4) "
            "values ($1, '\\x00', 1, 'abcd') returning id"
        )
        lc = lc or await conn.fetchval(insert, user_id)
        pid = await conn.fetchval("insert into project (user_id, liara_connection_id, name) values ($1, $2, 'p') "
                                  "returning id", user_id, lc)  # fmt: skip
        await conn.close()
        r = await client.post(
            f"/api/projects/{pid}/env-values", json={"key": "BOXAPI_KEY", "value": "sk-user-typed-42"}
        )
        assert r.status_code == 200 and r.json()["value_ref"].startswith("secret:")
        assert "sk-user-typed-42" not in r.text
        bad = await client.post(f"/api/projects/{pid}/env-values", json={"key": "1bad", "value": "x"})
        assert bad.status_code == 422
