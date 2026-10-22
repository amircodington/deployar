"""analyze_repo (read): fetch the deciding files at one commit and run the deterministic detectors."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from deployar import messages_fa as fa
from deployar.analysis.analyze import DETECTOR_VERSION, Repo, analyze, wanted
from deployar.clients.github import GitHubClient, GitHubNoAccess, parse_repo
from deployar.core.crypto import aad_for, get_vault
from deployar.core.errors import DeployarError
from deployar.models import GithubConnection, Project, RepoAnalysis
from deployar.tools.project import ensure_project, project_of
from deployar.tools.registry import ToolContext, deployar_tool
from deployar.tools.results import Ok, ToolError, ToolResult


async def github_token(ctx: ToolContext) -> str | None:
    async with ctx.sessions() as s:
        conn = await s.scalar(
            select(GithubConnection).where(GithubConnection.user_id == ctx.user_id, GithubConnection.status == "active")
        )
    if conn is None:
        return None  # public repos still work, at GitHub's anonymous rate limit
    aad = aad_for("github_connection", conn.id, conn.user_id)
    return get_vault().decrypt(conn.token_ciphertext, conn.key_version, aad)


REPO_SCHEMA = {"type": "object", "properties": {"repo": {"type": "string"}, "ref": {"type": "string"}}}


@deployar_tool("analyze_repo", group="github", risk="read", description=fa.ANALYZE_REPO_DESC, input_schema=REPO_SCHEMA)
async def analyze_repo(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    repo_text = args.get("repo")
    if not repo_text and (pid := await project_of(ctx)):
        async with ctx.sessions() as s:
            repo_text = await s.scalar(select(Project.repo_full_name).where(Project.id == pid))
    if not repo_text:
        return ToolError("no_repo", fa.NO_REPO)
    try:
        owner, name = parse_repo(repo_text)
        async with GitHubClient(await github_token(ctx)) as gh:
            meta = await gh.repo(owner, name)
            sha = await gh.commit_sha(owner, name, args.get("ref") or meta["default_branch"])
            paths = await gh.tree(owner, name, sha)
            files = await gh.files(owner, name, sha, sorted(p for p in paths if wanted(p)))
    except GitHubNoAccess:
        if ctx.emit:  # the reconnect card: tells the user exactly where to add a token
            await ctx.emit("github_reconnect", {"repo": repo_text, "message_fa": fa.GITHUB_NO_ACCESS})
        return ToolError("github_no_access", fa.GITHUB_NO_ACCESS)
    except DeployarError as e:
        return ToolError(e.code, e.message_fa, retryable=e.code in ("github_unreachable", "github_rate_limited"))

    detected = analyze(Repo(set(paths), files))
    project_id = await ensure_project(ctx, f"{owner}/{name}", meta["default_branch"])
    if project_id:  # cached per (project, commit, detector version) for the plan card
        async with ctx.sessions.begin() as s:
            await s.execute(
                insert(RepoAnalysis)
                .values(project_id=project_id, run_id=ctx.run_id, commit_sha=sha, detector_version=DETECTOR_VERSION,
                        detected=detected)
                .on_conflict_do_update(index_elements=["project_id", "commit_sha", "detector_version"],
                                       set_={"detected": detected, "run_id": ctx.run_id})
            )  # fmt: skip
    payload = {"repo": f"{owner}/{name}", "commit_sha": sha, "private": bool(meta.get("private")), **detected}
    return Ok(payload, source=f"github:{owner}/{name}@{sha[:7]}", card=("repo_analysis", payload))
