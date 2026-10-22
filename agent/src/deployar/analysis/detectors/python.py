"""Python apps: Django / Flask / FastAPI, runtime, deps, Django settings (GIS, DEBUG)."""

import re
import tomllib
from typing import Any

from deployar.analysis.detectors.common import (
    MONGO_DEPS,
    MYSQL_DEPS,
    POSTGRES_DEPS,
    REDIS_DEPS,
    dep_names,
    fact,
    join,
    warn,
)


def detect(paths: set[str], files: dict[str, str], root: str) -> dict[str, Any] | None:
    pyproject, reqs, manage = join(root, "pyproject.toml"), join(root, "requirements.txt"), join(root, "manage.py")
    if not any(p in files for p in (pyproject, reqs, manage)):
        return None
    out: dict[str, Any] = {"warnings": []}
    deps: set[str] = set()
    source = pyproject if pyproject in files else reqs
    if pyproject in files:
        data = tomllib.loads(files[pyproject])
        project = data.get("project", {})
        deps |= dep_names(project.get("dependencies", []))
        if rp := project.get("requires-python"):
            out["runtime"] = {"name": "python", "version": re.sub(r"[^\d.]", "", rp),
                              "source": f"{pyproject}#requires-python"}  # fmt: skip
    if reqs in files:
        deps |= dep_names(files[reqs].splitlines())
    if (p := join(root, ".python-version")) in files:
        out["runtime"] = {"name": "python", "version": files[p].strip(), "source": p}
    out["deps"] = deps
    out["evidence_file"] = source

    if "django" in deps or manage in files:
        out["framework"] = {"name": "django", "source": manage if manage in files else source}
        out["platform"] = fact("django", out["framework"]["source"])
        out["ram_estimate_mb"] = {"value": 512, "basis": "gunicorn + django baseline; rule ram.django.v1"}
    elif "flask" in deps:
        out["framework"] = {"name": "flask", "source": source}
        out["platform"] = fact("flask", source)
    else:
        out["platform"] = fact("python", source)

    db: list[tuple[str, str]] = []
    for kind, names in (("postgres", POSTGRES_DEPS), ("mysql", MYSQL_DEPS), ("mongodb", MONGO_DEPS)):
        db += [(kind, f"{source}#{d}") for d in names if d in deps]
    out["cache_hits"] = [("redis", f"{source}#{d}") for d in REDIS_DEPS if d in deps]
    out["extensions"] = []
    if "pgvector" in deps:
        out["extensions"].append(("pgvector", f"{source}#pgvector"))

    settings = next((p for p in sorted(files) if p.startswith(f"{root}/" if root != "." else "")
                     and p.endswith("settings.py")), None)  # fmt: skip
    if settings:
        text = files[settings]
        if "django.contrib.gis" in text or "postgis" in text:
            out["extensions"].append(("postgis", settings))
            out["system_libs"] = ("gdal", settings)
            db.append(("postgres", f"{settings}#DATABASES"))
            out["ram_estimate_mb"] = {"value": 1024, "basis": "django + GDAL/GEOS; rule ram.django.gis.v1"}
        elif "postgresql" in text:
            db.append(("postgres", f"{settings}#DATABASES"))
        if re.search(r'DEBUG\s*=\s*os\.environ\.get\(\s*["\']DEBUG["\']\s*,\s*["\'](1|True|true)', text):
            out["warnings"].append(
                warn("debug_default_on", "پیش‌فرض DEBUG روشن است؛ روی لیارا DEBUG=0 می‌گذارم.", settings)
            )
    out["db_hits"] = db
    return out
