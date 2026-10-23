#!/bin/sh
# Container entry: migrate, seed the single user, the agent on loopback, Next.js in front on $PORT.
set -e
cd /app/agent
.venv/bin/alembic upgrade head
if [ -n "$DEPLOYAR_EMAIL" ]; then .venv/bin/deployar-seed --email "$DEPLOYAR_EMAIL"; fi
# shortcut: no supervisor, so if the agent dies the web keeps serving and /api returns 502; add one if it bites.
.venv/bin/uvicorn deployar.main:app --host 127.0.0.1 --port 8800 &
cd /app/web
PORT="${PORT:-3000}" HOSTNAME=0.0.0.0 exec node server.js
