# Build plan — Mohammad's coding tasks

`TASKS.md` is the students' book (R&D, tests, docs, video; ids `T-xx`). This file is the code: ids
`B-xx`, built by Mohammad with Claude Code. Each task names what to read, the files it creates, how
to know it is done, and what it waits on. A Claude Code session should be able to start any task cold
from this file plus the sections it points to.

## How to run a task with Claude Code

1. `git pull`, then read `CLAUDE.md` and this task's **Read** list (only those sections).
2. Check **Depends**: every listed `B-xx` is ✓ on the board below (or its stub is acceptable, as stated).
3. superpowers: `writing-plans` for the task → `executing-plans`. TDD where the task says **TDD**.
4. Work in the **Files** listed. Anything outside them means the plan is wrong: stop and update this file.
5. Done = every **Done when** line passes and `make check` is green. Tick the board (`✓`), commit
   `B-xx: <what>` in small commits, push.
6. Something here turns out wrong (endpoint, shape, order)? Fix this file and the design doc in the
   same commit. A change to a numbered decision needs Mohammad's yes (`decisions.md`).

Prompt to start a session cold: *"Do B-xx from docs/BUILD.md. Read CLAUDE.md and the task's Read
list first, then plan, then build. Stop and ask if a Depends item is not done."*

## Defaults taken here (say if you disagree)

- **MVP auth = one passphrase** (`POST /api/session`, `DEPLOYAR_PASSPHRASE`), one seeded `user` row.
  Magic-link login from `DATA-MODEL.md` is P4-optional. Single-user tool on Mohammad's Mac (ADR 11).
- **GitHub = fine-grained personal token** stored like the Liara token. GitHub App is P4-optional.
- **Liara endpoints**: the tool table in `ARCHITECTURE.md §9` is a guess. B-08 does not wait for the
  full T-01 report: Mohammad confirms the 8 endpoints it needs from the `@liara/cli` source
  (`npm pack @liara/cli`, read `src/commands`) and the live account, and records them in
  `skills/liara-api/SKILL.md`. T-01 fills in the rest.
- **No CI service** for the MVP: `make check` in the pre-push hook is the gate.
- **Cut line**: tasks marked *cuttable* are dropped first if time runs short. The judged MVP is
  P0 + P1 + P2 + B-22.

## Board

Order inside a phase is the build order. `○` todo · `✱` doing · `✓` done.

| id | title | phase | depends | students feed it | cut? | state |
|---|---|---|---|---|---|---|
| B-00 | Agent SDK spike (local login, in-process MCP, can_use_tool) | P0 | — | — | | ✓ |
| B-01 | Repo scaffold: agent, web, worker, Compose, Makefile, hooks | P0 | — | — | | ✓ |
| B-02 | Core: config, ids, crypto vault, redactor, errors, Persian | P0 | B-01 | — | | ✓ |
| B-03 | Schema v1: migrations 0001–0004 + models | P0 | B-02 | — | | ✓ |
| B-04 | Approval gate (TDD) | P0 | B-03 | T-19 tests it later | | ✓ |
| B-05 | Tool registry, result types, `tool_call` recording | P0 | B-03, B-00 | — | | ✓ |
| B-06 | LLM seam, Claude backend, orchestrator, event bus, runs API + SSE | P0 | B-04, B-05 | — | | ✓ |
| B-07 | Web shell: RTL layout, tokens, chat, checklist, approval card, SSE | P0 | B-06 (fake events ok) | T-16, T-21 | | ✓ |
| B-08 | LiaraClient + connections + read tools | P0 | B-05 | T-01, T-04 | | ✓ |
| B-09 | GitHub client + repo analyzer + `analyze_repo` | P1 | B-05 | T-06, T-13 | | ○ |
| B-10 | Plan proposal (`list_plans`, price, plan card) + migration 0101 | P1 | B-08, B-09 | T-04 | | ○ |
| B-11 | Sensitive deploy tools: create_app, create_database, set_env, deploy_release | P1 | B-04, B-08 | T-01 | | ○ |
| B-12 | Deploy mode: prompt, step template, deployment watcher, live URL | P1 | B-10, B-11, B-07 | T-14, T-11 | | ○ |
| B-13 | Status panel (`/status` + StatusPanel) | P1 | B-08, B-07 | — | | ○ |
| B-14 | Domain: add_domain, check_dns, registrar guide, DNS recheck | P1 | B-12 | T-03, T-15 | | ○ |
| B-15 | Fault-lab app `lab/` deployed on Liara | P2 | B-12 | T-07, T-12 | | ○ |
| B-16 | Incident evidence: http_probe, evidence rows, migration 0201 | P2 | B-08 | T-12 | | ○ |
| B-17 | SRE engine: signals, ranking, criteria (TDD) + `make eval` | P2 | B-16 | T-17, T-18 | | ○ |
| B-18 | Actions + verify: restart, resize, rollback, verify_after_action | P2 | B-17, B-04 | T-19 | | ○ |
| B-19 | Incident mode end to end + limitation cards | P2 | B-18 | T-11, T-16 | | ○ |
| B-20 | Incident timeline page | P2 | B-19 | — | cuttable | ○ |
| B-21 | Torob app (ترب‌گرد) live on Liara via Deployar | P1→P2 | B-12 | T-14, T-26 | | ○ |
| B-22 | Coder: apply_code_fix, merge_and_deploy, DiffCard | P3 | B-19 | T-22 | | ○ |
| B-23 | Scheduled checks + weekly digest | P3 | B-16 | T-23 | cuttable | ○ |
| B-24 | MCP stdio endpoint for the user's Claude Code | P3 | B-05 | T-25 | cuttable | ○ |
| B-25 | Hardening: secrets canary, audit chain, retention | P4 | B-22 | T-20 | | ○ |
| B-26 | Demo freeze: seed, rehearsal script, md doc inputs | P4 | all above | T-26–T-32 | | ○ |

