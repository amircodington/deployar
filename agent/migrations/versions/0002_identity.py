"""Identity: user, liara_connection, github_connection (fine-grained token, BUILD.md defaults).

Revision ID: 0002_identity
Revises: 0001_base
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_identity"
down_revision: str | None = "0001_base"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UP = [
    """
create table "user" (
  id uuid primary key default uuid_generate_v7(),
  email citext not null unique,
  display_name text,
  role user_role not null default 'member',
  locale text not null default 'fa-IR' check (locale in ('fa-IR', 'en')),
  created_at timestamptz not null default now(),
  last_seen_at timestamptz,
  deleted_at timestamptz
)""",
    """
create table liara_connection (
  id uuid primary key default uuid_generate_v7(),
  user_id uuid not null references "user" on delete cascade,
  label text not null default 'Liara',
  token_ciphertext bytea not null,
  key_version smallint not null,
  token_last4 text not null check (length(token_last4) = 4),
  liara_account_email text,
  team_id text,
  status connection_status not null default 'active',
  expires_at timestamptz,
  last_verified_at timestamptz,
  created_at timestamptz not null default now(),
  revoked_at timestamptz,
  check ((status = 'revoked') = (revoked_at is not null))
)""",
    "create unique index liara_connection_one_active on liara_connection (user_id) where status = 'active'",
    "create index liara_connection_expiring on liara_connection (expires_at) where status = 'active'",
    """
create table github_connection (
  id uuid primary key default uuid_generate_v7(),
  user_id uuid not null references "user" on delete cascade,
  token_ciphertext bytea not null,
  key_version smallint not null,
  token_last4 text not null check (length(token_last4) = 4),
  account_login text not null,
  status connection_status not null default 'active',
  expires_at timestamptz,
  last_verified_at timestamptz,
  created_at timestamptz not null default now(),
  revoked_at timestamptz,
  check ((status = 'revoked') = (revoked_at is not null))
)""",
    "create unique index github_connection_one_active on github_connection (user_id) where status = 'active'",
    # deployar_readonly may read everything except the ciphertext columns.
    "revoke select on liara_connection, github_connection from deployar_readonly",
    """grant select (id, user_id, label, key_version, token_last4, liara_account_email, team_id, status,
  expires_at, last_verified_at, created_at, revoked_at) on liara_connection to deployar_readonly""",
    """grant select (id, user_id, key_version, token_last4, account_login, status, expires_at,
  last_verified_at, created_at, revoked_at) on github_connection to deployar_readonly""",
]

DOWN = ["drop table github_connection", "drop table liara_connection", 'drop table "user"']


def upgrade() -> None:
    for sql in UP:
        op.execute(sql)


def downgrade() -> None:
    for sql in DOWN:
        op.execute(sql)
