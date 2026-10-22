"""Base: extensions, uuid_generate_v7(), touch_updated_at(), P0 enum types, roles and default grants.

Revision ID: 0001_base
Revises:
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_base"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUMS = {
    "user_role": ["member", "admin"],
    "connection_status": ["active", "expired", "revoked", "invalid"],
    "project_status": ["draft", "provisioning", "live", "degraded", "down", "archived"],
    "message_role": ["user", "assistant", "system", "tool"],
    "run_kind": ["chat", "deploy", "sre", "code_fix", "check"],
    "run_trigger": ["user_message", "schedule", "approval_resume", "retry", "eval"],
    "run_status": ["queued", "running", "awaiting_approval", "succeeded", "failed", "cancelled"],
    "step_status": ["pending", "running", "blocked", "done", "failed", "skipped"],
    "risk_class": ["read", "sensitive", "human_only"],
    "tool_call_status": [
        "proposed", "awaiting_approval", "running", "succeeded", "failed", "rejected", "expired", "limitation",
    ],
    "approval_status": ["pending", "approved", "rejected", "expired", "cancelled", "invalidated", "executed", "failed"],
    "approval_decision": ["approve", "reject"],
    "actor_type": ["user", "agent", "worker", "system"],
    "limitation_kind": ["human_only", "api_missing", "plan_restricted"],
}  # fmt: skip

ROLES = ["deployar_migrator", "deployar_app", "deployar_readonly"]


def upgrade() -> None:
    op.execute("create extension if not exists pgcrypto")
    op.execute("create extension if not exists citext")
    # PG16 has no uuidv7(); swap for the built-in on PG18 (DATA-MODEL.md, conventions).
    op.execute("""
create function uuid_generate_v7() returns uuid language sql volatile as $$
  select encode(set_bit(set_bit(overlay(uuid_send(gen_random_uuid())
    placing substring(int8send(floor(extract(epoch from clock_timestamp()) * 1000)::bigint) from 3)
    from 1 for 6), 52, 1), 53, 1), 'hex')::uuid;
$$""")
    op.execute("""
create function touch_updated_at() returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$""")
    for name, values in ENUMS.items():
        op.execute(f"create type {name} as enum ({', '.join(repr(v) for v in values)})")

    # Roles are cluster-wide, so they are created if missing and never dropped by a downgrade.
    for role in ROLES:
        op.execute(f"""
do $$ begin
  if not exists (select from pg_roles where rolname = '{role}') then create role {role} nologin; end if;
end $$""")
    op.execute("grant usage on schema public to deployar_app, deployar_readonly")
    op.execute("grant all on schema public to deployar_migrator")
    op.execute(
        "alter default privileges in schema public grant select, insert, update, delete on tables to deployar_app"
    )
    op.execute("alter default privileges in schema public grant usage, select on sequences to deployar_app")
    op.execute("alter default privileges in schema public grant select on tables to deployar_readonly")


def downgrade() -> None:
    # Removes this database's grants and default privileges for the roles; the roles stay.
    op.execute(f"drop owned by {', '.join(ROLES)}")
    for name in reversed(ENUMS):
        op.execute(f"drop type {name}")
    op.execute("drop function touch_updated_at()")
    op.execute("drop function uuid_generate_v7()")
    op.execute("drop extension citext")
    op.execute("drop extension pgcrypto")
