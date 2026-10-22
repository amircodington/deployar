"""Plan proposal: the cheapest Liara plan that fits each app's RAM estimate, plus the database.

Pure selection here (testable); the propose_plan tool fetches prices and balance and stores the card.
Prices are only ever copied from a source (live /v1/me or the dated console table), never estimated.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

STALE_AFTER = timedelta(hours=1)  # prices older than this are re-fetched before an approval


@dataclass(frozen=True)
class Plan:
    id: str | None  # None = not confirmed from the API yet; create_app refuses such a plan
    name: str
    ram_mb: int
    cpu: float
    toman_month: int
    toman_hour: int


def catalogue(static: list[dict[str, Any]], live: dict[str, Any] | None = None) -> tuple[list[Plan], str]:
    """Live plans when /v1/me gives a usable shape; otherwise the dated console table (labelled)."""
    plans: list[Plan] = []
    for pid, p in ((live or {}).get("projects") or {}).items():
        try:
            ram = float(p["RAM"]["amount"]) * 1024
            plans.append(Plan(pid, p.get("name") or pid, int(ram), float(p["CPU"]["amount"]),
                              int(p["price"]), int(p.get("hourlyPrice") or round(int(p["price"]) / 720))))  # fmt: skip
        except (KeyError, TypeError, ValueError):
            plans = []
            break
    if plans:
        return sorted(plans, key=lambda x: (x.ram_mb, x.toman_month)), "liara:/v1/me"
    table = [Plan(None, p["name"], p["ram_mb"], p["cpu"], p["toman_month"], p["toman_hour"]) for p in static]
    return table, "static:liara-console-2026-10-22"


def fit(plans: list[Plan], ram_mb: int) -> Plan:
    return next((p for p in plans if p.ram_mb >= ram_mb), plans[-1])


def choose(detected: dict[str, Any], plans: list[Plan]) -> list[dict[str, Any]]:
    """One line per app, then the database (bigger when it carries PostGIS-style extensions)."""
    items: list[dict[str, Any]] = []
    for app in detected.get("apps", []):
        need = int(app["ram_estimate_mb"]["value"])
        p = fit(plans, need)
        items.append({"kind": "app", "root": app["root"], "platform": app["platform"]["value"], "plan_id": p.id,
                      "plan_name": p.name, "ram_mb": p.ram_mb, "cpu": p.cpu, "toman_month": p.toman_month,
                      "toman_hour": p.toman_hour, "why": f"{need}MB: {app['ram_estimate_mb']['basis']}"})  # fmt: skip
    db = detected.get("database")
    if db:
        ext = db.get("extensions", [])
        need = 1024 if ext else 512
        p = fit(plans, need)
        items.append({"kind": "db", "engine": db["kind"], "extensions": ext, "plan_id": p.id, "plan_name": p.name,
                      "ram_mb": p.ram_mb, "cpu": p.cpu, "toman_month": p.toman_month, "toman_hour": p.toman_hour,
                      "why": f"{need}MB: {db['kind']} + {ext}"})  # fmt: skip
    return items


def totals(items: list[dict[str, Any]], balance_toman: int | None) -> dict[str, Any]:
    month = sum(i["toman_month"] for i in items)
    hour = sum(i["toman_hour"] for i in items)
    out: dict[str, Any] = {"toman_month": month, "toman_hour": hour, "toman_day": hour * 24}
    if balance_toman is not None and hour:
        out["days_covered"] = round(balance_toman / (hour * 24), 1)  # billing is hourly (console, 2026-10-22)
    return out


def is_stale(fetched_at: datetime, now: datetime | None = None) -> bool:
    return (now or datetime.now(UTC)) - fetched_at > STALE_AFTER
