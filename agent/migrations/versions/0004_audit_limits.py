"""Audit and limits: append-only hash-chained audit_log + audit_append(), limitation_event.

Revision ID: 0004_audit_limits
Revises: 0003_agent_core
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_audit_limits"
down_revision: str | None = "0003_agent_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UP = [
    # No FKs on purpose: the log must outlive what it describes.
    r"""
create table audit_log (
  id bigint generated always as identity primary key,
  occurred_at timestamptz not null default now(),
  actor_type actor_type not null,
  actor_user_id uuid,
  project_id uuid,
  action text not null check (action ~ '^[a-z_]+\.[a-z_]+$'),
  target_type text,
  target_id uuid,
  run_id uuid,
  tool_call_id uuid,
  approval_id uuid,
  ip inet,
  user_agent text,
  data jsonb not null default '{}',
  prev_hash bytea not null,
  row_hash bytea not null
)""",
    "create index audit_log_project on audit_log (project_id, occurred_at desc)",
    "create index audit_log_target on audit_log (target_type, target_id)",
    "create index audit_log_approval on audit_log (approval_id) where approval_id is not null",
    """
create function audit_log_append_only() returns trigger language plpgsql as $$
begin
  if current_user <> 'deployar_migrator' then
    raise exception 'audit_log is append-only (% by %)', tg_op, current_user using errcode = 'P0001';
  end if;
  return coalesce(new, old);
end $$""",
    """create trigger audit_log_no_change before update or delete on audit_log
  for each row execute function audit_log_append_only()""",
    """create trigger audit_log_no_truncate before truncate on audit_log
  for each statement execute function audit_log_append_only()""",
    "revoke update, delete, truncate on audit_log from deployar_app",
    # The single insert path: one lock so the chain never forks; row_hash covers every column but the hashes.
    """
create function audit_append(
  p_actor_type actor_type, p_action text, p_actor_user_id uuid default null, p_project_id uuid default null,
  p_target_type text default null, p_target_id uuid default null, p_run_id uuid default null,
  p_tool_call_id uuid default null, p_approval_id uuid default null, p_ip inet default null,
  p_user_agent text default null, p_data jsonb default '{}'
) returns bigint language plpgsql as $$
declare
  v_id bigint;
  v_at timestamptz := now();
  v_prev bytea;
begin
  perform pg_advisory_xact_lock(hashtext('audit_log'));
  select row_hash into v_prev from audit_log order by id desc limit 1;
  v_prev := coalesce(v_prev, '\\x0000000000000000000000000000000000000000000000000000000000000000'::bytea);
  v_id := nextval(pg_get_serial_sequence('audit_log', 'id'));
  insert into audit_log overriding system value values (
    v_id, v_at, p_actor_type, p_actor_user_id, p_project_id, p_action, p_target_type, p_target_id,
    p_run_id, p_tool_call_id, p_approval_id, p_ip, p_user_agent, p_data, v_prev,
    sha256(v_prev || convert_to(jsonb_build_object(
      'id', v_id, 'occurred_at', v_at, 'actor_type', p_actor_type, 'actor_user_id', p_actor_user_id,
      'project_id', p_project_id, 'action', p_action, 'target_type', p_target_type,
      'target_id', p_target_id, 'run_id', p_run_id, 'tool_call_id', p_tool_call_id,
      'approval_id', p_approval_id, 'ip', p_ip, 'user_agent', p_user_agent, 'data', p_data
    )::text, 'UTF8')));
  return v_id;
end $$""",
    """
create table limitation_event (
  id uuid primary key default uuid_generate_v7(),
  user_id uuid not null references "user" on delete cascade,
  project_id uuid references project on delete cascade,
  run_id uuid references run on delete set null,
  tool_call_id uuid references tool_call on delete set null,
  capability text not null,
  kind limitation_kind not null,
  message_fa text not null,
  guide_key text,
  acknowledged_at timestamptz,
  created_at timestamptz not null default now()
)""",
    "create index limitation_event_by_capability on limitation_event (capability, created_at)",
]

DOWN = [
    "drop table limitation_event",
    "drop function audit_append",
    "drop table audit_log",
    "drop function audit_log_append_only()",
]


def upgrade() -> None:
    for sql in UP:
        op.execute(sql)


def downgrade() -> None:
    for sql in DOWN:
        op.execute(sql)
