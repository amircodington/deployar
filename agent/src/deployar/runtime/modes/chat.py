"""chat mode: answer with read tools only (SYSTEM-DESIGN.md §4)."""

MODE = "chat"
MAX_TURNS = 12
STEPS = [{"key": "answer", "label_fa": "پاسخ به پرسش"}]
PROMPT_FILE = "base_fa.md"
