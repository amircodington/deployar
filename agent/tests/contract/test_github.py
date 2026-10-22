"""analyze_repo against a mocked GitHub (B-09): fetch only deciding files, card out, reconnect on no access."""

import json
import uuid
from typing import Any

import asyncpg
import httpx
import respx
from pgtest import PG_TEST

GH = "https://api.github.com"
SHA = "8c17bc2" + "0" * 33


async def _ctx(emitted: list[tuple[str, dict[str, Any]]]) -> Any:
    from deployar.core.db import get_sessionmaker
    from deployar.tools.registry import ToolContext

    conn = await asyncpg.connect(PG_TEST)
    try:
        user = await conn.fetchval("""insert into "user" (email) values (gen_random_uuid() || '@t.ir') returning id""")
        run = await conn.fetchval("insert into run (kind, trigger) values ('chat', 'user_message') returning id")
    finally:
        await conn.close()

    async def emit(card_type: str, payload: dict[str, Any]) -> None:
        emitted.append((card_type, payload))

    return ToolContext(run_id=run, project_id=None, user_id=user, sessions=get_sessionmaker(), emit=emit)


def mock_repo(files: dict[str, str], extra_paths: list[str]) -> list[str]:
    respx.get(f"{GH}/repos/amox/torob-gard").respond(json={"default_branch": "main", "private": True})
    respx.get(f"{GH}/repos/amox/torob-gard/commits/main").respond(json={"sha": SHA})
    tree = [{"path": p, "type": "blob"} for p in [*files, *extra_paths]]
    respx.get(f"{GH}/repos/amox/torob-gard/git/trees/{SHA}").respond(json={"tree": tree})
    fetched: list[str] = []

    def content(request: httpx.Request) -> httpx.Response:
        path = request.url.path.split("/contents/", 1)[1]
        fetched.append(path)
        return httpx.Response(200, text=files[path])

    respx.get(url__regex=rf"{GH}/repos/amox/torob-gard/contents/.*").mock(side_effect=content)
    return fetched


@respx.mock
async def test_analyze_repo_reads_only_deciding_files_and_emits_the_card() -> None:
    from repo_fixtures import TOROB_GARD

    from deployar.tools.github import analyze  # noqa: F401
    from deployar.tools.registry import REGISTRY

    fetched = mock_repo(TOROB_GARD, ["api/catalog/models.py", "web/src/app/page.tsx", "docs/design/x.md"])
    emitted: list[tuple[str, dict[str, Any]]] = []
    out = await REGISTRY.run(await _ctx(emitted), "analyze_repo", {"repo": "https://github.com/amox/torob-gard"})
    body = json.loads(out["content"][0]["text"])

    assert body["status"] == "ok" and body["source"] == "github:amox/torob-gard@8c17bc2"
    assert sorted(a["root"] for a in body["data"]["apps"]) == ["api", "web"]
    assert body["data"]["database"]["kind"] == "postgres"
    assert "api/catalog/models.py" not in fetched and "docs/design/x.md" not in fetched  # code is never read
    assert emitted and emitted[0][0] == "repo_analysis" and emitted[0][1]["commit_sha"] == SHA


@respx.mock
async def test_private_repo_without_access_asks_to_reconnect() -> None:
    from deployar.tools.github import analyze  # noqa: F401
    from deployar.tools.registry import REGISTRY

    respx.get(f"{GH}/repos/amox/secret").respond(404)
    emitted: list[tuple[str, dict[str, Any]]] = []
    out = await REGISTRY.run(await _ctx(emitted), "analyze_repo", {"repo": "amox/secret"})
    assert out["is_error"] and json.loads(out["content"][0]["text"])["code"] == "github_no_access"
    assert emitted[0][0] == "github_reconnect"


@respx.mock
async def test_github_token_is_checked_and_stored_encrypted() -> None:
    from deployar.main import app

    token = "github_pat_" + "x" * 30
    respx.get(f"{GH}/user").respond(json={"login": "amircodington"})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post("/api/session", json={"passphrase": "p"})
        user_id = uuid.UUID(login.json()["user_id"])
        r = await client.post("/api/connections/github", json={"token": token})
        assert r.status_code == 200 and r.json()["login"] == "amircodington" and token not in r.text
    conn = await asyncpg.connect(PG_TEST)
    try:
        blob = await conn.fetchval(
            "select token_ciphertext from github_connection where user_id = $1 and status = 'active'", user_id
        )
    finally:
        await conn.close()
    assert blob and token.encode() not in blob
