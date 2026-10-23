#!/bin/sh
# Container entry: own Postgres/Redis when none is given, migrate, seed the user, the agent on loopback,
# Next.js in front on $PORT.
set -e
if [ -z "$DATABASE_URL" ]; then
  # shortcut: data lives in the container and resets on restart; set DATABASE_URL to a Liara database to keep it.
  PG=$(ls -d /usr/lib/postgresql/*/bin | tail -1)
  mkdir -p /var/lib/deployar-pg && chown postgres /var/lib/deployar-pg
  su postgres -s /bin/sh -c "$PG/initdb -D /var/lib/deployar-pg -U deployar --auth=trust >/dev/null"
  su postgres -s /bin/sh -c "$PG/pg_ctl -D /var/lib/deployar-pg -l /tmp/pg.log -w start \
    -o '-c listen_addresses=127.0.0.1 -c shared_buffers=32MB -c max_connections=30'"
  su postgres -s /bin/sh -c "$PG/createdb -h 127.0.0.1 -U deployar deployar"
  export DATABASE_URL=postgresql+asyncpg://deployar@127.0.0.1:5432/deployar
fi
if [ -z "$REDIS_URL" ]; then
  redis-server --bind 127.0.0.1 --save "" --appendonly no --maxmemory 32mb --daemonize yes >/dev/null
  export REDIS_URL=redis://127.0.0.1:6379/0
fi
cd /app/agent
.venv/bin/alembic upgrade head
if [ -n "$DEPLOYAR_EMAIL" ]; then .venv/bin/deployar-seed --email "$DEPLOYAR_EMAIL"; fi
# shortcut: no supervisor, so if the agent dies the web keeps serving and /api returns 502; add one if it bites.
.venv/bin/uvicorn deployar.main:app --host 127.0.0.1 --port 8800 &
cd /app/web
PORT="${PORT:-3000}" HOSTNAME=0.0.0.0 exec node server.js
