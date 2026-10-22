"""Enum values as created by migration 0001; test_models_match_database_enums keeps them in sync."""

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
