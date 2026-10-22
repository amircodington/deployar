"""incident mode: symptom → evidence → ranked causes → approval → action → verify (SYSTEM-DESIGN.md §4, §6)."""

MODE = "sre"  # run_kind enum value
MAX_TURNS = 40
STEPS = [
    {"key": "evidence", "label_fa": "جمع کردن شواهد",
     "tools": ["get_app_status", "get_logs", "get_metrics", "list_releases", "http_probe", "get_env_keys"]},
    {"key": "diagnose", "label_fa": "علت‌های محتمل", "tools": ["report_diagnosis"]},
    {"key": "act", "label_fa": "اقدام با تأیید تو",
     "tools": ["restart_app", "resize_plan", "set_env", "deploy_release"]},
    {"key": "verify", "label_fa": "اندازه‌گیری دوباره", "tools": ["verify_after_action", "watch_deployment"]},
]  # fmt: skip
PROMPT_FILE = "incident_fa.md"
