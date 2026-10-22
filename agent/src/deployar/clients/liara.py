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
            if r.status_code in _RETRY_STATUS and attempt < len(_BACKOFF_S):
                await asyncio.sleep(_BACKOFF_S[attempt])
                continue
            if r.status_code == 401:
                raise DeployarError("liara_unauthorized", fa.LIARA_UNAUTHORIZED, f"{method} {path}")
            if r.status_code in (404, 405):
                raise LiaraNotFound(f"{method} {path} -> {r.status_code}")
            if r.status_code >= 400:
                raise DeployarError("liara_error", fa.LIARA_ERROR, f"{method} {path} -> {r.status_code}")
            return r.json() if r.content else None
        raise DeployarError("liara_error", fa.LIARA_ERROR, f"{method} {path}: retries exhausted")

    # --- reads -------------------------------------------------------------------------------

    async def billing(self) -> dict[str, Any]:
        """{balance (toman), accountType, minCreditAmount, isManualMinCredit}; the API nests it under `user`."""
        data = await self.request("GET", "/v1/billing")
        user: dict[str, Any] = (data or {}).get("user") or data or {}
        return user

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
