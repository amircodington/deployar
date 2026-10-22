# همکار فنی (Server Assistant, Liara challenge)

Persian assistant that deploys a developer's app to Liara and runs an SRE loop (evidence → ranked
causes → approval → action → verify). Starcoach hackathon, Liara challenge (300 pts). Talk with
Mohammad in Persian; code, commits and docs in English; UI text in Persian.

## Read first
- `docs/00-BRAINSTORM-AND-PLAN.md`, `docs/decisions.md` (numbered; never reverse silently).
- `docs/SYSTEM-DESIGN.md`, `docs/ARCHITECTURE.md`, `docs/DATA-MODEL.md`, `docs/TASKS.md`.
- Brand: `docs/design/brand/README.md` + `tokens.json`. Published artifacts: plan §10.
- Brief: `~/Workspace/starcoach-hackathon/challenges/liara.html`.

## Stack (decided)
`web/` Next.js 16 + TS + Tailwind v4 (pnpm) · `agent/` Python 3.13 FastAPI on uv with the Claude
Agent SDK driving the local Claude Code login (LLMClient seam; BoxAPI later) · `worker/` arq ·
PostgreSQL 16 · Redis 7 · Docker Compose · Makefile `dev / check / push-test`. No amox-os.

## Hard rules
1. Approval is enforced in code (`can_use_tool` + DB trigger), never only in the prompt. Risk
   classes: read / sensitive / human_only; amber UI only for sensitive.
2. Liara and GitHub tokens never enter the LLM context or logs.
3. Every number shown carries its source tool and timestamp; after any action, verify and show
   before/after.
4. When the API can't do something, show a LimitationNote; never fake it.
5. Nothing loads from outside Iran at runtime in the product (fonts, icons self-hosted).
6. Ask Mohammad before anything that spends money or can't be undone.

## Workflow
superpowers (brainstorming → writing-plans → executing-plans, TDD for the gate and diagnosis),
ponytail always on (`ponytail:` on shortcuts), `/graphify` per phase, Emil Kowalski UI skills,
`dataviz` for charts. Small commits, `make check` before push.
