# Decisions

Numbered. Do not reverse one without asking Mohammad.

1. **2026-10-22 — Stack = Option A.** `web/` Next.js 16 + TS + Tailwind v4 (pnpm); `agent/` Python 3.13 FastAPI (uv) for the agent loop, Liara client, tools, approval gate, SSE; PostgreSQL 16; Redis 7; Docker Compose; Makefile `dev / check / push-test`. No Django (no data-entry workload).
2. **2026-10-22 — LLM = Mohammad's Claude subscription first.** The agent runs on the Claude Agent SDK (Python), which drives the locally logged-in Claude Code. BoxAPI credit is under $3, so it is not used at the start. The `LLMClient` seam stays so BoxAPI (`https://ai.boxapi.ir/ai/v1`, OpenAI-compatible) can replace it later by env var. Consequence: the agent process runs on Mohammad's Mac (or a machine logged in to his Claude account), not on Liara.
3. **2026-10-22 — Coding-agent fix = Claude Code** through the same Agent SDK (a sub-agent with Read/Edit/Bash in a clone of the user's repo, opens a branch/PR). No separate patch tool, no paid API.
4. **2026-10-22 — Team.** Mohammad builds the software; two university students do R&D, testing, docs and checks. The task book is written for them.
5. **2026-10-22 — Demo = deploy the Torob app (راهبر خرید) to Liara with this assistant**, then break it on purpose and let the SRE loop find, fix and verify. One scenario feeds both challenge videos.
6. **2026-10-22 — Working name «همکار فنی».**
7. **2026-10-22 — Liara account ready** with an API token and ~2,000,000 toman balance for the demo.
8. **2026-10-22 — No amox-os.** Conventions come from `diarman`, `future-mission-2d` and `In-Store-Agent (Torob)`.
