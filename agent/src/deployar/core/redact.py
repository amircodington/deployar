"""Scrub secrets from anything that leaves the process: log lines, tool results, SSE frames.

Three layers: keys whose name looks secret are masked; strings equal to a token this process has
decrypted are removed wherever they appear; common secret shapes (URL passwords, *_SECRET=, Bearer)
are masked.
"""

import re
from collections.abc import Mapping, MutableMapping
from typing import Any

MASK = "<redacted>"
_SECRET_KEY = re.compile(r"token|authorization|secret|password|cookie", re.IGNORECASE)
_SHAPES = [
    (re.compile(r"(\w+://[^:/@\s]+:)[^@\s]+@"), r"\1***@"),
    (re.compile(r"\b([A-Z0-9_]*(?:SECRET|KEY|TOKEN|PASSWORD|PASSPHRASE)[A-Z0-9_]*\s*[=:]\s*)\S+"), r"\1***"),
    (re.compile(r"(Bearer\s+)\S+", re.IGNORECASE), r"\1***"),
]
# shortcut: grows for the process lifetime; fine for one user with a few tokens, revisit if multi-tenant.
_known: set[str] = set()


def register_secret(value: str) -> None:
    """Called by the vault on every decrypt; short values are skipped to avoid scrubbing common words."""
    if len(value) >= 8:
        _known.add(value)


def _is_secret_key(key: object) -> bool:
    return isinstance(key, str) and bool(_SECRET_KEY.search(key))


def redact(value: Any) -> Any:
    if isinstance(value, str):
        for secret in _known:
            value = value.replace(secret, MASK)
        for pattern, repl in _SHAPES:
            value = pattern.sub(repl, value)
        return value
    if isinstance(value, dict):
        return {k: MASK if _is_secret_key(k) else redact(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return type(value)(redact(v) for v in value)
    return value


def redact_processor(_logger: Any, _method: str, event_dict: MutableMapping[str, Any]) -> Mapping[str, Any]:
    """structlog processor; runs last before rendering."""
    cleaned: Mapping[str, Any] = redact(dict(event_dict))
    return cleaned
