"""Tool result types (ARCHITECTURE.md §11, ADR 9). A missing API capability is a result, never an exception."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class Ok:
    """Every value the UI shows carries where it came from and when (hard rule 3)."""

    data: Any
    source: str | None = None
    observed_at: str = field(default_factory=_now)


@dataclass(frozen=True)
class Limitation:
    code: str
    message_fa: str
    workaround_fa: str | None = None
    kind: Literal["api_missing", "plan_restricted", "human_only"] = "api_missing"


@dataclass(frozen=True)
class ToolError:
    code: str
    message_fa: str
    retryable: bool = False


ToolResult = Ok | Limitation | ToolError


def to_payload(result: ToolResult) -> dict[str, Any]:
    """The JSON the model receives (after redaction)."""
    if isinstance(result, Ok):
        return {"status": "ok", "data": result.data, "source": result.source, "observed_at": result.observed_at}
    if isinstance(result, Limitation):
        return {"status": "limitation", "code": result.code, "message_fa": result.message_fa,
                "workaround_fa": result.workaround_fa}  # fmt: skip
    return {"status": "error", "code": result.code, "message_fa": result.message_fa, "retryable": result.retryable}