Critical path: B-00 → B-01 → B-02 → B-03 → B-04/B-05 → B-06 → B-08 → B-11 → B-12 → B-21 (first
judged scenario), then B-16 → B-17 → B-18 → B-19 → B-22.

---

## P0 — Foundation

Gate: `make dev` runs everything; a chat message in the web UI makes Claude call one read tool
(`get_balance`) and one sensitive stub tool that waits for an approval tap.

### B-00 · Agent SDK spike · 2 h

Prove the riskiest assumption first: the Claude Agent SDK (Python) drives the local Claude Code login
with an in-process MCP server and a `can_use_tool` callback that can block on an external event.

- **Read**: `decisions.md` #2, `ARCHITECTURE.md §3` (SDK options), Agent SDK docs (`claude-api` skill).
- **Files**: `spikes/b00_sdk.py` (throwaway, kept for reference), `docs/evidence/B-00/notes.md`.
- **Do**: one `ClaudeSDKClient` with `mcp_servers={"deployar": create_sdk_mcp_server(...)}`, two tools
  (`echo` read, `danger` sensitive), `allowed_tools=["mcp__deployar__echo"]` (read tools only; see notes), built-ins disallowed,
  `setting_sources=[]`, `can_use_tool` that awaits an `asyncio.Event` set from stdin.
- **Done when**: (1) runs with no `ANTHROPIC_API_KEY` set, on the logged-in Claude Code;
  (2) `danger` does not run until you type `y`, and gets a deny on `n`; (3) built-in Bash is refused;
  (4) notes record SDK version, streaming message types seen, and latency per turn.
- **If it fails**: stop and tell Mohammad; decision #2 (LLM backend) must be revisited before B-06.

### B-01 · Repo scaffold · 3 h

- **Read**: `ARCHITECTURE.md §5, §10, §11`, `decisions.md` #1.
- **Files**:
  - `agent/pyproject.toml` (uv; deps: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic,
    pydantic-settings, httpx, redis, arq, structlog, cryptography, claude-agent-sdk, uuid-utils;
    dev: pytest, pytest-asyncio, respx, ruff, mypy), `agent/src/deployar/__init__.py`,
    `agent/src/deployar/main.py` (`GET /api/health` → `{"ok":true}`), script `deployar-agent`,
    `agent/tests/unit/test_health.py`.
  - `web/` via `pnpm create next-app` (Next 16, TS, Tailwind v4, App Router, `src/`), vitest.
  - `docker-compose.yml` (exists: postgres + redis; add `web` and `worker` services),
    `Makefile`: `dev` (compose up + `uv run deployar-agent` on host), `check` (ruff, mypy, pytest,
    `pnpm lint`, `pnpm tsc --noEmit`, vitest), `migrate`, `eval`, `push-test`.
  - `.githooks/pre-push` → `make check`; `make setup` sets `git config core.hooksPath .githooks`.
  - `.env.example` (exists; keep in sync).
