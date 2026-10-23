#!/bin/sh
# Container entry: own Postgres/Redis when none is given, migrate, seed the user, the agent on loopback,
# Next.js in front on $PORT.
set -e
if [ -z "$DATABASE_URL" ]; then
  # shortcut: data lives in the container and resets on restart; set DATABASE_URL to a Liara database to keep it.
  PG=$(ls -d /usr/lib/postgresql/*/bin | tail -1)
  mkdir -p /var/lib/deployar-pg && chown postgres /var/lib/deployar-pg
  # UTF8 explicitly: the image has no locale, so initdb would pick SQL_ASCII and every Persian insert fails
  su postgres -s /bin/sh -c "$PG/initdb -D /var/lib/deployar-pg -U deployar --auth=trust -E UTF8 --locale=C.UTF-8 >/dev/null"
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
.venv/bin/deployar-seed --email "${DEPLOYAR_EMAIL:-admin@deployar.local}"  # login needs the one user
# shortcut: no supervisor, so if the agent dies the web keeps serving and /api returns 502; add one if it bites.
.venv/bin/uvicorn deployar.main:app --host 127.0.0.1 --port 8800 &
# Next.js answers Liara's health check, so start it only once /api works (the agent takes ~10 s on 0.5 CPU)
for _ in $(seq 60); do
  .venv/bin/python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8800/api/health', timeout=1)" \
    2>/dev/null && break
  sleep 1
done
cd /app/web
PORT="${PORT:-3000}" HOSTNAME=0.0.0.0 exec node server.js
