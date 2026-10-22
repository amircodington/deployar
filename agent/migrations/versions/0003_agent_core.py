"""Agent core: project, conversation, message, run, run_step, tool_call (+ risk checks, gate trigger), approval.

project.current_deployment_id lands in 0101 and run.incident_id in 0201 (DATA-MODEL.md, migration plan).

Revision ID: 0003_agent_core
Revises: 0002_identity
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_agent_core"
down_revision: str | None = "0002_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

READ_TOOLS = (
    "analyze_repo",
    "list_plans",
    "get_balance",
    "get_app_status",
    "get_logs",
    "get_metrics",
    "list_releases",
    "get_env_keys",
    "check_dns",
    "http_probe",
)
SENSITIVE_TOOLS = (
    "create_app",
    "create_database",
    "set_env",
    "deploy_release",
    "restart_app",
    "resize_plan",
    "rollback_release",
    "add_domain",
    "apply_code_fix",
    "merge_and_deploy",
)
HUMAN_ONLY_TOOLS = ("top_up_balance", "registrar_dns_records")  # fmt: skip


def _in(names: tuple[str, ...]) -> str:
    return ", ".join(f"'{n}'" for n in names)


UP = [
    r"""
create table project (
  id uuid primary key default uuid_generate_v7(),
  user_id uuid not null references "user" on delete cascade,
  liara_connection_id uuid not null references liara_connection on delete no action,
  github_connection_id uuid references github_connection on delete set null,
  name text not null,
  repo_full_name text check (repo_full_name ~ '^[\w.-]+/[\w.-]+$'),
  repo_default_branch text,
  liara_app_name text check (liara_app_name ~ '^[a-z0-9-]{3,32}$'),
  platform text,
  plan_id text,
  liara_db_name text,
  db_kind text check (db_kind in ('postgres', 'mysql', 'mariadb', 'mongodb', 'redis')),
  live_url text,
  status project_status not null default 'draft',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  archived_at timestamptz
)""",
    """create unique index project_liara_app on project (liara_connection_id, liara_app_name)
  where liara_app_name is not null""",
    "create index project_switcher on project (user_id, updated_at desc) where archived_at is null",
    "create trigger project_touch before update on project for each row execute function touch_updated_at()",
    """
create table conversation (
  id uuid primary key default uuid_generate_v7(),
  user_id uuid not null references "user" on delete cascade,
  project_id uuid references project on delete set null,
  title_fa text,
  agent_session_id text,
  created_at timestamptz not null default now(),
  last_message_at timestamptz not null default now(),
  archived_at timestamptz
)""",
    "create index conversation_sidebar on conversation (user_id, last_message_at desc) where archived_at is null",
    """
create table message (
  id uuid primary key default uuid_generate_v7(),
  conversation_id uuid not null references conversation on delete cascade,
  seq int not null,
  role message_role not null,
  content jsonb not null,
  model text,
  tokens_in int,
  tokens_out int,
  latency_ms int,
  created_at timestamptz not null default now(),
  unique (conversation_id, seq)
)""",
    """
create table run (
  id uuid primary key default uuid_generate_v7(),
  project_id uuid references project on delete cascade,
  conversation_id uuid references conversation on delete set null,
  triggered_by_message_id uuid references message on delete set null,
  parent_run_id uuid references run on delete cascade,
  kind run_kind not null,
  trigger run_trigger not null,
  status run_status not null default 'queued',
  arq_job_id text,
  error jsonb,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz check (finished_at is null or finished_at >= started_at)
)""",
    "create index run_project_history on run (project_id, created_at desc)",
    "create index run_active on run (project_id) where status in ('queued', 'running', 'awaiting_approval')",
    f"""
