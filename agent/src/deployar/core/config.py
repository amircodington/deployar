"""Settings from env / the repo-root .env (names in .env.example)."""

import re
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ROOT_ENV, extra="ignore")

    database_url: str = "postgresql+asyncpg://deployar:deployar@localhost:5432/deployar"
    redis_url: str = "redis://localhost:6379/0"

    deployar_token_keys: dict[str, SecretStr]
    deployar_token_key_version: int = 1
    approval_secret: SecretStr
    deployar_passphrase: SecretStr

    llm_backend: str = "claude"
    boxapi_base_url: str = "https://ai.boxapi.ir/ai/v1"
    boxapi_api_key: SecretStr = SecretStr("")
    boxapi_key_second: SecretStr = SecretStr("")  # used once the first key is out of credit
    boxapi_model: str = "anthropic/claude-haiku-5.5"
    boxapi_model_second: str = "openai/gpt-5.4-mini"  # the second key's BoxAPI allow list has only this model

    liara_api_base: str = "https://api.liara.ir"
    deployar_workdir: Path = Path("~/.deployar/work").expanduser()
    agent_url: str = "http://localhost:8800"

    @field_validator("database_url")
    @classmethod
    def _asyncpg(cls, v: str) -> str:
        # Liara (and create_database) hand out postgresql:// URLs; the agent's engine needs the asyncpg driver.
        return re.sub(r"^postgres(ql)?://", "postgresql+asyncpg://", v)

    @field_validator("deployar_workdir")
    @classmethod
    def _expand_home(cls, v: Path) -> Path:
        return v.expanduser()

    def token_keys(self) -> dict[str, str]:
        return {v: k.get_secret_value() for v, k in self.deployar_token_keys.items()}


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # required fields come from env
