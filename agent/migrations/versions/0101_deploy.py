"""P1 first deploy: repo_analysis, plan_proposal, deployment, domain; project.current_deployment_id.

Also widens the tool risk table with propose_plan (read).

Revision ID: 0101_deploy
Revises: 0004_audit_limits
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0101_deploy"
down_revision: str | None = "0004_audit_limits"
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


def _risk_check(read_tools: tuple[str, ...]) -> str:
    q = lambda names: ", ".join(f"'{n}'" for n in names)  # noqa: E731
    return f"""alter table tool_call add constraint tool_call_risk_matches_name check (
  case
    when name in ({q(read_tools)}) then risk_class = 'read'
    when name in ({q(SENSITIVE_TOOLS)}) then risk_class = 'sensitive'
    when name in ({q(HUMAN_ONLY_TOOLS)}) then risk_class = 'human_only'
    else false
  end)"""


UP = [
    "create type proposal_status as enum ('proposed', 'accepted', 'rejected', 'superseded')",
    """create type deployment_status as enum ('queued', 'uploading', 'building', 'releasing', 'health_check',
  'live', 'failed', 'superseded', 'rolled_back')""",
    "create type domain_status as enum ('pending_dns', 'active', 'failed', 'removed')",
    r"""
create table repo_analysis (
  id uuid primary key default uuid_generate_v7(),
  project_id uuid not null references project on delete cascade,
  run_id uuid references run on delete set null,
  commit_sha text not null check (commit_sha ~ '^[0-9a-f]{40}$'),
  detector_version text not null,
  detected jsonb not null,
  summary_fa text,
  created_at timestamptz not null default now(),
  unique (project_id, commit_sha, detector_version)
)""",
    "create index repo_analysis_latest on repo_analysis (project_id, created_at desc)",
    # items: one line per app plus the database (a monorepo has several apps); totals are their sum.
    """
create table plan_proposal (
  id uuid primary key default uuid_generate_v7(),
  project_id uuid not null references project on delete cascade,
  repo_analysis_id uuid not null references repo_analysis on delete cascade,
  run_id uuid references run on delete set null,
  items jsonb not null,
  app_plan_id text not null,
  app_price_monthly_rial bigint not null check (app_price_monthly_rial >= 0),
  db_plan_id text,
  db_price_monthly_rial bigint,
  total_monthly_rial bigint not null check (total_monthly_rial >= 0),
  total_hourly_rial bigint not null check (total_hourly_rial >= 0),
  balance_rial bigint,
  price_source text not null,
  prices_fetched_at timestamptz not null,
  reasoning_fa text not null,
  alternatives jsonb not null default '[]',
  status proposal_status not null default 'proposed',
  created_at timestamptz not null default now(),
  decided_at timestamptz,
  check ((db_plan_id is null) = (db_price_monthly_rial is null))
)""",
    "create unique index plan_proposal_one_open on plan_proposal (project_id) where status = 'proposed'",
    r"""
create table deployment (
  id uuid primary key default uuid_generate_v7(),
  project_id uuid not null references project on delete cascade,
  run_id uuid not null references run on delete cascade,
  tool_call_id uuid references tool_call on delete set null,
  rolled_back_from_id uuid references deployment on delete set null,
  app_root text not null default '.',
  liara_app_name text not null,
  commit_sha text not null check (commit_sha ~ '^[0-9a-f]{40}$'),
  source text not null default 'github_tarball' check (source in ('github_tarball', 'liara_rollback')),
  liara_source_id text,
  liara_release_id text,
  status deployment_status not null default 'queued',
  build_log_tail text,
  health jsonb,
  error_fa text,
  created_at timestamptz not null default now(),
  live_at timestamptz,
  finished_at timestamptz,
  check ((status in ('live', 'superseded', 'rolled_back')) <= (live_at is not null))
)""",
    """create unique index deployment_one_in_flight on deployment (project_id, app_root)
  where status in ('queued', 'uploading', 'building', 'releasing', 'health_check')""",
    "create index deployment_history on deployment (project_id, created_at desc)",
    r"""
create table domain (
  id uuid primary key default uuid_generate_v7(),
  project_id uuid not null references project on delete cascade,
  hostname citext not null check (hostname ~ '^([a-z0-9-]+\.)+[a-z]{2,}$'),
  liara_domain_id text,
  status domain_status not null default 'pending_dns',
  required_records jsonb not null,
  last_check jsonb,
  last_checked_at timestamptz,
  verified_at timestamptz,
  created_at timestamptz not null default now()
)""",
    "alter table project add column current_deployment_id uuid references deployment on delete set null",
    # One project per deployable app: a monorepo (ترب‌گرد: api + web) becomes two projects on one repo.
    "alter table project add column app_root text not null default '.'",
    "alter table tool_call drop constraint tool_call_risk_matches_name",
    _risk_check((*READ_TOOLS, "propose_plan")),
]

DOWN = [
    "alter table tool_call drop constraint tool_call_risk_matches_name",
    _risk_check(READ_TOOLS),
    "alter table project drop column app_root",
    "alter table project drop column current_deployment_id",
    "drop table domain",
    "drop table deployment",
    "drop table plan_proposal",
    "drop table repo_analysis",
    "drop type domain_status",
    "drop type deployment_status",
    "drop type proposal_status",
]


def upgrade() -> None:
    for sql in UP:
        op.execute(sql)


def downgrade() -> None:
    for sql in DOWN:
        op.execute(sql)
