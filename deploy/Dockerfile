# Production image (decision 14): Next.js and the FastAPI agent in one container, so one Liara app runs
# Deployar and the agent is never exposed; /api goes to it over loopback. Without DATABASE_URL/REDIS_URL the
# container also runs its own Postgres and Redis on loopback (one Liara app, data resets on restart).
# Local dev stays on docker-compose.yml.
FROM node:24-bookworm-slim AS web
WORKDIR /web
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0 NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
# rewrites are fixed at build time: the agent sits next to Next.js in the same container
RUN AGENT_URL=http://127.0.0.1:8800 pnpm build

FROM python:3.13-slim-bookworm
COPY --from=web /usr/local/bin/node /usr/local/bin/node
RUN apt-get update && apt-get install -y --no-install-recommends postgresql redis-server \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.12.23
WORKDIR /app/agent
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_COMPILE_BYTECODE=1 LLM_BACKEND=boxapi
COPY agent/pyproject.toml agent/uv.lock agent/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY agent/ ./
RUN uv sync --frozen --no-dev
COPY --from=web /web/.next/standalone /app/web
COPY --from=web /web/.next/static /app/web/.next/static
COPY --from=web /web/public /app/web/public
COPY deploy/start.sh /app/start.sh
EXPOSE 3000
CMD ["sh", "/app/start.sh"]
