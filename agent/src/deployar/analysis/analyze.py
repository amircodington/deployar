"""analyze_repo: deterministic detectors first, the LLM only explains (ADR 8).

Finds every deployable app in the repo (a monorepo gives several), the database it needs (kind,
extensions) and the env vars, each with the file that proves it.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from deployar import messages_fa as fa
from deployar.analysis.detectors import docker, env_example, nextjs, node, prisma, python
from deployar.analysis.detectors.common import join, warn

DETECTOR_VERSION = "detect@1"
APP_MARKERS = ("package.json", "pyproject.toml", "requirements.txt", "manage.py", "composer.json", "Dockerfile",
               "index.html")  # fmt: skip
SKIP_DIRS = {"node_modules", ".git", "docs", "doc", "test", "tests", "examples", ".github", "vendor", "public"}
# Files whose content decides the answer; the GitHub client fetches only these.
INTERESTING = (*APP_MARKERS, ".nvmrc", ".node-version", ".python-version", "prisma/schema.prisma", "settings.py",
               "docker-compose.yml", "docker-compose.yaml", "compose.yaml", ".env.example", ".env.sample",
               ".env.template", "liara.json")  # fmt: skip


@dataclass
class Repo:
    paths: set[str]
    files: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_files(cls, files: dict[str, str]) -> "Repo":
        return cls(set(files), files)


def wanted(path: str) -> bool:
    parts = path.split("/")
    return (
        len(parts) <= 4
        and not SKIP_DIRS & set(parts[:-1])
        and (parts[-1] in INTERESTING or path.endswith(("prisma/schema.prisma", "settings.py")))
    )


def app_roots(repo: Repo) -> list[str]:
    roots = set()
    for p in repo.paths:
        parts = p.split("/")
        if parts[-1] in APP_MARKERS and len(parts) <= 3 and not SKIP_DIRS & set(parts[:-1]):
            roots.add("/".join(parts[:-1]) or ".")
    # A Dockerfile that is only a database image (e.g. deploy/db) is not an app.
    roots = {r for r in roots if not _only_db_image(repo, r)}
    if "." in roots and len(roots) > 1 and not _has_app_manifest(repo, "."):
        if _builds_subroots(repo, roots) or _prebuilt_image(repo):
            return ["."]  # one root Dockerfile that builds the sub-apps into a single image, or pulls it
        roots.discard(".")  # a root Dockerfile/compose for local dev in a monorepo
    # Django settings packages live under the app root; keep the shallowest root only.
    return sorted(r for r in roots if not any(r != o and r.startswith(f"{o}/") for o in roots if o != "."))


def _has_app_manifest(repo: Repo, root: str) -> bool:
    return any(join(root, m) in repo.files for m in ("package.json", "pyproject.toml", "requirements.txt", "manage.py",
                                                    "composer.json", "index.html"))  # fmt: skip


def _builds_subroots(repo: Repo, roots: set[str]) -> bool:
    text = repo.files.get("Dockerfile", "")
    return any(re.search(rf"^\s*COPY\s+(--\S+\s+)*\.?/?{re.escape(r)}/", text, re.M | re.I) for r in roots - {"."})


def _prebuilt_image(repo: Repo) -> bool:
    """A root Dockerfile with no COPY/ADD only pulls an image built elsewhere (CI), so it is the deploy target."""
    text = repo.files.get("Dockerfile", "")
    return bool(text) and not docker.database_image(text) and not re.search(r"^\s*(COPY|ADD)\s", text, re.M | re.I)


def _only_db_image(repo: Repo, root: str) -> bool:
    dockerfile = join(root, "Dockerfile")
    return (
        dockerfile in repo.files
        and not _has_app_manifest(repo, root)
        and bool(docker.database_image(repo.files[dockerfile]))
    )


def analyze(repo: Repo) -> dict[str, Any]:
    apps: list[dict[str, Any]] = []
    db_hits: list[tuple[str, str]] = []
    cache_hits: list[tuple[str, str]] = []
    extensions: list[tuple[str, str]] = []
    orm: str | None = None
    warnings: list[dict[str, Any]] = []

    for root in app_roots(repo):
        app: dict[str, Any] = {"root": root, "warnings": []}
        lang = node.detect(repo.paths, repo.files, root) or python.detect(repo.paths, repo.files, root)
        dock = docker.detect(repo.files, root)
        composer = repo.files.get(join(root, "composer.json"))
        if lang:
            for k in ("platform", "framework", "runtime", "package_manager", "build_cmd", "start_cmd", "port",
                      "ram_estimate_mb"):  # fmt: skip
                if k in lang:
                    app[k] = lang[k]
            app["warnings"] += lang.get("warnings", [])
            db_hits += lang.get("db_hits", [])
            cache_hits += lang.get("cache_hits", [])
            extensions += lang.get("extensions", [])
            if lang.get("no_lockfile"):
                app["warnings"].append(warn("no_lockfile", fa.WARN_NO_LOCKFILE))
        elif composer is not None:
            laravel = "laravel/framework" in composer
            app["platform"] = {"value": "laravel" if laravel else "php", "source": join(root, "composer.json")}
        elif join(root, "index.html") in repo.paths and not dock:
            app["platform"] = {"value": "static", "source": join(root, "index.html")}
            app["ram_estimate_mb"] = {"value": 256, "basis": "static files; rule ram.static.v1"}
        if dock:
            app["dockerfile"] = dock["dockerfile"]
            app["warnings"] += dock["warnings"]
            if "port" in dock:
                app["port"] = dock["port"]
            # Docker when the language platform can't provide the system libraries, or nothing else fits.
            needs_libs = bool(lang and lang.get("system_libs")) or dock.get("installs_system_packages")
            if needs_libs or "platform" not in app:
                app["platform"] = {"value": "docker", "source": dock["dockerfile"]}
        if p := prisma.detect(repo.files, root):
            db_hits.insert(0, (p["kind"], p["source"]))
            orm = "prisma"
        nextjs.refine(app)
        app.setdefault("ram_estimate_mb", {"value": 512, "basis": "default for an unknown stack; rule ram.default.v1"})
        if "platform" in app:
            apps.append(app)

    # Database images in compose/Dockerfiles count as evidence (and carry extensions like pgvector).
    for path, text in sorted(repo.files.items()):
        name = path.rsplit("/", 1)[-1]
        if name == "Dockerfile" and (kind := docker.database_image(text)):
            if kind == "redis":
                cache_hits.append(("redis", path))
            else:
                db_hits.append((kind, path))
            if "postgis" in docker.base_image(text):
                extensions.append(("postgis", path))
            if "pgvector" in text:
                extensions.append(("pgvector", path))
        elif name in ("docker-compose.yml", "docker-compose.yaml", "compose.yaml"):
            for image in re.findall(r"image:\s*['\"]?([\w./-]+)", text):
                kind = docker.database_image(f"FROM {image}")
                if kind == "redis":
                    cache_hits.append(("redis", f"{path}#{image}"))
                elif kind:
                    db_hits.append((kind, f"{path}#{image}"))

    env_vars = env_example.detect(repo.files)
    if not db_hits:
        for e in env_vars:  # Laravel-style DB_CONNECTION=mysql
            if e["key"] == "DB_CONNECTION":
                line = repo.files[e["source"].rsplit(":", 1)[0]].splitlines()[int(e["source"].rsplit(":", 1)[1]) - 1]
                value = line.split("=", 1)[1].strip().lower()
                kind = {"mysql": "mysql", "mariadb": "mysql", "pgsql": "postgres", "mongodb": "mongodb"}.get(value)
                if kind:
                    db_hits.append((kind, e["source"]))

    result: dict[str, Any] = {"detector_version": DETECTOR_VERSION, "apps": apps, "env_vars": env_vars,
                              "warnings": warnings}  # fmt: skip
    if db_hits:
        kind = db_hits[0][0]
        result["database"] = {
            "kind": kind,
            "orm": orm,
            "extensions": sorted({e for e, _ in extensions}),
            "evidence": list(dict.fromkeys([src for k, src in db_hits if k == kind] + [src for _, src in extensions])),
        }
    if cache_hits:
        result["cache"] = {"kind": "redis", "evidence": list(dict.fromkeys(src for _, src in cache_hits))}
    if not apps:
        warnings.append(warn("no_app_found", fa.WARN_NO_APP))
    elif len(apps) > 1:
        warnings.append(warn("monorepo", fa.WARN_MONOREPO.format(n=len(apps))))
    return result
