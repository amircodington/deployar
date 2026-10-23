"""Settings normalisation: a Liara postgres URL works as-is for the agent's async engine."""

import pytest

from deployar.core.config import Settings


@pytest.mark.parametrize("url", ["postgresql://u:p@db:5432/x", "postgres://u:p@db:5432/x",
                                 "postgresql+asyncpg://u:p@db:5432/x"])  # fmt: skip
def test_database_url_gets_the_asyncpg_driver(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", url)
    assert Settings().database_url == "postgresql+asyncpg://u:p@db:5432/x"  # type: ignore[call-arg]
