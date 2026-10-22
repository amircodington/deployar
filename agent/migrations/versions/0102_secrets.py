"""Server-side secret values for set_env (ADR: value_refs), and Liara resources Deployar created.

secret_value: DATABASE_URL from create_database, generated keys, values the user posts to
/api/projects/{id}/env-values. The model only ever sees the row id (a value_ref), never the value.

Revision ID: 0102_secrets
Revises: 0101_deploy
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0102_secrets"
down_revision: str | None = "0101_deploy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UP = [
    r"""
create table secret_value (
  id uuid primary key default uuid_generate_v7(),
  user_id uuid not null references "user" on delete cascade,
  project_id uuid references project on delete cascade,
  key text not null check (key ~ '^[A-Za-z_][A-Za-z0-9_]{0,127}$'),
  ciphertext bytea not null,
  key_version smallint not null,
  origin text not null check (origin in ('database', 'generated', 'user')),
  created_at timestamptz not null default now(),
  used_at timestamptz
)""",
    "create index secret_value_project on secret_value (project_id, key)",
    """
create table liara_resource (
  id uuid primary key default uuid_generate_v7(),
  user_id uuid not null references "user" on delete cascade,
  project_id uuid references project on delete set null,
  kind text not null check (kind in ('network', 'app', 'database')),
  name text not null,
  liara_id text,
  plan_id text,
  run_id uuid references run on delete set null,
  created_at timestamptz not null default now(),
  unique (user_id, kind, name)
)""",
]

DOWN = ["drop table liara_resource", "drop table secret_value"]


def upgrade() -> None:
    for sql in UP:
        op.execute(sql)


def downgrade() -> None:
    for sql in DOWN:
        op.execute(sql)
