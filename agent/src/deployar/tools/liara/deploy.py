"""Sensitive Liara tools (B-11). Each runs only after its approval (gate + registry + DB trigger).

Secrets never pass through the model: create_database stores DATABASE_URL encrypted and returns a
value_ref; set_env resolves refs (and generated keys) here, server-side.
"""

import asyncio
import io
import re
import secrets
import tarfile
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from sqlalchemy import select, update

from deployar import messages_fa as fa
from deployar.clients.github import GitHubClient, GitHubNoAccess, parse_repo
from deployar.core.errors import DeployarError
from deployar.core.redact import _is_secret_key
from deployar.models import Deployment, LiaraResource, Project, RepoAnalysis
from deployar.tools.github.analyze import github_token
from deployar.tools.liara.read import _guard, liara_client
from deployar.tools.project import resolve_project
from deployar.tools.registry import ToolContext, deployar_tool
from deployar.tools.results import Ok, ToolError, ToolResult
from deployar.tools.secrets import load_secret, store_secret

NETWORK = "deployar"
PLATFORMS = ["node", "next", "docker", "static", "laravel", "php", "python", "django", "flask", "react", "vue",
             "angular", "dotnet", "go"]  # fmt: skip
MAX_SOURCE = 256 * 1024 * 1024  # Liara's upload limit
# toman/hour read from /v1/me on 2026-10-22 (same ids for apps and DBs); only the approval card uses it
# g2 plans include the basic bundle Liara now requires on create (plan + bundle, toman per hour)
HOURLY = {"ir-small": 1319, "ir-medium": 2292, "standard-base": 4097, "standard-plus": 7361, "standard-pro": 7361,
          "pro": 12778, "pro-plus": 22222, "pro-max": 38889,
          "small-g2": 1042, "medium-g2": 1806, "standard-base-g2": 3195, "standard-plus-g2": 5729,
          "standard-pro-g2": 5729, "pro-g2": 10069}  # fmt: skip
PRICE_SOURCE = {"source": "liara:/v1/me", "observed_at": "2026-10-23T06:00:00+00:00"}
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{2,30}[a-z0-9]$")


def _monthly(plan_id: str | None) -> int | None:
    h = HOURLY.get(plan_id or "")
    return int(round(h * 720, -3)) if h else None


def _cost(plan_id: str | None) -> dict[str, Any]:
    m = _monthly(plan_id)
    return {"cost_delta_toman": m, "cost_source": PRICE_SOURCE} if m else {}


def _slug(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9-]", "-", text.lower())).strip("-")[:32]


async def _project(ctx: ToolContext, project_id: str | None = None) -> Project:
    pid = await resolve_project(ctx, project_id)
    if pid is None:
        raise DeployarError("no_project", fa.NO_PROJECT)
    async with ctx.sessions() as s:
        p = await s.scalar(select(Project).where(Project.id == pid, Project.user_id == ctx.user_id))
    if p is None:
        raise DeployarError("no_project", fa.NO_PROJECT)
    return p


async def _record(ctx: ToolContext, kind: str, name: str, project_id: uuid.UUID | None, **kw: Any) -> None:
    async with ctx.sessions.begin() as s:
        s.add(LiaraResource(user_id=ctx.user_id, project_id=project_id, kind=kind, name=name, run_id=ctx.run_id, **kw))


async def _network(ctx: ToolContext, c: Any) -> str:
    """The one private network Deployar puts apps and databases in, so they can reach each other."""
    for n in await c.networks():
        if n.get("name") == NETWORK:
            return str(n["_id"])
    await c.create_network(NETWORK)
    await _record(ctx, "network", NETWORK, None)
    for n in await c.networks():
        if n.get("name") == NETWORK:
            return str(n["_id"])
    raise DeployarError("liara_error", fa.LIARA_ERROR, "network not listed after create")


# --- create_app ------------------------------------------------------------------------------------


