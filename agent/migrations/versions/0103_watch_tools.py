"""Risk table: watch_deployment and request_env_values (read), B-12.

Revision ID: 0103_watch_tools
Revises: 0102_secrets
Create Date: 2026-10-22
"""

import importlib
from collections.abc import Sequence

from alembic import op

revision: str = "0103_watch_tools"
down_revision: str | None = "0102_secrets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_0101 = importlib.import_module("migrations.versions.0101_deploy")
BEFORE = (*_0101.READ_TOOLS, "propose_plan")
AFTER = (*BEFORE, "watch_deployment", "request_env_values")


def upgrade() -> None:
    op.execute("alter table tool_call drop constraint tool_call_risk_matches_name")
    op.execute(_0101._risk_check(AFTER))


def downgrade() -> None:
    op.execute("alter table tool_call drop constraint tool_call_risk_matches_name")
    op.execute(_0101._risk_check(BEFORE))
