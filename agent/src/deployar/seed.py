"""`deployar-seed --email you@example.com`: create the single user (idempotent)."""

import argparse
import asyncio

from sqlalchemy.dialects.postgresql import insert

from deployar.core.db import get_engine, get_sessionmaker
from deployar.models import User


async def seed_user(email: str) -> None:
    async with get_sessionmaker()() as session:
        await session.execute(insert(User).values(email=email, role="admin").on_conflict_do_nothing())
        await session.commit()
    await get_engine().dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the single Deployar user.")
    parser.add_argument("--email", required=True)
    asyncio.run(seed_user(parser.parse_args().email))
    print("seeded")
