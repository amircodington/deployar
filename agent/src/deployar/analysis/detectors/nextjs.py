"""Next.js specifics: default port, the build being the RAM peak."""

from typing import Any

from deployar.analysis.detectors.common import fact


def refine(app: dict[str, Any]) -> None:
    if app.get("platform", {}).get("value") != "next":
        return
    app.setdefault("port", fact(3000, "next default"))
    app["ram_estimate_mb"] = {"value": 1024, "basis": "next build is the memory peak; rule ram.next.v1"}
