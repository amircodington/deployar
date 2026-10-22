"""Contract tests run the real app against the throwaway database, Redis db 15 and test keys."""

import base64
import json
import os
from collections.abc import Iterator

import pytest
from pgtest import REDIS_TEST, TEST_URL_STR, fresh_schema

PASSPHRASE = "p"


def clear_caches() -> None:
    from deployar.api import deps
    from deployar.core import config, crypto, db

    for f in (config.get_settings, db.get_engine, db.get_sessionmaker, deps.get_redis, deps.get_runtime,
              crypto.get_vault):  # fmt: skip
        f.cache_clear()


@pytest.fixture(scope="module", autouse=True)
def agent_env() -> Iterator[None]:
    fresh_schema()
    keys = {
        "DATABASE_URL": TEST_URL_STR, "REDIS_URL": REDIS_TEST, "DEPLOYAR_PASSPHRASE": PASSPHRASE,
        "APPROVAL_SECRET": base64.b64encode(os.urandom(32)).decode(),
        "DEPLOYAR_TOKEN_KEYS": json.dumps({"1": base64.b64encode(os.urandom(32)).decode()}),
        "DEPLOYAR_TOKEN_KEY_VERSION": "1", "LIARA_API_BASE": "https://api.liara.ir", "LLM_BACKEND": "claude",
    }  # fmt: skip
    saved = {k: os.environ.get(k) for k in keys}
    os.environ.update(keys)
    clear_caches()
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    clear_caches()
