"""Dashboard and monitor endpoints (UI reads): sourced blocks, summed series, secrets never returned."""

import json

import asyncpg
import httpx
import respx
from pgtest import PG_TEST
from test_liara_client import API, TOKEN, cassette


@respx.mock
async def test_dashboard_and_monitor() -> None:
    from deployar.main import app

    respx.get(f"{API}/v1/billing").respond(json=cassette("billing"))
    respx.get(f"{API}/v1/me").respond(json=cassette("me"))
    app_row = {"project_id": "torob-gard", "type": "docker", "status": "ACTIVE", "planID": "ir-medium",
               "isDeployed": True}  # fmt: skip
    respx.get(f"{API}/v1/projects").respond(json={"projects": [app_row]})
    respx.get(f"{API}/v1/projects/torob-gard").respond(json=cassette("project"))
    respx.get(f"{API}/v2/projects/torob-gard/logs").respond(json=cassette("logs"))
    respx.get(f"{API}/v1/projects/torob-gard/releases").respond(json=cassette("releases"))
    respx.get(url__regex=rf"{API}/v1/projects/torob-gard/metrics/(memory|cpu)").respond(json={"result": [
        {"applet": "web", "values": [[1, "2"], [2, "3"]]}, {"applet": "worker", "values": [[1, "5"]]}]})  # fmt: skip

    conn = await asyncpg.connect(PG_TEST)
    await conn.execute("""insert into "user" (email) values ('owner@deployar.ir') on conflict do nothing""")
    await conn.close()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/session", json={"passphrase": "p"})
        connected = await client.post("/api/connections/liara", json={"token": TOKEN, "team_id": "team-7"})
        assert connected.status_code == 200
        d = (await client.get("/api/dashboard")).json()
        assert d["liara"]["balance"] == {**d["liara"]["balance"], "toman": 2000000, "source": "liara:/v1/billing"}
        assert d["liara"]["apps"]["items"][0]["name"] == "torob-gard"

        m = await client.get("/api/apps/torob-gard/monitor?minutes=30")
        assert m.status_code == 200, m.text
        body = m.json()
        assert body["metrics"]["memory"] == [[1, 7.0], [2, 3.0]]  # applets summed per timestamp
        assert body["logs"]["source"].endswith("/logs") and body["releases"]["current"] == "r2"
        assert "hunter2" not in m.text and TOKEN not in json.dumps(d)

        assert (await client.get("/api/apps/Bad_Name/monitor")).status_code == 422
