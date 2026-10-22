"""prisma/schema.prisma: the datasource provider is the database."""

import re
from typing import Any

from deployar.analysis.detectors.common import join

PROVIDERS = {"postgresql": "postgres", "mysql": "mysql", "mongodb": "mongodb", "sqlite": "sqlite"}


def detect(files: dict[str, str], root: str) -> dict[str, Any] | None:
    path = join(root, "prisma/schema.prisma")
    if path not in files:
        return None
    m = re.search(r'provider\s*=\s*"(\w+)"', files[path].split("datasource", 1)[-1])
    if not m or m.group(1) not in PROVIDERS:
        return None
    return {"kind": PROVIDERS[m.group(1)], "orm": "prisma", "source": f"{path}#datasource.provider"}