def _preview_app(a: dict[str, Any]) -> dict[str, Any]:
    label = a.get("name") or (a.get("app_root") or ".").strip("/")  # the repo's root is ".", not a name to show
    return {"title_fa": f"ساخت اپ {label if label != '.' else 'جدید'} روی لیارا ({a.get('plan_id')})",
            "why_fa": a.get("reason_fa"), "changes": {"platform": a.get("platform"), "plan": a.get("plan_id")},
            **_cost(a.get("plan_id"))}  # fmt: skip


@deployar_tool("create_app", group="liara", risk="sensitive", description=fa.CREATE_APP_DESC, preview=_preview_app,
               input_schema={"type": "object", "required": ["app_root", "platform", "plan_id"], "properties": {
                   "app_root": {"type": "string"}, "name": {"type": "string"},
                   "platform": {"type": "string", "enum": PLATFORMS}, "plan_id": {"type": "string"},
                   "reason_fa": {"type": "string"}}})  # fmt: skip
async def create_app(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        repo = await _project(ctx)
        root = (args.get("app_root") or ".").strip("/") or "."
        name = args.get("name") or _slug(f"{repo.name}-{root}" if root != "." else repo.name)
        if not NAME.match(name):
            return ToolError("bad_app_name", fa.LIARA_EXISTS)
        async with await liara_client(ctx) as c:
            net = await _network(ctx, c)
            await c.create_app(name, args["platform"], args["plan_id"], net)
        async with ctx.sessions.begin() as s:  # one project per app (ADR 11): the repo project or a sibling
            target = await s.scalar(select(Project).where(
                Project.user_id == ctx.user_id, Project.repo_full_name == repo.repo_full_name, Project.app_root == root,
                Project.archived_at.is_(None)))  # fmt: skip
            if target is None and root != "." and repo.app_root == "." and repo.liara_app_name is None:
                target = await s.get(Project, repo.id)  # the draft becomes this app
            if target is None:
                target = Project(user_id=ctx.user_id, liara_connection_id=repo.liara_connection_id,
                                 github_connection_id=repo.github_connection_id, name=f"{repo.name} · {root}",
                                 repo_full_name=repo.repo_full_name,
                                 repo_default_branch=repo.repo_default_branch)  # fmt: skip
                s.add(target)
            target.app_root, target.liara_app_name = root, name
            target.platform, target.plan_id = args["platform"], args["plan_id"]
            await s.flush()
            pid = target.id
        await _record(ctx, "app", name, pid, plan_id=args["plan_id"])
        return Ok({"project_id": str(pid), "app": name, "app_root": root, "url": f"https://{name}.liara.run",
                   "network": NETWORK}, source="liara:POST /v1/projects")  # fmt: skip

    return await _guard(run())


# --- create_database -------------------------------------------------------------------------------


def _preview_db(a: dict[str, Any]) -> dict[str, Any]:
    return {"title_fa": f"ساخت دیتابیس {a.get('kind', 'postgres')} روی لیارا ({a.get('plan_id')})",
            "why_fa": a.get("reason_fa"), "changes": {"kind": a.get("kind"), "plan": a.get("plan_id")},
            **_cost(a.get("plan_id"))}  # fmt: skip


def _pick_version(versions: list[dict[str, Any]], wanted: str | None) -> str:
    values = [str(v.get("value")) for v in versions if v.get("value")]
    if wanted and wanted in values:
        return wanted
    with_ext = [str(v["value"]) for v in versions if v.get("postgisValue") and str(v.get("value", "")).startswith("16")]
    return (with_ext or values or [wanted or "16"])[0]


@deployar_tool("create_database", group="liara", risk="sensitive", description=fa.CREATE_DB_DESC, preview=_preview_db,
               input_schema={"type": "object", "required": ["kind", "plan_id"], "properties": {
                   "kind": {"type": "string", "enum": ["postgres", "mysql", "mariadb", "mongodb", "redis"]},
                   "plan_id": {"type": "string"}, "version": {"type": "string"}, "name": {"type": "string"},
                   "reason_fa": {"type": "string"}}})  # fmt: skip
async def create_database(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        repo = await _project(ctx)
        kind = args["kind"]
        name = args.get("name") or _slug(f"{repo.name}-{'db' if kind != 'redis' else 'redis'}")
        async with await liara_client(ctx) as c:
            versions = ((await c.me_summary()).get("databaseVersions") or {}).get(kind) or []
            version = _pick_version(versions, args.get("version"))
            net = await _network(ctx, c)
            db_id = await c.create_database(name, kind, version, args["plan_id"], net)
            await _record(ctx, "database", name, repo.id, liara_id=db_id, plan_id=args["plan_id"])
            conn = await _wait_ready(c, db_id)
        if conn is None:
            return ToolError("db_not_ready", fa.DB_NOT_READY, retryable=True)
        key = "REDIS_URL" if kind == "redis" else "DATABASE_URL"
        ref = await store_secret(ctx, key, _url(kind, conn), "database", repo.id)
        async with ctx.sessions.begin() as s:
            await s.execute(update(Project).where(Project.id == repo.id).values(liara_db_name=name, db_kind=kind))
        return Ok({"database_id": db_id, "name": name, "kind": kind, "version": version, "env_key": key,
                   "value_ref": ref}, source="liara:POST /v1/databases")  # fmt: skip

    return await _guard(run())


async def _wait_ready(c: Any, db_id: str, tries: int = 36, every_s: float = 5.0) -> dict[str, Any] | None:
    for _ in range(tries):
        conn: dict[str, Any] = await c.database_connection(db_id)
        if conn.get("root_password") and str(conn.get("status", "")).upper() in ("RUNNING", "ACTIVE", "READY"):
            return conn
        await asyncio.sleep(every_s)
    return None


def _url(kind: str, conn: dict[str, Any]) -> str:
    """Built here so the password exists only inside this function and the vault."""
    host = conn.get("hostname")
    scheme = {"postgres": "postgresql", "mysql": "mysql", "mariadb": "mysql", "mongodb": "mongodb", "redis": "redis"}
    port = (
        conn.get("internalPort")
        or {"postgres": 5432, "mysql": 3306, "mariadb": 3306, "mongodb": 27017, "redis": 6379}[kind]
    )
    user = conn.get("username") or ("default" if kind == "redis" else "root")
    db = conn.get("dbName") or ("postgres" if kind == "postgres" else "")
    tail = f"/{db}" if db else ""
    return f"{scheme[kind]}://{quote(str(user))}:{quote(str(conn['root_password']))}@{host}:{port}{tail}"


# --- set_env ---------------------------------------------------------------------------------------


def _preview_env(a: dict[str, Any]) -> dict[str, Any]:
    keys = [v.get("key") for v in a.get("vars") or []]
    return {"title_fa": f"تنظیم {len(keys)} متغیر محیطی (اپ ری‌استارت می‌شود)", "why_fa": a.get("reason_fa"),
            "changes": {"keys": keys}}  # fmt: skip


@deployar_tool("set_env", group="liara", risk="sensitive", description=fa.SET_ENV_DESC, preview=_preview_env,
               input_schema={"type": "object", "required": ["vars"], "properties": {
                   "project_id": {"type": "string"}, "reason_fa": {"type": "string"},
                   "vars": {"type": "array", "items": {"type": "object", "required": ["key"], "properties": {
                       "key": {"type": "string"}, "value": {"type": "string"}, "value_ref": {"type": "string"},
                       "generate": {"type": "boolean"}}}}}})  # fmt: skip
async def set_env(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        p = await _project(ctx, args.get("project_id"))
        if not p.liara_app_name:
            return ToolError("app_not_created", fa.APP_NOT_CREATED)
        new: dict[str, str] = {}
        for v in args.get("vars") or []:
            key = str(v["key"])
            if v.get("value_ref"):
                new[key] = await load_secret(ctx, v["value_ref"])
            elif v.get("generate"):
                value = secrets.token_urlsafe(48)
                await store_secret(ctx, key, value, "generated", p.id)
                new[key] = value
            elif "value" in v and not _is_secret_key(key):
                new[key] = str(v["value"])
            else:  # a secret-looking key with a literal value came through the model: refuse it
                return ToolError("plain_secret", fa.PLAIN_SECRET)
        async with await liara_client(ctx) as c:
            merged = {e["key"]: e["value"] for e in await c.env_pairs(p.liara_app_name) if e["key"]}
            merged.update(new)
            await c.update_envs(p.liara_app_name, [{"key": k, "value": v} for k, v in merged.items()])
        return Ok({"app": p.liara_app_name, "keys_set": sorted(new), "restarted": True},
                  source="liara:POST /v1/projects/update-envs")  # fmt: skip

    return await _guard(run())


# --- deploy_release --------------------------------------------------------------------------------


def repack(tar_gz: bytes, app_root: str) -> bytes:
    """GitHub's tarball has one top folder (owner-repo-sha/); Liara wants the app's own folder as the root.
    gzip level 1: 0.9 s vs 10.7 s at tarfile's default 9 on a 29 MB repo (laptop); 0.5 CPU on Liara is far slower."""
    out = io.BytesIO()
    prefix = "" if app_root in ("", ".") else app_root.strip("/") + "/"
    found = False
    with (
        tarfile.open(fileobj=io.BytesIO(tar_gz), mode="r:gz") as src,
        tarfile.open(fileobj=out, mode="w:gz", compresslevel=1) as dst,
    ):
        for m in src.getmembers():
            parts = m.name.split("/", 1)
            if len(parts) < 2 or not parts[1].startswith(prefix) or m.issym() or m.islnk():
                continue  # links are dropped: an archive must not point outside itself
            rel = parts[1][len(prefix) :]
            if not rel or rel.startswith(".git/") or ".." in rel.split("/"):
                continue
            found = True
            m.name = rel
            dst.addfile(m, src.extractfile(m) if m.isfile() else None)
    if not found:
        raise DeployarError("app_root_missing", fa.APP_ROOT_MISSING, app_root)
    return out.getvalue()


def _preview_deploy(a: dict[str, Any]) -> dict[str, Any]:
    return {"title_fa": f"انتشار {a.get('ref') or 'شاخه‌ی اصلی'} روی لیارا", "why_fa": a.get("reason_fa"),
            "changes": {"ref": a.get("ref")}}  # fmt: skip


async def _port(ctx: ToolContext, p: Project) -> int:
    async with ctx.sessions() as s:
        detected = await s.scalar(
            select(RepoAnalysis.detected).join(Project, Project.id == RepoAnalysis.project_id)
            .where(Project.repo_full_name == p.repo_full_name, Project.user_id == ctx.user_id)
            .order_by(RepoAnalysis.created_at.desc()).limit(1)
        )  # fmt: skip
    for app in (detected or {}).get("apps") or []:
        if app.get("root") == p.app_root and (app.get("port") or {}).get("value"):
            return int(app["port"]["value"])
    return 3000 if p.platform in ("node", "next") else 80


@deployar_tool("deploy_release", group="liara", risk="sensitive", description=fa.DEPLOY_DESC, preview=_preview_deploy,
               input_schema={"type": "object", "properties": {"project_id": {"type": "string"},
                                                              "ref": {"type": "string"},
                                                              "reason_fa": {"type": "string"}}})  # fmt: skip
async def deploy_release(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        p = await _project(ctx, args.get("project_id"))
        if not p.liara_app_name or not p.repo_full_name:
            return ToolError("app_not_created", fa.APP_NOT_CREATED)
        owner, repo = parse_repo(p.repo_full_name)
        try:
            async with GitHubClient(await github_token(ctx)) as gh:
                sha = await gh.commit_sha(owner, repo, args.get("ref") or p.repo_default_branch or "main")
                # repack is CPU-bound (seconds on 0.5 CPU): off the loop, or the SSE stream stalls and the proxy cuts it
                source = await asyncio.to_thread(repack, await gh.tarball(owner, repo, sha), p.app_root)
        except GitHubNoAccess:
            return ToolError("github_no_access", fa.GITHUB_NO_ACCESS)
        if len(source) > MAX_SOURCE:
            return ToolError("source_too_big", fa.SOURCE_TOO_BIG)
        port = await _port(ctx, p)
        async with await liara_client(ctx) as c:
            source_id = await c.upload_source(p.liara_app_name, source)
            release_id = await c.create_release(p.liara_app_name, {
                "sourceID": source_id, "port": port, "type": p.platform,
                "gitInfo": {"commit": sha, "branch": args.get("ref") or p.repo_default_branch},
                # Iran's builder stalled on apt-get (deb.debian.org) for 15+ min; the basic bundle has germanyBuilder
                "build": {"location": "germany"}, "message": f"deployar {sha[:7]}"})  # fmt: skip
        async with ctx.sessions.begin() as s:
            d = Deployment(project_id=p.id, run_id=ctx.run_id, app_root=p.app_root, liara_app_name=p.liara_app_name,
                           commit_sha=sha, liara_source_id=source_id, liara_release_id=release_id,
                           status="building")  # fmt: skip
            s.add(d)
            await s.flush()
            deployment_id = d.id
        return Ok({"deployment_id": str(deployment_id), "release_id": release_id, "commit": sha[:7], "port": port,
                   "app": p.liara_app_name, "url": f"https://{p.liara_app_name}.liara.run",
                   "size_kb": len(source) // 1024}, source=f"liara:POST /v2/projects/{p.liara_app_name}/releases",
                  observed_at=datetime.now(UTC).isoformat())  # fmt: skip

    return await _guard(run())


# --- restart_app / resize_plan ---------------------------------------------------------------------


@deployar_tool("restart_app", group="liara", risk="sensitive", description=fa.RESTART_DESC,
               preview=lambda a: {"title_fa": "ری‌استارت اپ", "why_fa": a.get("reason_fa")},
               input_schema={"type": "object", "properties": {"project_id": {"type": "string"},
                                                              "reason_fa": {"type": "string"}}})  # fmt: skip
async def restart_app(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        p = await _project(ctx, args.get("project_id"))
        if not p.liara_app_name:
            return ToolError("app_not_created", fa.APP_NOT_CREATED)
        async with await liara_client(ctx) as c:
            await c.restart(p.liara_app_name)
        return Ok({"app": p.liara_app_name, "restarted_at": datetime.now(UTC).isoformat()},
                  source=f"liara:POST /v1/projects/{p.liara_app_name}/actions/restart")  # fmt: skip

    return await _guard(run())


def _preview_resize(a: dict[str, Any]) -> dict[str, Any]:
    return {"title_fa": f"تغییر پلن اپ به {a.get('plan_id')}", "why_fa": a.get("reason_fa"),
            "changes": {"plan": a.get("plan_id"), "from": a.get("current_plan_id")},
            **({"cost_delta_toman": (_monthly(a.get("plan_id")) or 0) - (_monthly(a.get("current_plan_id")) or 0),
                "cost_source": PRICE_SOURCE} if _monthly(a.get("plan_id")) else {})}  # fmt: skip


@deployar_tool("resize_plan", group="liara", risk="sensitive", description=fa.RESIZE_DESC, preview=_preview_resize,
               input_schema={"type": "object", "required": ["plan_id"], "properties": {
                   "project_id": {"type": "string"}, "plan_id": {"type": "string"},
                   "current_plan_id": {"type": "string"}, "reason_fa": {"type": "string"}}})  # fmt: skip
async def resize_plan(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    async def run() -> ToolResult:
        p = await _project(ctx, args.get("project_id"))
        if not p.liara_app_name:
            return ToolError("app_not_created", fa.APP_NOT_CREATED)
        async with await liara_client(ctx) as c:
            await c.resize(p.liara_app_name, args["plan_id"])
        async with ctx.sessions.begin() as s:
            await s.execute(update(Project).where(Project.id == p.id).values(plan_id=args["plan_id"]))
        return Ok({"app": p.liara_app_name, "from": p.plan_id, "to": args["plan_id"]},
                  source=f"liara:POST /v1/projects/{p.liara_app_name}/resize")  # fmt: skip

    return await _guard(run())
