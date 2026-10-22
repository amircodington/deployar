"""GitHub client (fine-grained token, BUILD.md defaults). Reads only the files the analyzer needs."""

import asyncio
import re
from typing import Any

import httpx

from deployar import messages_fa as fa
from deployar.core.errors import DeployarError

API = "https://api.github.com"
_MAX_FILES = 60


class GitHubNoAccess(Exception):
    """404 on a repo: it does not exist or the token cannot see it (GitHub hides private repos)."""


def parse_repo(text: str) -> tuple[str, str]:
    m = re.search(r"(?:github\.com[/:])?([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", text.strip())
    if not m:
        raise DeployarError("bad_repo", fa.BAD_REPO, text)
    return m.group(1), m.group(2)


class GitHubClient:
    def __init__(self, token: str | None = None, transport: httpx.AsyncBaseTransport | None = None):
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "deployar"}  # fmt: skip
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(base_url=API, headers=headers, timeout=20.0, transport=transport)

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._client.aclose()

    async def _get(self, path: str, **kw: Any) -> httpx.Response:
        try:
            r = await self._client.get(path, **kw)
        except httpx.TransportError as e:
            raise DeployarError("github_unreachable", fa.GITHUB_UNREACHABLE, type(e).__name__) from e
        if r.status_code == 401:
            raise DeployarError("github_unauthorized", fa.GITHUB_UNAUTHORIZED, path)
        if r.status_code == 404:
            raise GitHubNoAccess(path)
        if r.status_code == 403 and r.headers.get("x-ratelimit-remaining") == "0":
            raise DeployarError("github_rate_limited", fa.GITHUB_RATE_LIMITED, path)
        if r.status_code >= 400:
            raise DeployarError("github_error", fa.GITHUB_ERROR, f"{path} -> {r.status_code}")
        return r

    async def user_login(self) -> str:
        return str((await self._get("/user")).json()["login"])

    async def repo(self, owner: str, name: str) -> dict[str, Any]:
        data: dict[str, Any] = (await self._get(f"/repos/{owner}/{name}")).json()
        return data

    async def commit_sha(self, owner: str, name: str, ref: str) -> str:
        return str((await self._get(f"/repos/{owner}/{name}/commits/{ref}")).json()["sha"])

    async def tree(self, owner: str, name: str, sha: str) -> list[str]:
        data = (await self._get(f"/repos/{owner}/{name}/git/trees/{sha}", params={"recursive": "1"})).json()
        return [t["path"] for t in data.get("tree", []) if t.get("type") == "blob"]

    async def files(self, owner: str, name: str, sha: str, paths: list[str]) -> dict[str, str]:
        sem = asyncio.Semaphore(8)

        async def one(path: str) -> tuple[str, str]:
            async with sem:
                r = await self._get(f"/repos/{owner}/{name}/contents/{path}", params={"ref": sha},
                                    headers={"Accept": "application/vnd.github.raw"})  # fmt: skip
                return path, r.text

        return dict(await asyncio.gather(*(one(p) for p in paths[:_MAX_FILES])))

    async def tarball(self, owner: str, name: str, sha: str) -> bytes:
        """Source archive at a fixed commit, for deploy_release (B-11)."""
        r = await self._client.get(f"/repos/{owner}/{name}/tarball/{sha}", follow_redirects=True)
        if r.status_code == 404:
            raise GitHubNoAccess(f"tarball {owner}/{name}@{sha}")
        r.raise_for_status()
        return r.content
