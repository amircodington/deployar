"""Risk table: list_databases (read).

Revision ID: 0106_list_databases
Revises: 0105_delete_tools
Create Date: 2026-10-23
"""

import importlib
from collections.abc import Sequence

from alembic import op

revision: str = "0106_list_databases"
down_revision: str | None = "0105_delete_tools"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_0101 = importlib.import_module("migrations.versions.0101_deploy")
_0104 = importlib.import_module("migrations.versions.0104_sre_tools")
_0105 = importlib.import_module("migrations.versions.0105_delete_tools")
READ = (*_0104.AFTER, "list_databases")


def _check(read: tuple[str, ...]) -> str:
    q = lambda names: ", ".join(f"'{n}'" for n in names)  # noqa: E731
    return f"""alter table tool_call add constraint tool_call_risk_matches_name check (
  case
    when name in ({q(read)}) then risk_class = 'read'
    when name in ({q(_0105.SENSITIVE)}) then risk_class = 'sensitive'
    when name in ({q(_0101.HUMAN_ONLY_TOOLS)}) then risk_class = 'human_only'
    else false
  end)"""


def upgrade() -> None:
    op.execute("alter table tool_call drop constraint tool_call_risk_matches_name")
    op.execute(_check(READ))


def downgrade() -> None:
    op.execute("alter table tool_call drop constraint tool_call_risk_matches_name")
    op.execute(_check(_0104.AFTER))
