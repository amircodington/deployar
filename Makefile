# Hamkar tasks. `make check` runs before every push (.githooks/pre-push).
.PHONY: setup dev down check agent-check web-check migrate eval

AGENT = cd agent &&
WEB = cd web &&

setup:  ## once per clone
	test -f .env || cp .env.example .env
	git config core.hooksPath .githooks
	$(AGENT) uv sync
	$(WEB) pnpm install

dev:  ## web :3000, worker, postgres, redis in Docker; agent :8000 on the host (Ctrl+C stops the agent)
	docker compose up -d --build
	@echo "web http://localhost:3000 · agent http://localhost:8000/api/health · logs: docker compose logs -f"
	$(AGENT) uv run hamkar-agent

down:
	docker compose down

check: agent-check web-check
	@echo "✓ check passed"

agent-check:
	$(AGENT) uv run ruff check .
	$(AGENT) uv run ruff format --check .
	$(AGENT) uv run mypy
	$(AGENT) uv run pytest -q

web-check:
	$(WEB) pnpm lint
	$(WEB) pnpm typecheck
	$(WEB) pnpm test

migrate:  ## alembic lands in B-03
	$(AGENT) uv run alembic upgrade head

eval:  ## SRE eval set, lands in B-17
	$(AGENT) uv run python -m hamkar.evals.run
