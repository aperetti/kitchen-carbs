#!/usr/bin/env bash
# QA: run the current code on a fresh copy of production's data (okf/architecture/environments.md).
#   tools/qa.sh          copy data/ -> data-qa/, rebuild and start QA on port ${QA_PORT:-8091}
#   tools/qa.sh stop     stop QA
# Production is only read, never changed. Migrations in the new code run on the copy.
set -euo pipefail
cd "$(dirname "$0")/.."
# Port settings (PROD_PORT, QA_PORT) live in this folder's .env, as docker compose reads them.
[ -f .env ] && { set -a; . ./.env; set +a; }
if [ "${1:-}" = "stop" ]; then docker compose --profile qa stop kitchen-carbs-qa; exit; fi
docker compose --profile qa stop kitchen-carbs-qa 2>/dev/null || true
python3 tools/snapshot.py data data-qa
docker compose --profile qa up -d --build kitchen-carbs-qa
port="${QA_PORT:-8091}"
for i in $(seq 1 30); do
  if curl -fs "http://localhost:$port/api/auth/config" >/dev/null; then   # open without signing in
    echo "QA is up: http://$(hostname -I | awk '{print $1}'):$port  (schema $(docker compose exec -T kitchen-carbs-qa python -c 'import sqlite3; print(sqlite3.connect("/data/app.db").execute("PRAGMA user_version").fetchone()[0])'), sign-in $(curl -fs http://localhost:$port/api/auth/config | python3 -c 'import json,sys; print("on" if json.load(sys.stdin)["enabled"] else "off")'))"
    docker compose logs --no-log-prefix kitchen-carbs-qa | grep -E "migrat|backup" || true
    exit 0
  fi
  sleep 2
done
echo "QA did not start. Logs:" >&2; docker compose logs --tail 50 kitchen-carbs-qa >&2; exit 1
