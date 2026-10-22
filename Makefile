# Deployar tasks. `make check` runs before every push (.githooks/pre-push).
.PHONY: setup dev down check agent-check web-check migrate seed eval push-test

AGENT = cd agent &&
WEB = cd web &&

setup:  ## once per clone
	test -f .env || cp .env.example .env
	git config core.hooksPath .githooks
	$(AGENT) uv sync
	$(WEB) pnpm install

dev:  ## web :3800, worker, postgres, redis in Docker; agent :8800 on the host (Ctrl+C stops the agent)
	docker compose up -d --build
	@echo "web http://localhost:3800 · agent http://localhost:8800/api/health · logs: docker compose logs -f"
	$(AGENT) uv run deployar-agent

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

migrate:
	$(AGENT) uv run alembic upgrade head

seed:  ## make seed EMAIL=you@example.com — the single user (idempotent)
	$(AGENT) uv run deployar-seed --email $(EMAIL)

eval:  ## SRE eval set, lands in B-17
	$(AGENT) uv run python -m deployar.evals.run

push-test:  ## live, read-only checks against the real Liara account (needs a token in Settings)
	$(AGENT) uv run pytest -m live -s -q tests/live
