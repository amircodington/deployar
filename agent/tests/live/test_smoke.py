"""B-11 live smoke: create a tiny static app, set an env var, deploy hello-world, read logs, delete it.

SPENDS BALANCE (one ir-small app for a few minutes, about 100 toman). Run by hand with Mohammad present:
    DEPLOYAR_SMOKE=1 uv run pytest -m live tests/live/test_smoke.py -s
"""

import asyncio
import io
import os
import tarfile
import time

import pytest
from sqlalchemy import select

from deployar.clients.liara import LiaraClient
from deployar.core.crypto import aad_for, get_vault
from deployar.core.db import get_sessionmaker
from deployar.models import LiaraConnection

pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get("DEPLOYAR_SMOKE") != "1", reason="spends balance")]


def hello() -> bytes:
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as t:
        data = b"<!doctype html><title>deployar smoke</title><p>salam</p>"
        info = tarfile.TarInfo("index.html")
        info.size = len(data)
        t.addfile(info, io.BytesIO(data))
    return out.getvalue()


async def test_create_env_deploy_logs_delete() -> None:
    async with get_sessionmaker()() as s:
        conn = await s.scalar(select(LiaraConnection).where(LiaraConnection.status == "active"))
    assert conn, "paste a token in Settings > Connections first"
    token = get_vault().decrypt(conn.token_ciphertext, conn.key_version,
                                aad_for("liara_connection", conn.id, conn.user_id))  # fmt: skip
    name = f"deployar-smoke-{int(time.time()) % 100000}"
    async with LiaraClient(token, conn.team_id) as c:
        nets = [n for n in await c.networks() if n.get("name") == "deployar"]
        if not nets:
            await c.create_network("deployar")
            nets = [n for n in await c.networks() if n.get("name") == "deployar"]
        await c.create_app(name, "static", "ir-small", nets[0]["_id"])
        try:
            await c.update_envs(name, [{"key": "SMOKE", "value": "1"}])
            source_id = await c.upload_source(name, hello())
            release_id = await c.create_release(name, {"sourceID": source_id, "port": 80, "type": "static"})
            state = ""
            for _ in range(60):
                state = (await c.release(release_id)).get("state", "")
                print("release", release_id, state)
                if state in ("READY", "FAILED", "CANCELED", "TIMEDOUT", "UNHEALTHY"):
                    break
                await asyncio.sleep(5)
            print("logs:", (await c.logs(name, int(time.time()) - 900))[-5:])
            assert state == "READY"
            assert "SMOKE" in (await c.project(name))["env_keys"]
        finally:
            await c.delete_app(name)