create table tool_call (
  id uuid primary key default uuid_generate_v7(),
  run_id uuid not null references run on delete cascade,
  message_id uuid references message on delete set null,
  name text not null,
  risk_class risk_class not null,
  args jsonb not null default '{{}}',
  args_hash bytea not null,
  secret_args_ciphertext bytea,
  secret_key_version smallint,
  idempotency_key text not null unique,
  status tool_call_status not null default 'proposed',
  result_summary jsonb,
  liara_request_id text,
  http_status smallint,
  duration_ms int,
  error jsonb,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  check (secret_args_ciphertext is null or secret_key_version is not null),
  -- the risk table lives in the database too, so a bug in the gate can't misclassify a tool
  constraint tool_call_risk_matches_name check (
    case
      when name in ({_in(READ_TOOLS)}) then risk_class = 'read'
      when name in ({_in(SENSITIVE_TOOLS)}) then risk_class = 'sensitive'
      when name in ({_in(HUMAN_ONLY_TOOLS)}) then risk_class = 'human_only'
      else false
    end),
  constraint tool_call_human_only_never_runs check (risk_class <> 'human_only' or status = 'limitation'),
  constraint tool_call_read_no_approval
    check (risk_class <> 'read' or status not in ('awaiting_approval', 'rejected', 'expired'))
)""",
    "create index tool_call_run_trace on tool_call (run_id, created_at)",
    "create index tool_call_by_name on tool_call (name, created_at desc)",
    """
create table run_step (
  id uuid primary key default uuid_generate_v7(),
  run_id uuid not null references run on delete cascade,
  seq smallint not null,
  key text not null,
  label_fa text not null,
  status step_status not null default 'pending',
  tool_call_id uuid references tool_call on delete set null,
  detail_fa text,
  started_at timestamptz,
  finished_at timestamptz,
  unique (run_id, seq),
  unique (run_id, key)
)""",
    """
create table approval (
  id uuid primary key default uuid_generate_v7(),
  tool_call_id uuid not null unique references tool_call on delete cascade,
  run_id uuid not null references run on delete cascade,
  project_id uuid not null references project on delete cascade,
  user_id uuid not null references "user" on delete cascade,
  status approval_status not null default 'pending',
  preview jsonb not null,
  args_hash bytea not null,
  signature bytea not null,
  expires_at timestamptz not null default now() + interval '10 minutes',
  decision approval_decision,
  decided_by uuid references "user" on delete set null,
  decided_at timestamptz,
  reject_reason_fa text,
  executed_at timestamptz,
  created_at timestamptz not null default now(),
  check (expires_at <= created_at + interval '10 minutes'),
  check ((decision is null) = (decided_at is null)),
  check (decided_at is null or decided_at <= expires_at),
  check (status not in ('approved', 'executed', 'failed') or decision = 'approve'),
  check ((status = 'rejected') = (coalesce(decision = 'reject', false)))
)""",
    "create index approval_inbox on approval (user_id, expires_at) where status = 'pending'",
    "create index approval_by_run on approval (run_id)",
    # Defence in depth behind the Python gate: a sensitive call cannot start or be recorded as done
    # without an approved approval for the same args. Stricter than DATA-MODEL's sketch: it also
    # covers INSERT and a direct jump to succeeded, and freezes args_hash once running.
    """
create function tool_call_gate() returns trigger language plpgsql as $$
begin
  if new.risk_class <> 'sensitive' or new.status not in ('running', 'succeeded') then
    return new;
  end if;
  if tg_op = 'UPDATE' and old.status in ('running', 'succeeded') then
    if new.args_hash is distinct from old.args_hash then
      raise exception 'tool_call %: args changed after release', new.id using errcode = 'P0001';
    end if;
    return new;
  end if;
  perform 1 from approval a
   where a.tool_call_id = new.id and a.status = 'approved' and a.args_hash = new.args_hash;
  if not found then
    raise exception 'sensitive tool_call % has no approved approval', new.id using errcode = 'P0001';
  end if;
  return new;
end $$""",
    """create trigger tool_call_gate before insert or update on tool_call
  for each row execute function tool_call_gate()""",
    "revoke select on tool_call from deployar_readonly",
    """grant select (id, run_id, message_id, name, risk_class, args, args_hash, secret_key_version,
  idempotency_key, status, result_summary, liara_request_id, http_status, duration_ms, error, created_at,
  started_at, finished_at) on tool_call to deployar_readonly""",
]

DOWN = [
    "drop table approval",
    "drop table run_step",
    "drop table tool_call",
    "drop function tool_call_gate()",
    "drop table run",
    "drop table message",
    "drop table conversation",
    "drop table project",
]


def upgrade() -> None:
    for sql in UP:
        op.execute(sql)


def downgrade() -> None:
    for sql in DOWN:
        op.execute(sql)
