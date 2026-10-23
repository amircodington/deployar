"""SRE loop and domain tools (B-14, B-16..B-19): before/after numbers, ranked causes, domain records."""

from dataclasses import replace
from typing import Any

import httpx
import respx
from test_deploy_tools import approve
from test_liara_client import API, _ctx_with_connection, _payload

URL = "https://torob-gard.liara.run/api/health"
SUMMARY = {"cpuUsage": [{"value": [1, "0.40"]}], "memoryUsage": [{"value": [1, str(500 * 1_048_576)]}]}


def _cards(ctx: Any) -> tuple[Any, list[tuple[str, dict[str, Any]]]]:
    cards: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        cards.append((kind, payload))

    return replace(ctx, emit=emit), cards


@respx.mock
async def test_probe_diagnose_verify_shows_before_and_after() -> None:
    from deployar.tools.liara import incident  # noqa: F401
    from deployar.tools.registry import REGISTRY

    respx.get(f"{API}/v1/projects/torob-gard/metrics/summary").respond(json=SUMMARY)
    site = respx.get(URL)
    site.side_effect = [httpx.Response(500)] * 4 + [httpx.Response(200)] + [httpx.Response(200)] * 5
    ctx, cards = _cards(await _ctx_with_connection())

    before = _payload(await REGISTRY.run(ctx, "http_probe", {"path": "/api/health", "n": 5}))
    assert before["data"]["error_rate"] == 0.8 and before["data"]["memory_mb"] == 500
    assert before["source"] == f"probe:{URL}"

    hyps = {"symptom_fa": "سایت ۵۰۰ می‌دهد", "hypotheses": [
        {"cause_fa": "محدودیت CPU", "likelihood": 0.1, "evidence": ["cpu 0.40"]},
        {"cause_fa": "خطای برنامه", "likelihood": 0.7, "evidence": ["Traceback in views.py:42"], "action_fa": "رفع کد"},
    ]}  # fmt: skip
    ranked = _payload(await REGISTRY.run(ctx, "report_diagnosis", hyps))["data"]["ranked"]
    assert ranked == ["خطای برنامه", "محدودیت CPU"]
    assert cards[-1][0] == "diagnosis" and cards[-1][1]["baseline"]["error_rate"] == 0.8

    after = _payload(await REGISTRY.run(ctx, "verify_after_action", {"wait_s": 0}))
    assert after["data"]["fixed"] is True and after["data"]["after"]["error_rate"] == 0.0
    assert cards[-1][0] == "verify" and cards[-1][1]["before"]["error_rate"] == 0.8


async def test_verify_without_a_baseline_says_so() -> None:
    from deployar.tools.liara import incident  # noqa: F401
    from deployar.tools.registry import REGISTRY

    ctx = await _ctx_with_connection()
    assert _payload(await REGISTRY.run(ctx, "verify_after_action", {"wait_s": 0}))["code"] == "no_baseline"


@respx.mock
async def test_add_domain_returns_the_record_and_check_dns_follows_it() -> None:
    from deployar.tools.liara import domain  # noqa: F401
    from deployar.tools.registry import REGISTRY

    created = respx.post(f"{API}/v1/domains").respond(201, json={"domain": {"_id": "dom-1"}})
    check = respx.get(f"{API}/v1/domains/dom-1/check")
    check.side_effect = [
        httpx.Response(200, json={"domain": {"status": "PENDING", "CNameRecord": "torob-gard.liara.run"}}),
        httpx.Response(200, json={"domain": {"status": "OK", "certificatesStatus": "ACTIVE"}}),
    ]
    ctx = await _ctx_with_connection()
    args = {"domain": "shop.torobgard.ir"}
    assert _payload(await REGISTRY.run(ctx, "add_domain", args))["code"] == "approval_missing"
    await approve(ctx, "add_domain", args)
    out = _payload(await REGISTRY.run(ctx, "add_domain", args))
    assert out["data"]["records"] == [{"type": "CNAME", "name": "shop.torobgard.ir", "value": "torob-gard.liara.run"}]
    assert created.calls[0].request.content == b'{"name":"shop.torobgard.ir","project":"torob-gard","type":"PROJECT"}'

    dns = _payload(await REGISTRY.run(ctx, "check_dns", args))
    assert dns["data"]["connected"] is True and dns["data"]["certificate"] == "ACTIVE"


def test_human_only_tools_are_registered_and_never_run() -> None:
    from deployar import messages_fa as fa
    from deployar.tools.liara import domain  # noqa: F401
    from deployar.tools.registry import REGISTRY

    for name in ("top_up_balance", "registrar_dns_records"):
        assert REGISTRY.risk_of(name) == "human_only" and fa.HUMAN_STEPS[name]


@respx.mock
async def test_the_app_name_works_where_a_project_id_is_expected() -> None:
    from deployar.tools.liara import incident  # noqa: F401
    from deployar.tools.registry import REGISTRY

    respx.get(f"{API}/v1/projects/torob-gard/metrics/summary").respond(json=SUMMARY)
    respx.get(URL).respond(200)
    ctx = await _ctx_with_connection()
    out = _payload(await REGISTRY.run(ctx, "http_probe", {"project_id": "torob-gard", "path": "/api/health", "n": 1}))
    assert out["status"] == "ok" and out["data"]["app"] == "torob-gard"  # the model passed the app name, not a uuid
