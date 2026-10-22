"""`make push-test`: read-only checks against the real Liara account (costs nothing).

Uses the connection pasted in Settings > Connections (dev database, real .env keys). Anything that
creates or changes resources on Liara spends balance and needs Mohammad's yes first (BUILD.md, B-08).
"""

import pytest
from sqlalchemy import select

from deployar.clients.liara import LiaraClient
from deployar.core.crypto import aad_for, get_vault
from deployar.core.db import get_sessionmaker
from deployar.models import LiaraConnection

pytestmark = pytest.mark.live


async def test_reads_the_real_balance() -> None:
    async with get_sessionmaker()() as s:
        conn = await s.scalar(select(LiaraConnection).where(LiaraConnection.status == "active"))
    if conn is None:
        pytest.skip("no Liara connection yet: paste a token in Settings > Connections")
    token = get_vault().decrypt(
        conn.token_ciphertext, conn.key_version, aad_for("liara_connection", conn.id, conn.user_id)
    )
    async with LiaraClient(token, conn.team_id) as c:
        billing = await c.billing()
        me = await c.me_summary()
    print("billing keys:", sorted(billing), "| plans keys:", sorted((me.get("plans") or {}).keys()))
    assert billing, "empty /v1/billing response"
