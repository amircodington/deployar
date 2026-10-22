# Server Assistant (Liara) — brainstorm and plan

Written 2026-10-22. First document of the project: the idea, the stack to agree on, an architecture
sketch, the Liara API surface, roadmap, and how Claude Code works in this repo. Working draft for
discussion; agreed items move to `docs/decisions.md`.

Source of truth for scope: the Starcoach hackathon Liara brief
(`~/Workspace/starcoach-hackathon/challenges/liara.html`). Same hackathon and same team as
In-Store Agent (Torob), so this plan reuses its conventions and decisions where they fit.

Working name: **همکار فنی** (working title, from the brief: «همکار فنی برای صاحب وب‌سایت»).

---

## 1. What this is

A Persian assistant that acts as the developer's DevOps/SRE colleague on Liara. The developer says
«این را آنلاین کن» with a GitHub link; the assistant reads the repo, proposes a Liara plan, asks for a
yes, creates the app + database, sets env vars, deploys, and walks them through the domain panel.
Later, when they say «سایتم کند شده», it collects logs, metrics and status, ranks likely causes,
proposes a fix (restart, resize, or a code fix via a coding agent), asks for a yes where it matters,
acts, and **re-reads the metrics to prove it worked**.

Scoring (300): Liara integration 100 · intelligence 100 · UX 50 · reliability & security 50.
Required: runnable MVP covering one real scenario end to end, approval card before every sensitive
action, explicit "the API can't do this" messages, an `.md` doc (architecture, Liara API usage,
limits, interaction), a ~5-minute demo video.

## 2. Brainstorm — ideas, ranked

### Tier 1 — the MVP (what the judges score)

| # | Idea | Criterion it scores |
|---|------|---------------------|
| 1 | **Repo analyzer**: read the GitHub repo (package.json, requirements, Dockerfile, prisma/schema, `.env.example`) → platform, runtime version, DB needs, env vars, RAM estimate. Deterministic detectors first, LLM only to explain. | Integration, intelligence |
| 2 | **Plan proposal card**: Liara platform + plan + DB with the price from the API, "I won't spend money until you say yes". | UX, safety |
| 3 | **First deploy pipeline**: create app → create DB → wire `DATABASE_URL` → set env → deploy release → stream build logs → health check → live URL. Each step a row in a live checklist. | Integration (biggest chunk) |
| 4 | **Domain guide**: add domain on Liara via API, then a 3-step illustrated guide for IRNIC/registrar NS or CNAME records, with a "check now" DNS probe. | UX, "only the human does what the API can't" |
| 5 | **SRE loop** ("سایتم کند/خراب شده"): evidence (logs, CPU/RAM, restarts, release history) → ranked hypotheses with confidence → actions → approval → act → **verify** with before/after numbers. | Intelligence (whole 100) |
| 6 | **Approval gate** in code, not in the prompt: every tool has a risk class (`read`, `sensitive`, `human_only`); sensitive tools return a pending action that only a signed user click can execute. | Security 50 |
| 7 | **Limit honesty**: a tool that the API doesn't support returns `limitation` with a Persian sentence; the UI shows it as a grey box. | Security 50 |
| 8 | **Coding-agent fix**: for code-rooted causes, hand a brief to a coding agent, open a branch/PR, show the diff, deploy on approval, verify. | Intelligence + "the video asks for it" |

### Tier 2 — strong, after the MVP

