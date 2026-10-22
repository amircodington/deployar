"""deploy mode: repo → plan → approvals → app, DB, env → release → live URL (SYSTEM-DESIGN.md §4–5).

A step turns running when the model first calls one of its tools; earlier steps are then done.
"""

MODE = "deploy"
MAX_TURNS = 40
STEPS = [
    {"key": "analyze", "label_fa": "خواندن مخزن", "tools": ["analyze_repo"]},
    {"key": "plan", "label_fa": "پیشنهاد پلن و هزینه", "tools": ["propose_plan", "list_plans", "get_balance"]},
    {"key": "create", "label_fa": "ساخت اپ و دیتابیس", "tools": ["create_app", "create_database"]},
    {"key": "env", "label_fa": "تنظیم متغیرها", "tools": ["set_env", "request_env_values"]},
    {"key": "release", "label_fa": "ساخت و انتشار", "tools": ["deploy_release", "watch_deployment"]},
]
PROMPT_FILE = "deploy_fa.md"
