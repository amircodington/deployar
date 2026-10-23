"""BoxAPI backend (decision 2's seam): an OpenAI-compatible tool loop for running off the Claude login.

The model sees every registered tool, but each call still goes through can_use_tool (the same gate the
Claude SDK uses), so approval stays in code. When the first key is out of credit, the second takes over.
"""

import asyncio
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
from claude_agent_sdk import PermissionResultAllow, ToolPermissionContext
from sqlalchemy import select

from deployar.core.config import get_settings
from deployar.llm.client import Done, LLMEvent, TextDelta, ToolResult, ToolUse
from deployar.models import Message, Run
from deployar.runtime.gate import PREFIX, CanUseTool
from deployar.tools.registry import Registry, ToolContext

log = logging.getLogger(__name__)
BACKOFF_S = (2.0, 5.0, 10.0)  # a retried call may be billed twice; better than a run that dies on one dropped connect
RETRY_STATUS = {429, 502, 503, 504}
_QUOTA = re.compile(r"credit|quota|balance|insufficient|billing", re.I)

# Tool-call detail of a conversation lives in process memory; after a restart the history is rebuilt from the
# saved user and assistant texts (message table), so the model remembers what was said, not the raw tool output.
SESSIONS: dict[str, list[dict[str, Any]]] = {}


async def saved_history(ctx: ToolContext) -> list[dict[str, Any]]:
    """The run's conversation before its own message, as chat turns."""
    async with ctx.sessions() as s:
        run = await s.get(Run, ctx.run_id)
        if run is None or run.conversation_id is None:
            return []
        upto = await s.scalar(select(Message.seq).where(Message.id == run.triggered_by_message_id)) or 0
        rows = (await s.scalars(select(Message).where(
            Message.conversation_id == run.conversation_id, Message.seq < upto,
            Message.role.in_(("user", "assistant"))).order_by(Message.seq))).all()  # fmt: skip
    turns = [{"role": m.role, "content": " ".join(p.get("text_fa", "") for p in m.content if isinstance(p, dict))}
             for m in rows]  # fmt: skip
    return [t for t in turns if t["content"].strip()]


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
        second = s.boxapi_model_second or s.boxapi_model
        keys = ((s.boxapi_api_key, s.boxapi_model), (s.boxapi_key_second, second))
        pairs = [(k.get_secret_value(), m) for k, m in keys
                 if k.get_secret_value()]  # fmt: skip
        self.keys, self.models = [k for k, _ in pairs], [m for _, m in pairs] or [s.boxapi_model]
        self.key = 0  # process-wide index: once the first key is spent, every run uses the second
        self.http = http or httpx.AsyncClient(base_url=s.boxapi_base_url.rstrip("/"), timeout=120.0)

    @property
    def model(self) -> str:
        return self.models[self.key]  # each key may allow other models (BoxAPI per-key allow list)

    async def _chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        tries = 0
        while True:
            body = {"model": self.model, "messages": messages, "tools": tools}
            headers = {"Authorization": f"Bearer {self.keys[self.key]}"} if self.keys else {}
            try:
                r = await self.http.post("/chat/completions", json=body, headers=headers)
            except httpx.TransportError as e:  # GapGPT from Iran: dropped connects, TLS resets, read timeouts
                r = None
                err: Exception = e
            if (r is None or r.status_code in RETRY_STATUS) and tries < len(BACKOFF_S):
                log.warning("LLM gateway %s; retry %s in %ss", r.status_code if r else type(err).__name__, tries + 1,
                            BACKOFF_S[tries])  # fmt: skip
                await asyncio.sleep(BACKOFF_S[tries])
                tries += 1
                continue
            if r is None:
                raise err
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
        if resume in SESSIONS:
            session_id, history = resume, SESSIONS[resume]
        else:  # a new chat, or the agent restarted since this one's last turn
            session_id, history = str(uuid.uuid4()), await saved_history(tool_ctx)
            SESSIONS[session_id] = history
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
