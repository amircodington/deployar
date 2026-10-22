from datetime import UTC, datetime, timedelta

from repo_fixtures import TOROB_GARD

from deployar.analysis.analyze import Repo, analyze
from deployar.runtime.plan import catalogue, choose, is_stale, totals
from deployar.tools.liara.read import STATIC_PLANS


def test_torob_gard_gets_a_plan_per_app_and_a_bigger_db_for_postgis() -> None:
    plans, source = catalogue(STATIC_PLANS, live=None)
    assert source.startswith("static:") and all(p.id is None for p in plans)  # unconfirmed ids, labelled
    items = choose(analyze(Repo.from_files(TOROB_GARD)), plans)
    by = {i.get("root") or i["kind"]: i for i in items}
    assert by["api"]["plan_name"] == "مریخ" and by["web"]["plan_name"] == "مریخ"  # 1024 MB each
    assert by["db"]["plan_name"] == "مریخ" and by["db"]["extensions"] == ["pgvector", "postgis"]
    t = totals(items, balance_toman=2_000_000)
    assert t["toman_month"] == 3 * 1_650_000 and t["toman_hour"] == 3 * 2_290
    assert t["days_covered"] == round(2_000_000 / (3 * 2_290 * 24), 1)


def test_live_plans_win_over_the_table_when_their_shape_is_usable() -> None:
    live = {"projects": {
        "512mb": {"available": False, "price": 100, "RAM": {"amount": 0.5}, "CPU": {"amount": 1}},
        "ir-small": {"available": True, "price": 1319.44, "RAM": {"amount": 0.5}, "CPU": {"amount": 0.5}},
        "ir-medium": {"available": True, "price": 2291.66, "RAM": {"amount": 1}, "CPU": {"amount": 1}},
        "medium-g2": {"available": True, "price": 1145.83, "RAM": {"amount": 1}, "CPU": {"amount": 1}},
    }}  # fmt: skip
    plans, source = catalogue(STATIC_PLANS, live)
    assert source == "liara:/v1/me" and [p.id for p in plans] == ["ir-small", "ir-medium"]  # no legacy, no g2
    assert plans[0].toman_hour == 1319 and plans[0].toman_month == 950_000  # price is per hour
    assert catalogue(STATIC_PLANS, {"projects": {"x": {"weird": 1}}})[1].startswith("static:")


def test_prices_go_stale_after_an_hour() -> None:
    now = datetime.now(UTC)
    assert not is_stale(now - timedelta(minutes=59), now) and is_stale(now - timedelta(minutes=61), now)
