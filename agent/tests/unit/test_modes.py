"""Every mode is a run_kind the DB accepts, and the text picks the right one."""

import pytest

from deployar.models.enums import ENUMS
from deployar.runtime.orchestrator import DEPLOY_HINT, INCIDENT_HINT, MODES


def test_mode_names_are_run_kinds() -> None:
    assert set(MODES) <= set(ENUMS["run_kind"])
    for spec in MODES.values():
        assert spec.MODE in ENUMS["run_kind"]


@pytest.mark.parametrize(("text", "deploy", "incident"), [
    ("ترب‌گرد را روی لیارا بالا بیاور", True, False),
    ("از صبح سایت خیلی کند شده", False, True),
    ("سایت ۵۰۰ می‌دهد", False, True),
    ("موجودی لیارا چقدر است؟", False, False),
])  # fmt: skip
def test_hints(text: str, deploy: bool, incident: bool) -> None:
    assert bool(DEPLOY_HINT.search(text)) is deploy
    assert bool(INCIDENT_HINT.search(text)) is incident