- **Done when**: `make setup && make dev` serves `localhost:3800` and `localhost:8800/api/health`;
  `make check` is green; the folders of `ARCHITECTURE.md §10` exist where code will land (no empty
  placeholder modules).

### B-02 · Core utilities · 3 h · TDD

- **Read**: `ARCHITECTURE.md §11`, `DATA-MODEL.md` → *Secrets handling*.
- **Files**: `agent/src/deployar/core/{config,ids,crypto,redact,errors,persian,logging}.py`,
  `agent/tests/unit/test_{crypto,redact,persian,ids}.py`.
- **Do**: settings from env (names in `.env.example`); UUIDv7; AES-256-GCM vault with key versions
  and AAD; structlog redaction processor; `DeployarError(code, message_fa, detail)`; ASCII↔Persian digits.
- **Done when**: ciphertext moved to another row's AAD fails; a decrypted token string is scrubbed
  from any log line; key rotation round-trips; Persian digit conversion both ways.

### B-03 · Schema v1 · 4 h

- **Read**: `DATA-MODEL.md` → *Identity & connections*, *Conversation, runs & approvals*,
  *Audit & evals* (`audit_log`, `limitation_event`), *Migration plan*.
- **Files**: `agent/alembic.ini`, `agent/migrations/versions/0001_base.py` … `0004_audit_limits.py`,
  `agent/src/deployar/models/*.py`, `agent/src/deployar/core/db.py`, `agent/tests/unit/test_migrations.py`,
  `agent/src/deployar/seed.py` (`deployar-seed`, `make seed EMAIL=…`).
- **Done when**: `alembic upgrade head && downgrade base && upgrade head` passes on the Compose PG16;
  the `tool_call` gate trigger rejects a sensitive row marked executed without a consumed approval;
  `audit_log` rejects UPDATE/DELETE; a seed command creates the single user.

### B-04 · Approval gate · 5 h · TDD

The 50 security points live here. Write the tests first.

- **Read**: `SYSTEM-DESIGN.md §8–9`, `ARCHITECTURE.md §6.1` + ADR 4–5, `DATA-MODEL.md` → `approval`,
  *Redis keys* (`approval:{id}:decision`).
- **Files**: `agent/src/deployar/runtime/{approvals,gate}.py`, `agent/src/deployar/api/approvals.py`,
  `agent/tests/unit/test_gate.py`, `agent/tests/unit/test_approvals.py`.
  Also touched: `messages_fa.py` (deny texts, human_only guides), `main.py` (router + error mapping),
  `models/enums.py` (enum values for reads), migration `0001` (`approval_status` gains `invalidated`;
  pre-release, so edited in place), `tests/unit/pgtest.py` (shared throwaway DB).
- **Done when** (each a test): sensitive tool never runs without a consumed approval; expired (10 min),
  replayed, tampered-signature and wrong-user decisions are denied; args changed after approval →
  `invalidated`; a lost Redis push still resolves from Postgres on timeout; human_only tools are always
  denied execution and return their guide; read tools pass without a card.

### B-05 · Tool registry · 3 h

- **Read**: `ARCHITECTURE.md §3` (Tool registry), §9, §11 (Tools), ADR 9.
- **Files**: `agent/src/deployar/tools/{registry,results}.py`, `agent/tests/unit/test_registry.py`.
- **Do**: `@deployar_tool(name, group, risk)` registers into the SDK MCP server; writes `tool_call`
  rows; runs the redactor on output; returns `Ok[T] | Limitation | ToolError`; sensitive tools re-check
  the consumed approval inside the tool (second layer); writes `limitation_event` on `Limitation`.
- **Done when**: a fake tool's secret-looking output is redacted before the model sees it; a sensitive
  tool called directly (callback bypassed) refuses; a `Limitation` produces the event row.

### B-06 · Orchestrator, runs API, SSE · 6 h

- **Read**: `SYSTEM-DESIGN.md §4`, `ARCHITECTURE.md §3, §7 (Run), §8` (full contract + SSE events),
  ADR 10, `DATA-MODEL.md` *Redis keys* (`stream:run:*`).
