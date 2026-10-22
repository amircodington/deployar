import json, sys, re
sys.path.insert(0, sys.argv[1])
from data import TASKS, PHASES

ROOT = "/Users/amox/Workspace/server-assistant (Liara)"

RULES = [
    ("Evidence", "Everything goes in `docs/evidence/<task-id>/`. Notes as `.md`, data as `.csv` (UTF-8, header row, ASCII digits), structured data as `.json` (must pass `python3 -m json.tool`), screenshots as `NN-what.png` ≤ 1 MB. Videos and raw recordings never go in git: put a link in a `.md`."),
    ("Header", "Every note starts with `> Author: <name> · Date: YYYY-MM-DD · Task: T-xx`."),
    ("Never invent", "No guessed values. If you do not know, write `unknown` and say why in `notes`. A wrong number is worse than an empty one."),
    ("Token", "Never paste the Liara token or a GitHub token anywhere: not in notes, CSV, screenshots, chat, commits or command lines you save. Load it with `read -s LIARA_TOKEN`. Redact as `Authorization: Bearer <REDACTED>`. If one leaks, tell Mohammad at once so he revokes it."),
    ("Safety", "Never press a paid or destructive button on Liara (create app/DB, change plan, restart, deploy, delete, add domain, change env, top-up payment) or an approval card in our app without Mohammad present and saying yes. Tasks marked **Needs Mohammad** say exactly which steps."),
    ("Report", "Post in the project chat as `T-xx · done|blocked · one line · link`. Ask early when stuck; a wrong assumption costs a day."),
]

NAMES = """Tools (read, automatic): `analyze_repo`, `list_plans`, `get_balance`, `get_app_status`, `get_logs`, `get_metrics`, `list_releases`, `get_env_keys`, `check_dns`, `http_probe`.
Tools (sensitive, approval card): `create_app`, `create_database`, `set_env`, `deploy_release`, `restart_app`, `resize_plan`, `rollback_release`, `add_domain`, `apply_code_fix`, `merge_and_deploy`.
Tools (human_only, guide + limitation box): `top_up_balance`, `registrar_dns_records`.
Tables: `eval_case`, `eval_run`, `limitation_event` (see `docs/DATA-MODEL.md`). Design docs: `docs/SYSTEM-DESIGN.md`, `docs/ARCHITECTURE.md`, `docs/DATA-MODEL.md`."""

CHECKLISTS = [
    ("Before reporting a bug", "Can you repeat it twice? Browser + width + theme; screenshot (no token); exact text you typed; time (Tehran); action log row if any."),
    ("Before marking data done", "No empty cells (`unknown` instead); ASCII digits in CSV; JSON validates; file opens in Excel/Numbers; your name and date on top."),
    ("Before sharing a screenshot", "Token, balance, email, phone, connection strings, env values blurred; browser autofill closed; no other tabs with private data."),
]


def deps(t):
    return ", ".join(t["deps"]) or "—"


def task_md(t):
    L = [f"### {t['id']} · {t['title']} · {t['type']} · {t['owner']} · {t['est']}",
         f"**Phase** {t['phase']} {PHASES[t['phase']]} · **Depends on** {deps(t)}"]
    if t["approval"]:
        L.append(f"**Needs Mohammad:** {t['approval']}")
    L.append(f"**Why:** {t['why']}")
    L.append("**Inputs:**\n" + "\n".join(f"- {x}" for x in t["inputs"]))
    L.append("**Steps:**\n" + "\n".join(f"{i}. {x}" for i, x in enumerate(t["steps"], 1)))
    L.append("**Done when:**\n" + "\n".join(f"- [ ] {x}" for x in t["done"]))
    L.append(f"**Evidence:** `{t['evidence']}`")
    L.append(f"**Report:** `{t['report']}`")
    if t["template"]:
        L.append(f"**Template:**\n```{t['lang']}\n{t['template']}\n```")
    return "\n\n".join(L)


for t in TASKS:
    t["md"] = task_md(t)

# ---------------- TASKS.md
md = ["# Task book — team",
      "",
      "For the two students (Student A, Student B). Mohammad builds the software with Claude Code; you do R&D, tests, docs, checks and evidence. "
      "Each task: why, inputs, steps, what \"done\" looks like, where the evidence goes, what to post. Interactive version: `docs/artifacts/task-book.html`.",
      "",
      "## Rules for every task",
      ""]
md += [f"- **{k}.** {v}" for k, v in RULES]
md += ["", "Legend: **R&D** = research/experiment, **Docs** = writing/screenshots, **Test** = checking the product, **Data** = labelling/fixtures, **Video** = demo video. "
       "Owner **A** / **B** = Student A / Student B, **either** = whoever is free (claim it in chat first).",
       "", "Canonical names (use exactly these in notes and files):", "", NAMES, "",
       "## Board", "", "| id | title | type | owner | phase | estimate | depends | Mohammad |", "|---|---|---|---|---|---|---|---|"]
md += [f"| {t['id']} | {t['title']} | {t['type']} | {t['owner']} | {t['phase']} | {t['est']} | {deps(t)} | {'yes' if t['approval'] else ''} |" for t in TASKS]
for p, name in PHASES.items():
    md += ["", f"## {p} — {name}", ""]
    for t in TASKS:
        if t["phase"] == p:
            md += [t["md"], ""]
md += ["## Checklists used by every task", ""]
md += [f"**{k}**: {v}" + "\n" for k, v in CHECKLISTS]
open(f"{ROOT}/docs/TASKS.md", "w").write("\n".join(md).rstrip() + "\n")

# ---------------- HTML
page = open(sys.argv[1] + "/page.html").read()
payload = json.dumps({"phases": PHASES, "rules": RULES, "names": NAMES, "checklists": CHECKLISTS, "tasks": TASKS}, ensure_ascii=False)
payload = payload.replace("</", "<\\/")
open(f"{ROOT}/docs/artifacts/task-book.html", "w").write(page.replace("/*__DATA__*/null", payload))
print(len(TASKS), "tasks")
