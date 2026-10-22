# Liara console check — 2026-10-22

Read in the built-in browser on Mohammad's logged-in account. Nothing was created or changed; the
create-app wizard was opened up to step 4 (plans) and left. The API token page was opened but its
token section was not read (hard rule 2).

## Account

- Team credit: **2,000,000 toman** (shown as «اعتبار تیم», so this is a team account).
- Apps: none yet.
- Two-factor login: **off**. Turn it on before the demo; this account holds a token with full access.
- API token page: `console.liara.ir/API` (token has an expiry setting).

## Create-app wizard (what `create_app` must cover)

1. Platform: NodeJS, NextJS, Laravel, PHP, Python, Django, Flask, .NET, React, Angular, Vue, Static, Go, Docker.
2. App id → `<id>.liara.run`. **The liara.run address is active for 7 days from the first deploy**
   (meant for testing). Demo timing and B-14 (custom domain) depend on this.
3. **Private network**: app and database must be in the same private network to talk. `create_app`
   and `create_database` need a network step (or pick an existing one).
4. Plan (tiers پایه / نقره‌ای / طلایی; numbers below are the default tab, پایه).
5. (not opened: final step creates the app)

## App plans, tier پایه (VAT added on top; location Iran; traffic unlimited, fair use)

| Plan | Monthly (toman) | Hourly (toman) | RAM | vCPU | Disk |
|---|---|---|---|---|---|
| زمین | 950,000 | 1,318 | 512 MB | 0.5 | 5 GB |
| مریخ | 1,650,000 | 2,290 | 1 GB | 1 | 10 GB |
| مشتری | 2,950,000 | 4,096 | 2 GB | 1 | 20 GB |
| زحل | 5,300,000 | 7,360 | 4 GB | 2 | 40 GB |
| اورانوس | 9,200,000 | 12,776 | 8 GB | 4 | 80 GB |
| نپتون | 16,000,000 | 22,222 | 16 GB | 8 | 160 GB |
| پلوتون | 28,000,000 | 38,888 | 32 GB | 16 | 320 GB |

Billing is hourly, so a demo run costs hours, not a month: one زمین app for 48 h ≈ 63,000 toman
before VAT. This is the dated static table B-10 may fall back to if the API has no prices.

## Other

- Liara sells an AI API (news: Claude Sonnet 4.5, GPT-5, Qwen, JEV, embeddings), billed from the same
  credit. Possible later replacement for BoxAPI behind the `LLMClient` seam (decision #2); not decided.
- Liara Postgres has pgvector (news item). PostGIS support not checked.

## Follow-up: hosting options for ترب‌گرد (same day)

- **Managed PostgreSQL** versions 13.23–18.4; the create wizard has toggles for **PostGIS** and
  **Pgvector** (docs: `docs.liara.ir/dbaas/postgresql/extensions/`, 52 more extensions). DB plans
  have the same names and prices as app plans (زمین 1,318/h … ).
- **Docker platform** is fully supported (Dockerfile or docker-compose, `liara.json`). ترب‌گرد's API
  needs GDAL system libraries, so Docker is the right platform for it; the web is a plain Next.js app.
- **VPS (IaaS)** exists with its own API (`iaas-api.liara.ir`); smallest documented plan is مشتری
  (1 core, 2 GB, 20 GB). No prices in the docs, and capacity was announced as limited. Not used:
  the challenge scores Liara PaaS integration (apps, releases, logs, metrics), which a VPS bypasses.
- Rough demo cost for ترب‌گرد: API مریخ 2,290 + web زمین 1,318 + Postgres مریخ 2,290 ≈ 5,900
  toman/h before VAT ≈ 140,000/day; the 2,000,000 credit covers about two weeks if left on 24/7.
