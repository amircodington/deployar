"""Runs API + SSE contract (B-06), driven by a fake LLM through the real gate, registry and event bus."""

import asyncio
import base64
import json
import os
import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from pgtest import PG_TEST, REDIS_TEST, TEST_URL_STR, fresh_schema

PASSPHRASE = "test-passphrase"


@pytest.fixture(scope="module", autouse=True)
def env() -> Iterator[None]:
    fresh_schema()
    saved = {k: os.environ.get(k) for k in ("DATABASE_URL", "REDIS_URL", "DEPLOYAR_PASSPHRASE", "APPROVAL_SECRET")}
    os.environ.update({
        "DATABASE_URL": TEST_URL_STR, "REDIS_URL": REDIS_TEST, "DEPLOYAR_PASSPHRASE": PASSPHRASE,
        "APPROVAL_SECRET": base64.b64encode(os.urandom(32)).decode(),
    })  # fmt: skip
    _clear_caches()
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    _clear_caches()


def _clear_caches() -> None:
    from deployar.api import deps
    from deployar.core import config, db

    for f in (config.get_settings, db.get_engine, db.get_sessionmaker, deps.get_redis, deps.get_runtime):
        f.cache_clear()


async def _project_for_first_user() -> uuid.UUID:
    import asyncpg

    conn = await asyncpg.connect(PG_TEST)
    try:
        user = await conn.fetchval("""insert into "user" (email, role) values ('mohammad@deployar.ir', 'admin')
                                      on conflict (email) do update set role = 'admin' returning id""")
        lc = await conn.fetchval(
            "insert into liara_connection (user_id, token_ciphertext, key_version, token_last4) "
            "values ($1, '\\x00', 1, 'abcd') on conflict do nothing returning id",
            user,
        ) or await conn.fetchval("select id from liara_connection where user_id = $1", user)
        return await conn.fetchval(
            "insert into project (user_id, liara_connection_id, name) values ($1, $2, 'ترب‌گرد') returning id", user, lc
        )
    finally:
        await conn.close()


def parse_sse(body: str) -> list[tuple[str, str, dict[str, Any]]]:
    events = []
    for block in body.split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line and not line.startswith(":"))
        if "event" in fields:
            events.append((fields["id"], fields["event"], json.loads(fields["data"])))
    return events


async def test_run_streams_events_and_replays_after_last_event_id() -> None:
    from deployar.api.deps import get_runtime
    from deployar.llm.fake_backend import FakeBackend, demo_registry
    from deployar.main import app
    from deployar.runtime.events import EVENT_MODELS, Envelope

    project_id = await _project_for_first_user()
    rt = get_runtime()
    rt.llm, rt.registry = FakeBackend(), demo_registry()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # every route but health and login needs the session cookie
        assert (await client.post("/api/runs", json={"text": "x"})).status_code == 401
        assert (await client.post("/api/session", json={"passphrase": "wrong"})).status_code == 401
        assert (await client.post("/api/session", json={"passphrase": PASSPHRASE})).status_code == 200

        r = await client.post("/api/runs", json={"text": "اپ را ری‌استارت کن", "project_id": str(project_id)})
        assert r.status_code == 200, r.text
        run_id = r.json()["run_id"]
        run = (await client.get(f"/api/runs/{run_id}")).json()
        assert [s["key"] for s in run["steps"]] == ["answer"]

        stream = asyncio.create_task(client.get(f"/api/runs/{run_id}/events"))
        # act as the user: wait for the approval card in the stream, then approve it with its signature
        card = None
        for _ in range(200):
            for _id, env in await rt.bus.read(uuid.UUID(run_id), "0", block_ms=50):
                if env.type == "approval.requested":
                    card = env.data
            if card:
                break
        assert card, "no approval.requested event"
        d = await client.post(f"/api/approvals/{card['approval_id']}/decision",
                              json={"decision": "approve", "signature": card["signature"]})  # fmt: skip
        assert d.json() == {"status": "approved"}

        events = parse_sse((await asyncio.wait_for(stream, 10)).text)
        types = [t for _, t, _ in events]
        for expected in ("run.started", "message.delta", "tool.called", "approval.requested", "run.done"):
            assert expected in types, f"{expected} missing from {types}"
        assert types[0] == "run.started" and types[-1] == "run.done"
        assert events[-1][2]["data"]["status"] == "succeeded"
        for _, t, payload in events:  # every payload validates against its model
            env = Envelope.model_validate(payload)
            EVENT_MODELS[t].model_validate(env.data)
        seqs = [p["seq"] for _, _, p in events]
        assert seqs == sorted(seqs)

        # reconnect after the third event: exactly the rest is replayed
        replay = parse_sse((await client.get(f"/api/runs/{run_id}/events",
                                             headers={"Last-Event-ID": events[2][0]})).text)  # fmt: skip
        assert [e[0] for e in replay] == [e[0] for e in events[3:]]

        final = (await client.get(f"/api/runs/{run_id}")).json()
        assert final["status"] == "succeeded" and final["steps"][0]["status"] == "done"
