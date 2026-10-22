"""propose_plan stores one open proposal per project and emits the plan card (B-10)."""

import json
import uuid
from pathlib import Path
from typing import Any

import asyncpg
import respx
from pgtest import PG_TEST
from repo_fixtures import TOROB_GARD

API = "https://api.liara.ir"
CASSETTES = Path(__file__).resolve().parents[1] / "cassettes" / "liara"


async def _ctx(emitted: list[tuple[str, dict[str, Any]]]) -> Any:
    from deployar.analysis.analyze import DETECTOR_VERSION, Repo, analyze
    from deployar.core.crypto import aad_for, get_vault
    from deployar.core.db import get_sessionmaker
    from deployar.tools.registry import ToolContext

    conn = await asyncpg.connect(PG_TEST)
    try:
        user = await conn.fetchval("""insert into "user" (email) values (gen_random_uuid() || '@t.ir') returning id""")
        cid = uuid.uuid4()
        blob, v = get_vault().encrypt("liara-token-xxxxxxxxxxxxxxxx", aad_for("liara_connection", cid, user))
        await conn.execute("insert into liara_connection (id, user_id, token_ciphertext, key_version, token_last4) "
                           "values ($1, $2, $3, $4, 'xxxx')", cid, user, blob, v)  # fmt: skip
        project = await conn.fetchval(
            "insert into project (user_id, liara_connection_id, name, repo_full_name) "
            "values ($1, $2, 'ترب‌گرد', 'amox/torob-gard') returning id",
            user,
            cid,
        )
        await conn.execute("insert into repo_analysis (project_id, commit_sha, detector_version, detected) "
                           "values ($1, $2, $3, $4)", project, "a" * 40, DETECTOR_VERSION,
                           json.dumps(analyze(Repo.from_files(TOROB_GARD))))  # fmt: skip
        run = await conn.fetchval("insert into run (project_id, kind, trigger) values ($1, 'deploy', 'user_message') "
                                  "returning id", project)  # fmt: skip
    finally:
        await conn.close()

    async def emit(t: str, p: dict[str, Any]) -> None:
        emitted.append((t, p))

    return ToolContext(run_id=run, project_id=project, user_id=user, sessions=get_sessionmaker(), emit=emit)


@respx.mock
async def test_plan_card_with_price_source_time_and_balance() -> None:
    from deployar.tools.liara import plan  # noqa: F401
    from deployar.tools.registry import REGISTRY

    respx.get(f"{API}/v1/billing").respond(json=json.loads((CASSETTES / "billing.json").read_text()))
    respx.get(f"{API}/v1/me").respond(json=json.loads((CASSETTES / "me.json").read_text()))
    emitted: list[tuple[str, dict[str, Any]]] = []
    ctx = await _ctx(emitted)
    for _ in range(2):  # a second proposal supersedes the first
        out = json.loads((await REGISTRY.run(ctx, "propose_plan", {}))["content"][0]["text"])
    assert out["status"] == "ok" and out["source"] == "liara:/v1/me"
    card = emitted[-1][1]
    assert emitted[-1][0] == "plan_proposal"
    assert card["balance_toman"] == 2_000_000 and card["prices_fetched_at"] and card["plan_ids_confirmed"]
    assert [i["plan_id"] for i in card["items"]] == ["ir-medium", "ir-medium", "ir-medium"]
    assert card["totals"]["toman_hour"] == 3 * 2292
    conn = await asyncpg.connect(PG_TEST)
    try:
        rows = await conn.fetch("select status::text from plan_proposal where project_id = $1", ctx.project_id)
    finally:
        await conn.close()
    assert sorted(r["status"] for r in rows) == ["proposed", "superseded"]
