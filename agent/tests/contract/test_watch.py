"""watch_deployment (B-12): follows the release to a live URL, or to a Persian reason with the log tail."""

from typing import Any

import asyncpg
import httpx
import pytest
import respx
from pgtest import PG_TEST
from test_liara_client import API, _ctx_with_connection, _payload

SHA = "b" * 40


async def _deployment(ctx: Any, release: str) -> str:
    conn = await asyncpg.connect(PG_TEST)
    try:
        q = (
            "insert into deployment (project_id, run_id, liara_app_name, commit_sha, liara_release_id, status) "
            "values ($1, $2, 'torob-gard', $3, $4, 'building') returning id"
        )
        return str(await conn.fetchval(q, ctx.project_id, ctx.run_id, SHA, release))
    finally:
        await conn.close()


def _emit_into(ctx: Any, cards: list[tuple[str, dict[str, Any]]]) -> Any:
    from dataclasses import replace

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        cards.append((kind, payload))

    return replace(ctx, emit=emit)


@respx.mock
async def test_build_to_live_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from deployar.tools.liara import watch
    from deployar.tools.registry import REGISTRY

    monkeypatch.setattr(watch, "POLL_S", 0)
    states = respx.get(f"{API}/v1/releases/rel-1")
    states.side_effect = [
        httpx.Response(200, json={"release": {"state": s}}) for s in ("BUILDING", "DEPLOYING", "READY")
    ]
    respx.get(f"{API}/v2/releases/rel-1/build-logs").respond(json={"buildOutput": [
        {"stream": "STDOUT", "line": "Step 1/5 : FROM python:3.13", "createdAt": "t1"}]})  # fmt: skip
    respx.get("https://torob-gard.liara.run").respond(200, text="ok")

    cards: list[tuple[str, dict[str, Any]]] = []
    ctx = _emit_into(await _ctx_with_connection(), cards)
    dep = await _deployment(ctx, "rel-1")
    out = _payload(await REGISTRY.run(ctx, "watch_deployment", {"deployment_id": dep}))
    assert out["status"] == "ok" and out["data"]["health"]["ok"], out
    kinds = [k for k, _ in cards]
    assert kinds.count("deploy_progress") == 3 and kinds[-1] == "live_url"
    assert cards[0][1]["log_tail"] == ["Step 1/5 : FROM python:3.13"]

    conn = await asyncpg.connect(PG_TEST)
    try:
        row = await conn.fetchrow("select status::text, live_at from deployment where id = $1::uuid", dep)
        url = await conn.fetchval("select live_url from project where id = $1", ctx.project_id)
    finally:
        await conn.close()
    assert row["status"] == "live" and row["live_at"] is not None and url == "https://torob-gard.liara.run"


@respx.mock
async def test_failed_build_gives_a_reason_and_the_tail(monkeypatch: pytest.MonkeyPatch) -> None:
    from deployar import messages_fa as fa
    from deployar.tools.liara import watch
    from deployar.tools.registry import REGISTRY

    monkeypatch.setattr(watch, "POLL_S", 0)
    respx.get(f"{API}/v1/releases/rel-2").respond(json={"release": {"state": "FAILED"}})
    respx.get(f"{API}/v2/releases/rel-2/build-logs").respond(json={"buildOutput": [
        {"stream": "STDOUT", "line": "npm ERR! 404 Not Found - left-pad@9.9.9", "createdAt": "t1"},
        {"stream": "STDOUT", "line": "DATABASE_URL=postgres://u:hunter2@db/x", "createdAt": "t2"}]})  # fmt: skip

    ctx = await _ctx_with_connection()
    dep = await _deployment(ctx, "rel-2")
    out = _payload(await REGISTRY.run(ctx, "watch_deployment", {"deployment_id": dep}))
    assert out["data"]["state"] == "FAILED" and out["data"]["reason_fa"] == fa.BUILD_DEPS
    assert "hunter2" not in str(out)  # the log tail is redacted before the model sees it
    conn = await asyncpg.connect(PG_TEST)
    try:
        status = await conn.fetchval("select status::text from deployment where id = $1::uuid", dep)
    finally:
        await conn.close()
    assert status == "failed"


@respx.mock
async def test_liara_release_id_finds_the_deployment(monkeypatch: pytest.MonkeyPatch) -> None:
    from deployar.tools.liara import watch
    from deployar.tools.registry import REGISTRY

    monkeypatch.setattr(watch, "POLL_S", 0)
    respx.get(f"{API}/v1/releases/6adb2510aa8f2ba374027585").respond(json={"release": {"state": "TIMEDOUT"}})
    respx.get(f"{API}/v2/releases/6adb2510aa8f2ba374027585/build-logs").respond(json={"buildOutput": []})

    ctx = await _ctx_with_connection()
    await _deployment(ctx, "6adb2510aa8f2ba374027585")  # the model passed Liara's id, not ours
    out = _payload(await REGISTRY.run(ctx, "watch_deployment", {"deployment_id": "6adb2510aa8f2ba374027585"}))
    assert out["status"] == "ok" and out["data"]["state"] == "TIMEDOUT", out


async def test_the_env_form_gets_the_project_uuid_even_when_the_model_sends_the_app_name() -> None:
    from dataclasses import replace

    from deployar.tools.liara import watch  # noqa: F401
    from deployar.tools.registry import REGISTRY

    cards: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        cards.append((kind, payload))

    ctx = replace(await _ctx_with_connection(), emit=emit)
    await REGISTRY.run(ctx, "request_env_values", {"project_id": "torob-gard", "keys": [{"key": "API_KEY"}]})
    assert cards == [
        ("env_request", {"project_id": str(ctx.project_id), "keys": [{"key": "API_KEY", "hint_fa": None}]})
    ]