- **Files**: `agent/src/deployar/llm/{client,claude_backend}.py`, `agent/src/deployar/runtime/{orchestrator,events}.py`,
  `agent/src/deployar/runtime/modes/chat.py`, `agent/src/deployar/runtime/prompts/base_fa.md`,
  `agent/src/deployar/api/{session,runs,events}.py`, `agent/tests/contract/test_sse.py`.
  Also: `api/deps.py` (runtime + session dependency); agent moved to **:8800** and web to **:3800**
  because ترب‌گرد's own dev stack uses 8000/3000 on the same Mac.
- **Done when**: `POST /api/runs` with text creates `run` + steps; `GET /api/runs/{id}/events` streams
  `run.started`, `message.delta`, `tool.called`, `approval.requested`, `run.done`; reconnect with
  `Last-Event-ID` replays missed events; every SSE payload validates against its pydantic model;
  `/api/session` passphrase cookie guards all routes.

### B-07 · Web shell · 6 h

- **Read**: `ARCHITECTURE.md §4, §8`, `docs/design/brand/README.md`, `tokens.json`, component READMEs
  under `docs/design/brand/components/` (ApprovalSlider, RunChecklist, RiskChip, LimitationNote,
  MetricCard), `docs/design/mockup-v0.html`. Skills: `emil-design-eng`, `apple-design`, `mobile-native`.
- **Files**: `web/src/app/{layout,page}.tsx`, `web/src/app/p/[projectId]/page.tsx`,
  `web/src/app/settings/connections/page.tsx`, `web/src/components/{chat,checklist,cards}/…`
  (ApprovalCard, LimitationBox, HumanOnlyCard first; other cards land with their task),
  `web/src/lib/{api,sse,persian,money,fa}.ts`, `web/public/fonts/` (Vazirmatn, self-hosted),
  `web/src/app/globals.css` (`@theme` from `tokens.json`).
  Also: `LLM_BACKEND=fake` (agent) plays a scripted turn through the real gate for UI work without
  Claude usage; `next.config.ts` has `compress: false` because gzip buffered the proxied SSE stream.
- **Done when**: RTL at 360 px and desktop; SSE reconnects; tapping approve posts the signed decision
  and the checklist moves on; no request leaves localhost (rule 5, check the network tab); cards render
  from fixtures in vitest.

### B-08 · Liara client, connections, read tools · 5 h

- **Read**: `ARCHITECTURE.md §9` (read rows), `SYSTEM-DESIGN.md §10`, `DATA-MODEL.md` →
  `liara_connection`, T-01 report if ready. See *Defaults* above for verifying endpoints.
- **Files**: `agent/src/deployar/clients/liara.py`, `agent/src/deployar/tools/liara/read.py`,
  `agent/src/deployar/api/connections.py`, `skills/liara-api/SKILL.md`,
  `agent/tests/contract/test_liara_client.py`, `agent/tests/cassettes/liara/*.json` (tokens scrubbed).
- **Do**: httpx client with retry on 429/5xx, 5 req/s bucket, error map (401 → `liara_unauthorized`,
  404 on a capability → `Limitation`); tools `list_plans`, `get_balance`, `get_app_status`, `get_logs`,
  `get_metrics`, `list_releases`, `get_env_keys`; every value `{value, source, observed_at}`.
- **Done when**: pasting a token in settings validates it with `get_balance`, stores it encrypted, shows
  last4; each read tool passes against a cassette; one `-m live` test reads the real balance.
- **Status 2026-10-22**: done against synthetic cassettes from the official OpenAPI spec
  (`skills/liara-api/SKILL.md`); the live balance test waits for Mohammad's token in Settings.
