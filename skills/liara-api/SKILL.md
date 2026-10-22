---
name: liara-api
description: Verified Liara API endpoints Deployar uses (PaaS, DBaaS, billing), with the fields that must never leave the client.
---

# Liara API (verified 2026-10-22)

Source of truth: Liara's OpenAPI pages at `https://developers.liara.ir` (index: `/llms.txt`, each page
has the YAML spec) and `docs.liara.ir/references/api/`. Supersedes the guessed table in
`ARCHITECTURE.md §9`; T-01 confirms shapes against the live account and records cassettes.

- Base URL: **`https://api.liara.ir`** (not `api.iran.liara.ir`). Header `Authorization: Bearer <token>`.
- Team accounts: add query param **`teamID=<id>`** to every call (team id is shown in the console's API menu).
- Tokens expire (chosen at creation in `console.liara.ir/API`).

| Use | Method + path | Notes |
|---|---|---|
| Credit (balance) | `GET /v1/billing` | credit in toman, account type, min-credit alert |
| Account, plans, DB versions | `GET /v1/me` | also returns **Object Storage access/secret keys and national code**: read only `user.email`, `plans`, `databaseVersions` |
| All apps | `GET /v1/projects` | `projects[]{project_id, type, status, scale, planID, isDeployed}` |
| One app | `GET /v1/projects/{name}` | `project{type, status, scale, planID, hourlyPrice, isDeployed, envs[]}` — **envs include values**: keep keys only |
| Create app | `POST /v1/projects` | `{name, planID, platform, network, readOnlyRootFilesystem}`; `network` = private network id |
| Restart | `POST /v1/projects/{name}/actions/restart` | |
| Change plan | `POST /v1/projects/{name}/resize` | `{planID}` |
| Logs | `GET /v1/projects/{name}/logs?since=<ts>` | `[{type, datetime, message}]` |
| Events | `GET /v1/projects/{name}/events?start&end&search` | |
| Releases | `GET /v1/projects/{name}/releases?page=1&count=N` | `{currentRelease, releases[]{_id, state, createdAt, finishedAt, gitInfo, port}}` |
| Upload source | `POST /v2/projects/{name}/sources` | multipart `file` (tar.gz) → `{sourceID}` |
| Create release | `POST /v2/projects/{name}/releases` | `{sourceID, port, type}` → `{releaseID}` |
| Set env | `POST /v1/projects/update-envs` | `{project, variables[{key, value}]}`; restarts the app |
| Metrics now | `GET /v1/projects/{name}/metrics/summary` | `cpuUsage[], memoryUsage[], disksUsage[]` |
| Metrics series | `GET /v1/projects/{name}/metrics/{cpu,memory}?since=<ts>` | `{end, result[{applet, values[[ts, v]]}]}` |
| Create DB | `POST /v1/databases` | `{hostname, type, planID, version, publicNetwork, options}` → `{databaseID}` |
| One DB | `GET /v1/databases/{id}` | includes **`root_password`**, host, port, username: build the URL server-side, encrypt, never return it |
| All DBs | `GET /v1/databases` | |
| Add domain | `POST /v1/domains` | `{name, project, type}` |
| Check domain | `GET /v1/domains/{id}/check` | `status`, `CNameRecord`, `certificatesStatus` |

Not in the public spec (found in the console only): private networks list/create, plan prices with
toman amounts (console shows hourly/monthly; `/v1/me` `plans` shape to confirm with the live token).

## Confirmed on the live account (2026-10-22)

- `GET /v1/billing` → `{"user": {balance, accountType, minCreditAmount, isManualMinCredit}}`, and with
  `teamID` also `"team": {…same…}`. `balance` is toman. A team token spends **team** credit: read `team`.
- Console also calls `GET /v2/teams`, `GET /v1/networks?teamID=` (private networks for create_app),
  `GET /v1/me/two-fa`, `GET /v1/service-count`.
- `GET /v1/me` → `plans.projects` / `plans.databases`: `{plan_id: {available, price, RAM.amount (GB),
  CPU.amount, volume (GB)}}`. **`price` is toman per hour**; monthly in the console = price × 720,
  rounded to 1,000. Available first-gen ids: `ir-small` (0.5 GB, 1,319/h = زمین), `ir-medium` (1 GB,
  2,292/h = مریخ), `standard-base` (2 GB), `standard-plus` (4 GB; DB: `standard-pro`), `pro`, `pro-plus`,
  `pro-max`. `-g2` ids are half price but need a `projectBundlePlans` bundle; not used yet.
- `databaseVersions.postgres[]` = `{value, postgisValue, pgvectorValue}` (16.14 → PostGIS 3.6, pgvector 0.8.1).
