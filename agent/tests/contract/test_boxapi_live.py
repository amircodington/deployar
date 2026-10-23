"""Live BoxAPI tool loop: one real model call through the gate (a fraction of a cent on Haiku).

DEPLOYAR_BOXAPI_LIVE=1 uv run pytest -m live tests/contract/test_boxapi_live.py -s
"""

import os
from typing import Any

import pytest
from claude_agent_sdk import PermissionResultAllow
from test_liara_client import _ctx_with_connection

pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get("DEPLOYAR_BOXAPI_LIVE") != "1",
                                                   reason="spends BoxAPI credit")]  # fmt: skip


async def test_the_model_calls_a_tool_and_answers_in_persian() -> None:
    from deployar.llm.boxapi_backend import BoxAPIBackend
    from deployar.llm.client import Done, TextDelta, ToolUse
    from deployar.tools.liara import incident  # noqa: F401
    from deployar.tools.registry import REGISTRY, Registry

    only = Registry()  # one tool, so the model can't wander to Liara with the test's fake token
    only.specs["report_diagnosis"] = REGISTRY.specs["report_diagnosis"]

    async def gate(*_: Any) -> Any:
        return PermissionResultAllow()

    evs = [ev async for ev in BoxAPIBackend().run(
        prompt="سایت خطای ۵۰۰ می‌دهد و لاگ می‌گوید MemoryError. دو علت احتمالی را با report_diagnosis ثبت کن، "
               "بعد در یک جمله‌ی فارسی بگو.",
        system_prompt="تو دستیار SRE فارسی هستی.", registry=only, tool_ctx=await _ctx_with_connection(),
        can_use_tool=gate, max_turns=4)]  # fmt: skip
    for ev in evs:
        print(type(ev).__name__, str(ev)[:160])
    assert any(isinstance(e, ToolUse) and e.name.endswith("report_diagnosis") for e in evs)
    assert any(isinstance(e, TextDelta) for e in evs) and isinstance(evs[-1], Done) and not evs[-1].is_error