- **Also**: add `make push-test` → `cd agent && uv run pytest -m live` (Mohammad's call, 2026-10-22).
  Register the `live` marker and keep it out of `make check` (`addopts = "-m 'not live'"`). Live tests
  that create or change anything on Liara spend balance: ask Mohammad before adding them.

---

## P1 — First deploy

Gate: «این را آنلاین کن» + a GitHub link ends with a live Liara URL after one plan approval and the
per-step approvals, with build logs streaming in the checklist (`SYSTEM-DESIGN.md §5`).

### B-09 · Repo analyzer · 5 h · TDD

- **Read**: `SYSTEM-DESIGN.md §5`, `ARCHITECTURE.md §9` (`analyze_repo`), `DATA-MODEL.md` →
  `repo_analysis`; fixtures from T-06 in `docs/evidence/T-06/`.
- **Files**: `agent/src/deployar/clients/github.py`, `agent/src/deployar/analysis/detectors/{node,nextjs,python,prisma,docker,env_example}.py`,
  `agent/src/deployar/analysis/analyze.py`, `agent/src/deployar/tools/github/analyze.py`,
  `agent/tests/unit/test_detectors.py`, `web/src/components/cards/RepoAnalysisCard.tsx`.
- **Done when**: on the T-06 fixtures, platform and DB detection match the labels (T-13 runs the
  scoring); each finding lists the evidence file; private repo without access → reconnect card.

### B-10 · Plan proposal · 3 h

- **Read**: `DATA-MODEL.md` → `plan_proposal`, `project`, *Migration plan* (0101); T-04 price table.
- **Files**: `agent/migrations/versions/0101_deploy.py`, `agent/src/deployar/runtime/plan.py`,
  `web/src/components/cards/PlanCard.tsx`.
- **Done when**: analysis → plan card with Liara plan, DB, monthly toman price, source and time;
  prices older than 1 h re-fetched before approval; balance shown next to the price.

### B-11 · Sensitive deploy tools · 5 h

- **Read**: `ARCHITECTURE.md §9` (sensitive rows, `value_refs` note), `DATA-MODEL.md` → `deployment`,
  *Secrets handling* (env values).
- **Files**: `agent/src/deployar/tools/liara/deploy.py`, `agent/src/deployar/api/projects.py`
  (`/env-values`), `agent/tests/contract/test_deploy_tools.py`, `agent/tests/live/test_smoke.py`.
- **Done when**: each tool only runs through B-04 approval; `DATABASE_URL` goes from
  `create_database` to `set_env` as ciphertext and never appears in a model transcript (canary test);
  live smoke: create tiny app → env → deploy hello-world → logs → delete (run by hand, Mohammad present).

### B-12 · Deploy mode · 6 h

- **Read**: `SYSTEM-DESIGN.md §4–5`, `ARCHITECTURE.md §7` (Deployment), T-11 limitation catalogue.
- **Files**: `agent/src/deployar/runtime/modes/deploy.py`, `agent/src/deployar/runtime/prompts/deploy_fa.md`,
  `agent/src/deployar/worker/{settings.py,jobs/watch_deployment.py}`, `web/src/components/cards/LiveUrlCard.tsx`.
- **Done when**: the P1 gate passes on the fault-lab hello-world or any small Next.js repo; a failed
  build shows the redacted log tail and a Persian reason; a missing env var stops the run with a
  question, not a crash.

### B-13 · Status panel · 2 h

- **Files**: `agent/src/deployar/api/projects.py` (`/status`), `web/src/components/status/StatusPanel.tsx`.
- **Done when**: app state, plan, RAM/CPU sparkline, last release, balance, each with source + time;
  a value without source is not rendered.

### B-14 · Domain · 4 h

- **Read**: `SYSTEM-DESIGN.md §5` (domain), T-03 guide.
- **Files**: `agent/src/deployar/tools/liara/domain.py`, `agent/src/deployar/tools/probe/dns.py`,
  `agent/src/deployar/worker/jobs/dns_recheck.py`, `web/src/components/cards/DomainGuide.tsx`.
- **Done when**: add_domain (approved) → 3-step registrar guide with screenshots from T-03 → "check now"
  shows expected vs observed records; recheck job flips the card to green when DNS propagates.

### B-21 · Torob app live via Deployar · 3 h + fixes

- **Needs**: the ترب‌گرد repo URL (not in this repo yet; Mohammad adds it to `decisions.md`).
- **Done when**: the app is live on Liara, deployed only through Deployar's UI, with the run recorded;
  everything Deployar could not do is a LimitationNote, not a manual console step. Feeds T-14 / T-26.

---

## P2 — SRE loop

Gate: OOM leak and slow `/products` on the fault lab are found, fixed with restart/resize, and
verified with before/after numbers (`SYSTEM-DESIGN.md §6`).

### B-15 · Fault lab · 3 h

- **Read**: T-07 spec (`docs/evidence/T-07/`), `SYSTEM-DESIGN.md §14`.
- **Files**: `lab/` (small Next.js + Prisma app: `/leak`, `/boom`, slow `/products`, switches via env).
- **Done when**: deployed through Deployar; each fault reproduces on Liara with the symptoms T-12 measured.

### B-16 · Evidence · 4 h

- **Read**: `DATA-MODEL.md` → *Incidents & SRE* (`incident`, `evidence`), migration 0201.
- **Files**: `agent/migrations/versions/0201_incidents.py`, `agent/src/deployar/tools/probe/http.py`,
  `agent/src/deployar/sre/evidence.py`.
- **Done when**: an incident run stores logs, metrics, status, releases and probe p50/p95 as evidence
  rows with source and window.

### B-17 · SRE engine · 6 h · TDD

- **Read**: `SYSTEM-DESIGN.md §7`, `ARCHITECTURE.md §12` (SRE evals), ADR 8; T-17 cases in `evals/incidents/`.
- **Files**: `agent/src/deployar/sre/{signals,ranking,criteria}.py`, `agent/migrations/versions/0202_evals.py`,
  `agent/src/deployar/evals/run.py`, `make eval`.
- **Done when**: `make eval` prints top-1/top-2 and writes `eval_run` rows; gate top-1 ≥ 80 %,
  top-2 = 100 %, zero sensitive actions without approval.

### B-18 · Actions and verify · 5 h

- **Files**: `agent/src/deployar/tools/liara/actions.py` (restart, resize, rollback),
  `agent/src/deployar/sre/verify.py`, `agent/src/deployar/worker/jobs/verify_after_action.py`,
  `web/src/components/cards/VerificationCard.tsx`.
- **Done when**: after an approved action the worker re-measures with the same probe and window and
  writes a verdict (`resolved|improved|unchanged|worse`); the card shows before/after with sources.

### B-19 · Incident mode end to end · 4 h

- **Files**: `agent/src/deployar/runtime/modes/incident.py`, `prompts/incident_fa.md`,
  `web/src/components/cards/{EvidenceCard,HypothesesCard}.tsx`.
- **Done when**: «سایتم کند شده» on the fault lab passes the P2 gate; DB slow-query request shows
  `db_query_log_unavailable` as a LimitationBox.

### B-20 · Incident timeline · 2 h · cuttable

- **Files**: `web/src/app/p/[projectId]/incidents/[id]/page.tsx`, `GET /api/incidents/{id}`.

---

## P3 — Coding fix + extras

### B-22 · Coder · 8 h

- **Read**: `ARCHITECTURE.md §6.2`, ADR 6, `DATA-MODEL.md` → `code_fix`, migration 0301.
- **Files**: `agent/src/deployar/coder/{worktree,brief,runner,guard}.py`, `agent/src/deployar/tools/github/fix.py`,
  `agent/migrations/versions/0301_code_fix.py`, `web/src/components/cards/DiffCard.tsx`.
- **Done when**: slow `/products` → brief → subagent edits only in the worktree, Bash allow-list only →
  tests pass → our code pushes and opens a PR → DiffCard → approved `merge_and_deploy` bound to head sha
  → verified. Head moved after approval → invalidated (test).

### B-23 · Scheduled checks · 4 h · cuttable

- **Files**: migration `0302_checks.py`, `agent/src/deployar/worker/jobs/scheduled_checks.py`,
  `GET/PATCH /api/projects/{id}/checks`, a settings toggle in the project page.

### B-24 · MCP stdio endpoint · 2 h · cuttable

- **Files**: `agent/src/deployar/mcp_stdio.py` serving the same registry; approvals still go through the web UI.
- **Done when**: T-25 calls `get_app_status` from Claude Code; a sensitive tool waits for the web tap.

---

## P4 — Ship

### B-25 · Hardening · 4 h

- **Files**: `agent/tests/unit/test_secret_canary.py`, audit hash chain in `core/audit.py`, migration `0401_retention.py`.
- **Done when**: a canary token never appears in logs, SSE frames, `tool_call` rows or model input;
  T-20 checklist has no open "fail".

### B-26 · Demo freeze · 3 h

- **Done when**: tag `demo-v1`; `make dev` from a clean clone works by following `README.md`; the
  `SYSTEM-DESIGN.md §14` script runs end to end; md-doc inputs (endpoints used, limitation counts from
  `limitation_event`, eval numbers) handed to T-27.
