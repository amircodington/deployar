"""BoxAPI backend (decision 14): the tool loop keeps the gate, and the second key takes over on no credit."""

import json
from typing import Any

import httpx
import respx
from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny
from test_liara_client import _ctx_with_connection

BASE = "https://box.test/ai/v1"


def _msg(content: str | None = None, calls: list[tuple[str, str, dict[str, Any]]] | None = None) -> httpx.Response:
    tool_calls = [{"id": i, "type": "function", "function": {"name": n, "arguments": json.dumps(a)}}
                  for i, n, a in calls or []]  # fmt: skip
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content,
                                                               "tool_calls": tool_calls or None}}]})  # fmt: skip


def _backend(keys: list[str], models: list[str] | None = None) -> Any:
    from deployar.llm.boxapi_backend import BoxAPIBackend

    b = BoxAPIBackend(http=httpx.AsyncClient(base_url=BASE))
    b.keys, b.models, b.key = keys, models or ["m1"] * len(keys), 0
    return b


async def _events(backend: Any, gate: Any, prompt: str = "سلام", resume: str | None = None) -> list[Any]:
    from deployar.tools.liara import deploy, incident  # noqa: F401
    from deployar.tools.registry import REGISTRY

    ctx = await _ctx_with_connection()
    return [ev async for ev in backend.run(prompt=prompt, system_prompt="sys", registry=REGISTRY, tool_ctx=ctx,
                                           can_use_tool=gate, max_turns=5, resume=resume)]  # fmt: skip


@respx.mock
async def test_read_tool_runs_and_its_result_goes_back_to_the_model() -> None:
    from deployar.llm.client import Done, TextDelta, ToolResult, ToolUse

    hyps = {"symptom_fa": "کند است", "hypotheses": [{"cause_fa": "حافظه", "likelihood": 0.6}]}
    route = respx.post(f"{BASE}/chat/completions")
    route.side_effect = [_msg(calls=[("c1", "report_diagnosis", hyps)]), _msg("احتمالاً حافظه است.")]
    asked: list[str] = []

    async def gate(name: str, args: dict[str, Any], _c: Any) -> Any:
        asked.append(name)
        return PermissionResultAllow()

    evs = await _events(_backend(["k1"]), gate)
    assert asked == ["mcp__deployar__report_diagnosis"]
    assert [type(e) for e in evs] == [ToolUse, ToolResult, TextDelta, Done]
    assert evs[1].status == "ok" and not evs[-1].is_error
    second = json.loads(route.calls[1].request.content)["messages"]
    assert second[0] == {"role": "system", "content": "sys"} and second[-1]["role"] == "tool"
    assert "حافظه" in second[-1]["content"]


@respx.mock
async def test_a_denied_tool_never_runs() -> None:
    from deployar.llm.boxapi_backend import SESSIONS

    route = respx.post(f"{BASE}/chat/completions")
    route.side_effect = [_msg(calls=[("c1", "restart_app", {"reason_fa": "x"})]), _msg("منتظر تأیید تو هستم.")]

    async def gate(name: str, args: dict[str, Any], _c: Any) -> Any:
        return PermissionResultDeny(message="رد شد")

    evs = await _events(_backend(["k1"]), gate)
    assert evs[1].status == "error"
    tool_msg = json.loads(route.calls[1].request.content)["messages"][-1]
    assert json.loads(tool_msg["content"]) == {"status": "denied", "message": "رد شد"}
    assert evs[-1].session_id in SESSIONS  # the next message of this conversation resumes it


@respx.mock
async def test_second_key_takes_over_when_the_first_is_out_of_credit() -> None:
    route = respx.post(f"{BASE}/chat/completions")
    route.side_effect = [httpx.Response(402, json={"error": "insufficient credit"}), _msg("سلام")]
    backend = _backend(["k1", "k2"], ["haiku", "gpt-mini"])  # the second key may allow another model only

    async def gate(*_: Any) -> Any:
        return PermissionResultAllow()

    evs = await _events(backend, gate)
    assert [c.request.headers["authorization"] for c in route.calls] == ["Bearer k1", "Bearer k2"]
    assert [json.loads(c.request.content)["model"] for c in route.calls] == ["haiku", "gpt-mini"]
    assert backend.key == 1 and evs[-1].is_error is False and evs[-1].model == "gpt-mini"


@respx.mock
async def test_an_http_failure_ends_the_run_as_an_error() -> None:
    respx.post(f"{BASE}/chat/completions").respond(500)

    async def gate(*_: Any) -> Any:
        return PermissionResultAllow()

    evs = await _events(_backend(["k1"]), gate)
    assert evs[-1].is_error and evs[-1].error == "boxapi: HTTPStatusError"


@respx.mock
async def test_after_a_restart_the_chat_remembers_its_saved_turns() -> None:
    import asyncpg
    from pgtest import PG_TEST

    from deployar.tools.liara import incident  # noqa: F401
    from deployar.tools.registry import REGISTRY

    ctx = await _ctx_with_connection()
    conn = await asyncpg.connect(PG_TEST)
    try:  # an earlier turn saved in the database; this process has no memory of it (SESSIONS is empty for it)
        conv = await conn.fetchval("insert into conversation (user_id) values ($1) returning id", ctx.user_id)
        for seq, (role, text) in enumerate([("user", "اپ من shop است"), ("assistant", "باشد، shop"),
                                            ("user", "اسم اپم چه بود؟")], 1):  # fmt: skip
            mid = await conn.fetchval(
                "insert into message (conversation_id, seq, role, content) values ($1, $2, $3, $4::jsonb) returning id",
                conv, seq, role, json.dumps([{"type": "text", "text_fa": text}]))  # fmt: skip
        await conn.execute("update run set conversation_id = $1, triggered_by_message_id = $2 where id = $3",
                           conv, mid, ctx.run_id)  # fmt: skip
    finally:
        await conn.close()
    route = respx.post(f"{BASE}/chat/completions").mock(return_value=_msg("shop"))

    async def gate(*_: Any) -> Any:
        return PermissionResultAllow()

    evs = [ev async for ev in _backend(["k1"]).run(prompt="اسم اپم چه بود؟", system_prompt="sys", registry=REGISTRY,
                                                    tool_ctx=ctx, can_use_tool=gate, max_turns=2,
                                                    resume="lost-after-restart")]  # fmt: skip
    sent = json.loads(route.calls[0].request.content)["messages"]
    assert [m["content"] for m in sent] == ["sys", "اپ من shop است", "باشد، shop", "اسم اپم چه بود؟"]
    assert not evs[-1].is_error