| # | Idea |
|---|------|
| 9 | **Rollback in one tap** to the last healthy release (sensitive). |
| 10 | **Fault lab for the demo**: a tiny sample app with switches (`/leak` memory, `/boom` 500, slow query) so failures are real and repeatable. |
| 11 | **Recurring checks** (the brief's "automate repetitive ops"): scheduled health probe + backup check + "your plan is 90% RAM all week" digest. No 24/7 paging (video says not needed). |
| 12 | **Incident timeline**: every incident saved with evidence, hypotheses, actions, verification — exportable as a post-mortem. |
| 13 | **MCP server** exposing the same tools, so Claude Code (the user's coding agent) can call "deploy" and "read logs" directly. |
| 14 | **CLI** (`hamkar deploy`, `hamkar why-slow`) as a thin client of the same API. |

### Tier 3 — later

Cost advisor (right-size plans), multi-app projects, team accounts, ArvanCloud/other PaaS adapters.

### Anti-goals

- Spending money or restarting anything without an explicit click. No "auto" mode for sensitive tools.
- Claiming a capability Liara's API doesn't have; faking a metric. Every number carries its source.
- A wall of chat text. Status is a live checklist and cards; prose is short Persian.
- Storing the user's Liara token in plain text, or in the LLM context. Tokens never reach the model.
- 24/7 monitoring infrastructure (Prometheus/Grafana). Out of scope; read Liara's own metrics.

## 3. The Liara API surface (to verify in P0, task T-01)

Liara exposes a REST API with a bearer token from the console (expiry 1 h–1 y), and the official
`@liara/cli`. Community MCP servers (e.g. `razavioo/liara-mcp`) wrap apps, deploy/rollback, env vars,
disks, logs and metrics — useful as a map of what exists, not as a dependency.

| Need | Expected API | Risk class |
|---|---|---|
| List plans + prices, account balance | plans / user endpoints | read |
| Create app (platform, plan) | projects | sensitive (costs money) |
| Create DB (Postgres/MySQL…), get connection | databases | sensitive |
| Set env vars | app env | sensitive (restarts app) |
| Deploy release (upload tarball or build from source) | releases / deploy | sensitive |
| Build + runtime logs | logs | read |
| CPU / RAM / network metrics | metrics | read |
| App status, restart, scale/resize | app actions | sensitive |
| Domains: add, check | domains | sensitive / read |
| Top up balance, registrar panel (IRNIC) | **not in API** | human_only |
| DB slow-query logs | probably **not in API** → limitation message | — |

## 4. Stack — options to discuss

What the team already uses (Torob decision #1): Next.js 16 + TS + Tailwind v4 (pnpm), FastAPI
agent on uv, PostgreSQL 16, Redis 7, Docker Compose, Makefile `dev / check / push-test`; LLM through
BoxAPI behind one OpenAI-compatible `LLMClient` (Torob decision #2).

### Option A — recommended: Next.js web + FastAPI agent (Torob shape, minus Django)

```
web/     Next.js 16 (App Router, TS, Tailwind v4, pnpm) — chat + cards + live checklist, RTL
agent/   Python 3.13 (uv) — FastAPI: agent loop, Liara client, tools, approval gate, SSE;
         also serves the same tools over MCP (FastMCP) for Claude Code
db/      PostgreSQL 16 (users, liara connections, sessions, actions, incidents, evidence)
redis/   job queue (arq) for long deploys/verification, rate limits, SSE fan-out
lab/     fault-lab sample app (Next.js + Prisma) deployed to Liara for the demo
```

- No Django: there's no data-entry workload here (Torob needed it for students). One Python service.
- Same `LLMClient`, same Makefile, same Compose → the team learns nothing twice; code can be lifted
  from Torob's agent.
- The assistant itself is deployed **on Liara**, and it deploys the Torob app: one scenario, two demos
  (brief's own suggestion).

### Option B — one language: all TypeScript

Next.js + agent in TypeScript (Vercel AI SDK or Claude Agent SDK TS) + official MCP TS SDK; Liara's
CLI is Node too. Single repo, single toolchain. Costs: can't reuse Torob's Python agent; you'd
maintain two agent stacks across the hackathon.

### Option C — no web UI: MCP server + Claude Code as the interface

Smallest build: only the tools + approval gate, used from Claude Code/Claude Desktop. Strongest
"coding agent" story, weakest UX score (50 pts) and hard for a non-technical user — the target persona.

**Recommendation: A**, with the MCP endpoint from Tier 2 #13 added cheaply because it's the same
tool registry.

### Coding-agent fix — how

| Choice | Pros | Cons |
|---|---|---|
| **Claude Code headless** (`claude -p` in a sandbox worker, repo cloned, opens a PR) | Real coding agent, best fixes. | Needs an Anthropic-compatible endpoint from Iran (try BoxAPI as base URL); heavier worker. |
| **Our own patch tool** (LLM writes a unified diff for 1–3 files, we apply, push branch, PR) | Small, fully ours, works with any model. | Weaker on multi-file fixes. |

Recommendation: start with our own patch tool (enough for "paginate `/products`"), keep the worker
interface so Claude Code headless can replace it.

### Other defaults (say if you disagree)

- **Auth**: phone OTP (Kavenegar) or simply email magic link for the demo; Liara token stored
  encrypted (Fernet/AES-GCM, key in env), never logged, never sent to the LLM.
- **GitHub**: GitHub App (repo read + PR write) rather than personal tokens.
- **Design**: tokens in Tailwind `@theme`, Vazirmatn self-hosted, Emil Kowalski skills for motion.
- **Tests**: pytest with recorded Liara responses (VCR-style) + a live smoke suite on a test
  account; vitest + Playwright for web; an "SRE eval" set of injected incidents with expected top cause.

## 5. Architecture sketch

```
 Developer (browser)                        Claude Code (optional, via MCP)
      │ HTTPS + SSE                                 │
      ▼                                             ▼
   web (Next.js) ───────────────► agent (FastAPI) ◄─┘
                                    │  loop: understand → gather → plan → (approve) → act → verify
                                    ├─ tools.read:      analyze_repo, get_logs, get_metrics, get_status, list_plans
                                    ├─ tools.sensitive: create_app, create_db, set_env, deploy, restart, resize, rollback, apply_fix
                                    ├─ tools.human:     top_up, registrar_dns  → instructions only
                                    ├─ approval gate (pending_action, signed one-time confirm)
                                    ├─ jobs (arq): deploy watcher, verify-after-fix, scheduled checks
                                    ▼
              Liara API ◄─┤   ├─► GitHub API (read repo, branch, PR)   ├─► BoxAPI (LLM)
                          ▼
                    PostgreSQL + Redis
```

## 6. Roadmap

| Phase | Outcome |
|---|---|
| **P0 Foundation** | Repo, Compose, Makefile, CI; Liara API capability report (T-01); fault-lab app; brand book; schema v1. |
| **P1 First deploy** | «این را آنلاین کن» end to end on a real Liara account: analyze → plan card → approve → app+DB+env → deploy → live URL → domain guide. |
| **P2 SRE loop** | Evidence → ranked causes → approve → restart/resize → verify; limitation boxes; incident timeline. |
| **P3 Coding fix** | Patch tool → PR → diff card → approve → deploy → verify; MCP endpoint. |
| **P4 Ship** | Deploy the assistant on Liara, deploy Torob app with it, md doc (4 sections), eval run, 5-min video with 3 scenarios. |

## 7. How Claude Code works in this repo

Same as Torob/diarman; amox-os is **not** used. superpowers (brainstorming → writing-plans →
executing-plans, TDD for the approval gate, risk classes and diagnosis ranking; systematic-debugging;
verification-before-completion; code review per phase); ponytail always on with `ponytail:` comments
on shortcuts; `/graphify` per phase; UI skills `emil-design-eng`, `apple-design`, `mobile-native`,
`prototype`, `break-ui`, `animate`/`review-animations`, `pick-ui-library`, `ask-sonner`; `dataviz`
for metric charts. Project skills to write in `skills/`: `liara-api`, `agent-tools` (risk classes,
approval contract), `brand`.

## 8. Deliverables

| Artifact | Repo source |
|---|---|
| Brand book | `docs/design/brand/` |
| System design | `docs/SYSTEM-DESIGN.md` |
| Database design (ERD) | `docs/DATA-MODEL.md` |
| Software architecture | `docs/ARCHITECTURE.md` |
| Task book | `docs/TASKS.md` |

## 9. Answers (2026-10-22) — see `decisions.md`

Stack A. LLM = Claude subscription via the Claude Agent SDK (BoxAPI later). Coding fix = Claude Code.
Same team. Demo = deploy the Torob app with this assistant. Name «همکار فنی». Liara account with
2M toman ready. Mockup v0: https://claude.ai/artifact/3ghx7zL5cp2xC9tiRLM9JH (`docs/design/mockup-v0.html`).

## 9a. Original open questions

1. Stack A (recommended), B or C?
2. Reuse BoxAPI + the same `LLMClient` as Torob?
3. Same team (you + the two students)?
4. Demo target: deploy the Torob app with this assistant (recommended) or only the fault-lab app?
5. Coding fix: our patch tool first (recommended) or Claude Code headless from day one?
6. Name: keep «همکار فنی» as the working title?
7. Do you have a Liara account with an API token and some balance for the demo?

## 10. Artifacts (2026-10-22)

| Artifact | Link | Source in repo |
|---|---|---|
| Mockup v0 | https://claude.ai/artifact/3ghx7zL5cp2xC9tiRLM9JH | `docs/design/mockup-v0.html` |
| Brand book (Design System) | https://claude.ai/artifact/4FEE36Y3dPpB5mqrHf8yoT | `docs/design/brand/` |
| System design | https://claude.ai/artifact/Lnj7CkTyNwZvrFniqBfN8W | `docs/SYSTEM-DESIGN.md` |
| Database design | https://claude.ai/artifact/JGdNgnL6jg5TzHH2FKkPqR | `docs/DATA-MODEL.md` |
| Software architecture | https://claude.ai/artifact/9C2AQxmDLT3y8x8Cafu4AU | `docs/ARCHITECTURE.md` |
| Task book | https://claude.ai/artifact/21HCK9MiQLHt2s5qUNMhdm | `docs/TASKS.md` |

HTML pages in `docs/artifacts/` are generated from the md files by `docs/tools-taskbook/md2page.py`
(task book: `gen.py`). Edit the md, regenerate, republish.
