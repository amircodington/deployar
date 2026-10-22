"""package.json apps: platform, runtime, package manager, scripts, port, database drivers."""

import json
import re
from typing import Any

from deployar.analysis.detectors.common import MONGO_DEPS, MYSQL_DEPS, POSTGRES_DEPS, REDIS_DEPS, fact, join

LOCKFILES = (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"), ("package-lock.json", "npm"))


def detect(paths: set[str], files: dict[str, str], root: str) -> dict[str, Any] | None:
    path = join(root, "package.json")
    if path not in files:
        return None
    pkg = json.loads(files[path] or "{}")
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    scripts = pkg.get("scripts", {})
    out: dict[str, Any] = {"deps": set(deps), "evidence_file": path}

    if "next" in deps:
        out["platform"] = fact("next", f"{path}#dependencies.next")
        out["framework"] = {"name": "next", "version": deps["next"], "source": path}
    elif any(d in deps for d in ("react-scripts", "vite")) and "start" not in scripts:
        out["platform"] = fact("static", f"{path}#devDependencies")  # a static build, served as files
    else:
        out["platform"] = fact("node", path)

    pm = next((name for lock, name in LOCKFILES if join(root, lock) in paths), None)
    out["package_manager"] = pm or "npm"
    run = {"npm": "npm run", "pnpm": "pnpm", "yarn": "yarn", "bun": "bun run"}[out["package_manager"]]
    if "build" in scripts:
        out["build_cmd"] = f"{run} build"
    if "start" in scripts:
        out["start_cmd"] = f"{run} start"
        if m := re.search(r"(?:-p|--port)[ =](\d+)", scripts["start"]):
            out["port"] = fact(int(m.group(1)), f"{path}#scripts.start")

    for name in (".nvmrc", ".node-version"):
        if (p := join(root, name)) in files and files[p].strip():
            out["runtime"] = {"name": "node", "version": files[p].strip().lstrip("v"), "source": p}
            break
    else:
        if engine := pkg.get("engines", {}).get("node"):
            out["runtime"] = {"name": "node", "version": re.sub(r"[^\d.]", "", engine) or engine,
                              "source": f"{path}#engines.node"}  # fmt: skip
    if not pm:
        out["no_lockfile"] = True

    db: list[tuple[str, str]] = []
    for kind, names in (("postgres", POSTGRES_DEPS), ("mysql", MYSQL_DEPS), ("mongodb", MONGO_DEPS)):
        db += [(kind, f"{path}#dependencies.{d}") for d in names if d in deps and d != "@prisma/client"]
    out["db_hits"] = db
    out["cache_hits"] = [("redis", f"{path}#dependencies.{d}") for d in REDIS_DEPS if d in deps]
    return out
