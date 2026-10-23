"""BoxAPI backend (decision 2's seam): an OpenAI-compatible tool loop for running off the Claude login.

The model sees every registered tool, but each call still goes through can_use_tool (the same gate the
Claude SDK uses), so approval stays in code. When the first key is out of credit, the second takes over.
"""

import json
import logging
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
from claude_agent_sdk import PermissionResultAllow, ToolPermissionContext

from deployar.core.config import get_settings
from deployar.llm.client import Done, LLMEvent, TextDelta, ToolResult, ToolUse
from deployar.runtime.gate import PREFIX, CanUseTool
from deployar.tools.registry import Registry, ToolContext

log = logging.getLogger(__name__)
_QUOTA = re.compile(r"credit|quota|balance|insufficient|billing", re.I)

# shortcut: conversation history lives in process memory, so an agent restart forgets earlier turns of a
# conversation (the next message starts fresh). Upgrade to the message table if multi-turn memory matters.
SESSIONS: dict[str, list[dict[str, Any]]] = {}


def is_quota_error(r: httpx.Response) -> bool:
    return r.status_code == 402 or (r.status_code in (401, 403, 429) and bool(_QUOTA.search(r.text)))


def _tools(registry: Registry) -> list[dict[str, Any]]:
    return [{"type": "function", "function": {"name": s.name, "description": s.description,
                                              "parameters": s.input_schema}}
            for s in registry.specs.values()]  # fmt: skip


def _status(out: dict[str, Any]) -> str:
    try:
        return str(json.loads(out["content"][0]["text"]).get("status", "ok"))
    except (ValueError, KeyError, IndexError, AttributeError):
        return "error" if out.get("is_error") else "ok"


class BoxAPIBackend:
    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        s = get_settings()
        self.model = s.boxapi_model
        self.keys = [k.get_secret_value() for k in (s.boxapi_api_key, s.boxapi_key_second) if k.get_secret_value()]
        self.key = 0  # process-wide index: once the first key is spent, every run uses the second
        self.http = http or httpx.AsyncClient(base_url=s.boxapi_base_url.rstrip("/"), timeout=120.0)

    async def _chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        body = {"model": self.model, "messages": messages, "tools": tools}
        while True:
            headers = {"Authorization": f"Bearer {self.keys[self.key]}"} if self.keys else {}
            r = await self.http.post("/chat/completions", json=body, headers=headers)
            if is_quota_error(r) and self.key + 1 < len(self.keys):
                self.key += 1
                log.warning("BoxAPI key out of credit (HTTP %s); using the second key", r.status_code)
                continue
            r.raise_for_status()
            return dict(r.json()["choices"][0]["message"])

    async def run(
        self,
        *,
        prompt: str,
        system_prompt: str,
        registry: Registry,
        tool_ctx: ToolContext,
        can_use_tool: CanUseTool,
        max_turns: int,
        resume: str | None = None,
    ) -> AsyncIterator[LLMEvent]:
        session_id = resume if resume in SESSIONS else str(uuid.uuid4())
        history = SESSIONS.setdefault(session_id, [])
        history.append({"role": "user", "content": prompt})
        tools = _tools(registry)
        try:
            for _ in range(max_turns):
                msg = await self._chat([{"role": "system", "content": system_prompt}, *history], tools)
                calls = msg.get("tool_calls") or []
                history.append({"role": "assistant", "content": msg.get("content") or "",
                                **({"tool_calls": calls} if calls else {})})  # fmt: skip
                if msg.get("content"):
                    yield TextDelta(msg["content"])
                if not calls:
                    yield Done(session_id, model=self.model)
                    return
                for call in calls:
                    name = call["function"]["name"]
                    try:
                        args = json.loads(call["function"].get("arguments") or "{}")
                    except ValueError:
                        args = {}
                    yield ToolUse(call["id"], PREFIX + name, args)
                    decision = await can_use_tool(PREFIX + name, args, ToolPermissionContext())
                    if isinstance(decision, PermissionResultAllow) and registry.risk_of(name):
                        out = await registry.run(tool_ctx, name, args)
                        text, status = out["content"][0]["text"], _status(out)
                    else:
                        text = json.dumps({"status": "denied", "message": getattr(decision, "message", "")},
                                          ensure_ascii=False)  # fmt: skip
                        status = "error"
                    history.append({"role": "tool", "tool_call_id": call["id"], "content": text})
                    yield ToolResult(call["id"], status)
            yield Done(session_id, is_error=True, error="max_turns", model=self.model)
        except httpx.HTTPError as e:
            yield Done(session_id, is_error=True, error=f"boxapi: {type(e).__name__}", model=self.model)
