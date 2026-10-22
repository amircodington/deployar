"""arq worker settings. Jobs land in worker/jobs/ (B-12, B-18, B-23)."""

import os
from typing import Any

from arq.connections import RedisSettings


async def ping(ctx: dict[str, Any]) -> str:
    # arq refuses to start with no functions; this one also lets a test enqueue a no-op.
    return "pong"


class WorkerSettings:
    functions = [ping]
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
