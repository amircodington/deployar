"""`.env.example`: which variables the app needs, which are secrets, and who fills each one."""

import re
from typing import Any

SECRETISH = re.compile(r"SECRET|KEY|TOKEN|PASSWORD|PASS\b|PRIVATE|CREDENTIAL", re.I)
CANDIDATES = (".env.example", ".env.sample", ".env.template", "env.example")


def fill_for(key: str) -> str:
    if key == "DATABASE_URL" or key.startswith("DB_"):
        return "from_created_db"
    if key == "REDIS_URL":
        return "from_created_redis"
    if re.search(r"SECRET_KEY$|^APP_KEY$", key):
        return "generate"
    return "ask_user"


def detect(files: dict[str, str]) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path in sorted(files):
        if path.rsplit("/", 1)[-1] not in CANDIDATES:
            continue
        for n, line in enumerate(files[path].splitlines(), 1):
            m = re.match(r"\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*)$", line)
            if not m or m.group(1) in found:
                continue
            key, value = m.group(1), m.group(2).strip()
            found[key] = {
                "key": key,
                "secret": bool(SECRETISH.search(key) or re.search(r"://[^/\s:]+:[^@\s]+@", value)),
                "fill": fill_for(key),
                "has_example_value": bool(value),
                "source": f"{path}:{n}",
            }
    return list(found.values())
