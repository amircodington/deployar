# دیپلویار (Deployar)

Persian DevOps/SRE assistant for Liara. Starcoach hackathon, Liara challenge.

- What and why: `docs/SYSTEM-DESIGN.md` · how: `docs/ARCHITECTURE.md` · tables: `docs/DATA-MODEL.md`
- Code tasks: `docs/BUILD.md` · team tasks: `docs/TASKS.md` · decisions: `docs/decisions.md`

## Run

Needs Docker, uv, pnpm and a logged-in Claude Code (the agent runs on the host and uses that login).

```bash
make setup   # once: .env, git hooks, deps
make dev     # web :3000, worker, postgres, redis in Docker; agent :8000 on the host
make check   # ruff, mypy, pytest, eslint, tsc, vitest (also the pre-push hook)
```

The first `make dev` installs the web container's node_modules into a volume; on a slow link that
takes several minutes.
