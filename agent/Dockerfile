# Worker image (arq). The agent itself runs on the host for the Claude login (ADR 11).
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src src
RUN uv sync --frozen --no-dev
CMD ["uv", "run", "--no-sync", "arq", "hamkar.worker.settings.WorkerSettings"]
