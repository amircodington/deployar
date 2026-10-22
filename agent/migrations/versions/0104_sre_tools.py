"""Risk table: report_diagnosis and verify_after_action (read), B-19.

Revision ID: 0104_sre_tools
Revises: 0103_watch_tools
Create Date: 2026-10-22
"""

import importlib
from collections.abc import Sequence

from alembic import op

revision: str = "0104_sre_tools"
down_revision: str | None = "0103_watch_tools"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_0101 = importlib.import_module("migrations.versions.0101_deploy")
_0103 = importlib.import_module("migrations.versions.0103_watch_tools")
AFTER = (*_0103.AFTER, "report_diagnosis", "verify_after_action")


def upgrade() -> None:
    op.execute("alter table tool_call drop constraint tool_call_risk_matches_name")
    op.execute(_0101._risk_check(AFTER))


def downgrade() -> None:
    op.execute("alter table tool_call drop constraint tool_call_risk_matches_name")
    op.execute(_0101._risk_check(_0103.AFTER))
