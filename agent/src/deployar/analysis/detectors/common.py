"""Shared shapes for detectors: every fact is {value, source}; nothing is guessed without a file."""

import re
from typing import Any

Fact = dict[str, Any]

POSTGRES_DEPS = ("psycopg", "psycopg2", "asyncpg", "pg", "postgres", "@prisma/client")
MYSQL_DEPS = ("mysqlclient", "pymysql", "mysql2", "mysql")
MONGO_DEPS = ("mongoose", "mongodb", "pymongo", "motor")
REDIS_DEPS = ("redis", "ioredis", "celery")


def fact(value: Any, source: str) -> Fact:
    return {"value": value, "source": source}


def join(root: str, name: str) -> str:
    return name if root == "." else f"{root}/{name}"


def dep_names(spec_list: list[str]) -> set[str]:
    """`django>=5.2` / `psycopg[binary]` → `django` / `psycopg`."""
    return {re.split(r"[\[<>=!~ ;]", s.strip(), maxsplit=1)[0].lower() for s in spec_list if s.strip()}


def warn(code: str, message_fa: str, source: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"code": code, "message_fa": message_fa}
    if source:
        out["source"] = source
    return out
