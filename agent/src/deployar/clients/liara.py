"""Liara API client (skills/liara-api/SKILL.md). The token lives only inside this object.

Responses that carry secrets (env values, DB root password, Object Storage keys) are trimmed here,
before anything else can see them. No request logging: httpx is kept at WARNING (core/logging.py).
"""

import asyncio
import time
from typing import Any

import httpx

from deployar import messages_fa as fa
from deployar.core.config import get_settings
from deployar.core.errors import DeployarError

_RETRY_STATUS = {429, 500, 502, 503, 504}
_BACKOFF_S = (0.5, 1.0, 2.0)
_MIN_INTERVAL_S = 0.2  # 5 requests/s per token


def _message(r: httpx.Response) -> str:
    """Liara's own error text, for the audit detail (never the request body)."""
    try:
        body = r.json()
    except ValueError:
        return ""
    return str(body.get("message") or "")[:200] if isinstance(body, dict) else ""


class LiaraNotFound(Exception):
    """404/405: the resource or the capability is not there; tools turn this into a Limitation or error."""


class LiaraClient:
    def __init__(self, token: str, team_id: str | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self._client = httpx.AsyncClient(
            base_url=get_settings().liara_api_base,
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(20.0, connect=10.0),
            transport=transport,
        )
        self._team = {"teamID": team_id} if team_id else {}
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "LiaraClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def _throttle(self) -> None:
        async with self._lock:
            wait = self._last + _MIN_INTERVAL_S - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()

    async def request(self, method: str, path: str, *, params: dict[str, Any] | None = None, **kw: Any) -> Any:
        for attempt in range(len(_BACKOFF_S) + 1):
            await self._throttle()
            try:
                r = await self._client.request(method, path, params={**self._team, **(params or {})}, **kw)
            except httpx.TransportError as e:
                if attempt == len(_BACKOFF_S):
                    raise DeployarError("liara_unreachable", fa.LIARA_UNREACHABLE, type(e).__name__) from e
                await asyncio.sleep(_BACKOFF_S[attempt])
                continue
            # a write that reached Liara may have happened: only a 429 (rejected before work) is safe to resend
            retry = _RETRY_STATUS if method == "GET" else {429}
            if r.status_code in retry and attempt < len(_BACKOFF_S):
                await asyncio.sleep(_BACKOFF_S[attempt])
                continue
            if r.status_code == 401:
                raise DeployarError("liara_unauthorized", fa.LIARA_UNAUTHORIZED, f"{method} {path}")
            if r.status_code in (404, 405):
                raise LiaraNotFound(f"{method} {path} -> {r.status_code}")
            if r.status_code == 402:
                raise DeployarError("liara_no_credit", fa.LIARA_NO_CREDIT, f"{method} {path}")
            if r.status_code == 409:
                raise DeployarError("liara_exists", fa.LIARA_EXISTS, f"{method} {path}: {_message(r)}")
            if r.status_code >= 400:
                raise DeployarError("liara_error", fa.LIARA_ERROR, f"{method} {path} -> {r.status_code}: {_message(r)}")
            return r.json() if r.content else None
        raise DeployarError("liara_error", fa.LIARA_ERROR, f"{method} {path}: retries exhausted")

    # --- reads -------------------------------------------------------------------------------

    async def billing(self) -> dict[str, Any]:
        """{balance (toman), accountType, minCreditAmount, isManualMinCredit}.

        The API returns `user` (personal) and, with teamID, also `team`; a team token spends team credit.
        """
        data = await self.request("GET", "/v1/billing") or {}
        chosen: dict[str, Any] = (data.get("team") if self._team else None) or data.get("user") or data
        return chosen

    async def me_summary(self) -> dict[str, Any]:
        """Only what we use: /v1/me also carries national code and Object Storage keys."""
        me = await self.request("GET", "/v1/me")
        user = me.get("user") or {}
        return {"email": user.get("email"), "plans": me.get("plans"), "databaseVersions": me.get("databaseVersions")}

    async def projects(self) -> list[dict[str, Any]]:
        data = await self.request("GET", "/v1/projects")
        return list(data.get("projects") or [])

    async def project(self, name: str) -> dict[str, Any]:
        """Env values are dropped here; callers get key names only."""
        p = dict((await self.request("GET", f"/v1/projects/{name}")).get("project") or {})
        p["env_keys"] = sorted(e.get("key", "") for e in p.pop("envs", None) or [])
        return p

    async def logs(self, name: str, since: int) -> list[dict[str, Any]]:
        return list(await self.request("GET", f"/v1/projects/{name}/logs", params={"since": since}) or [])

    async def releases(self, name: str, count: int = 10) -> dict[str, Any]:
        data: dict[str, Any] = await self.request(
            "GET", f"/v1/projects/{name}/releases", params={"page": 1, "count": count}
        )
        return data

    async def metrics_summary(self, name: str) -> dict[str, Any]:
        data: dict[str, Any] = await self.request("GET", f"/v1/projects/{name}/metrics/summary")
        return data

    async def metrics(self, name: str, kind: str, since: int) -> dict[str, Any]:
        data: dict[str, Any] = await self.request("GET", f"/v1/projects/{name}/metrics/{kind}", params={"since": since})
        return data

    # --- writes (only ever called from sensitive tools, after approval) ------------------------

    async def networks(self) -> list[dict[str, Any]]:
        return list((await self.request("GET", "/v1/networks") or {}).get("networks") or [])

    async def create_network(self, name: str) -> None:
        await self.request("POST", "/v1/networks", json={"networkName": name})

    async def create_app(self, name: str, platform: str, plan_id: str, network_id: str) -> None:
        body = {"name": name, "planID": plan_id, "platform": platform, "network": network_id,
                "readOnlyRootFilesystem": False}  # fmt: skip
        await self.request("POST", "/v1/projects", json=body)

    async def create_database(self, hostname: str, kind: str, version: str, plan_id: str, network_id: str) -> str:
        body = {"hostname": hostname, "type": kind, "version": version, "planID": plan_id, "network": network_id,
                "publicNetwork": False}  # fmt: skip
        data = await self.request("POST", "/v1/databases", json=body) or {}
        return str(data.get("databaseID") or data.get("_id") or "")

    async def database_connection(self, db_id: str) -> dict[str, Any]:
        """Status plus what a connection string needs. root_password stays inside the caller."""
        d = (await self.request("GET", f"/v1/databases/{db_id}") or {}).get("database") or {}
        # `port` is the public node port; inside the private network the app uses hostname:internalPort
        keep = ("status", "type", "hostname", "internalPort", "username", "root_password", "dbName")
        return {k: d.get(k) for k in keep}

    async def env_pairs(self, name: str) -> list[dict[str, str]]:
        """Current env with values, for merging in set_env only; never returned from a tool."""
        p = (await self.request("GET", f"/v1/projects/{name}")).get("project") or {}
        return [{"key": e.get("key", ""), "value": e.get("value", "")} for e in p.get("envs") or []]

    async def update_envs(self, name: str, variables: list[dict[str, str]]) -> None:
        await self.request("POST", "/v1/projects/update-envs", json={"project": name, "variables": variables})

    async def upload_source(self, name: str, tar_gz: bytes) -> str:
        files = {"file": ("source.tar.gz", tar_gz, "application/gzip")}
        data = await self.request("POST", f"/v2/projects/{name}/sources", files=files, timeout=300.0)
        return str((data or {}).get("sourceID") or "")

    async def create_release(self, name: str, body: dict[str, Any]) -> str:
        data = await self.request("POST", f"/v2/projects/{name}/releases", json=body)
        return str((data or {}).get("releaseID") or "")

    async def release(self, release_id: str) -> dict[str, Any]:
        data: dict[str, Any] = (await self.request("GET", f"/v1/releases/{release_id}") or {}).get("release") or {}
        return data

    async def build_logs(self, release_id: str, since: str | None = None) -> dict[str, Any]:
        params = {"since": since} if since else None
        data: dict[str, Any] = await self.request("GET", f"/v2/releases/{release_id}/build-logs", params=params) or {}
        return data

    async def restart(self, name: str) -> None:
        await self.request("POST", f"/v1/projects/{name}/actions/restart")

    async def resize(self, name: str, plan_id: str) -> None:
        await self.request("POST", f"/v1/projects/{name}/resize", json={"planID": plan_id})

    async def delete_app(self, name: str) -> None:
        await self.request("DELETE", f"/v1/projects/{name}")

    async def delete_database(self, db_id: str) -> None:
        await self.request("DELETE", f"/v1/databases/{db_id}")

    async def add_domain(self, domain: str, app: str) -> str:
        data = await self.request("POST", "/v1/domains", json={"name": domain, "project": app, "type": "PROJECT"}) or {}
        return str((data.get("domain") or {}).get("_id") or "")

    async def check_domain(self, domain_id: str) -> dict[str, Any]:
        d = (await self.request("GET", f"/v1/domains/{domain_id}/check") or {}).get("domain") or {}
        return {k: d.get(k) for k in ("name", "status", "certificatesStatus", "CNameRecord")}
