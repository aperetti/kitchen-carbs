#!/usr/bin/env bash
# Deploy the current code to production (okf/rules/backup-before-change.md).
#   1. run the tests inside Docker   2. confirm QA was checked   3. back up production
#   4. rebuild and restart production (pending migrations back up again and run on start)
set -euo pipefail
cd "$(dirname "$0")/.."
# Port settings (PROD_PORT, QA_PORT) live in this folder's .env, as docker compose reads them.
[ -f .env ] && { set -a; . ./.env; set +a; }
echo "1/4 tests"
docker build -q --network host --target test app >/dev/null && echo "    tests passed"
if [ "${1:-}" != "--yes" ]; then
  read -r -p "2/4 Did you check this version in QA (tools/qa.sh)? [y/N] " ok
  [ "$ok" = "y" ] || { echo "Stopped. Run tools/qa.sh first."; exit 1; }
fi
echo "3/4 back up production"
if [ -f data/app.db ]; then
  ts=$(date +%Y%m%d-%H%M%S)
  python3 tools/snapshot.py data "data/backups/pre-deploy-$ts" >/dev/null && echo "    data/backups/pre-deploy-$ts"
else
  echo "    no production database yet (first deploy)"
fi
echo "4/4 deploy"
docker compose up -d --build --remove-orphans kitchen-carbs   # HTTPS comes from the Cloudflare Tunnel (okf/architecture/https.md)
port="${PROD_PORT:-8090}"
for i in $(seq 1 30); do
  if curl -fs "http://localhost:$port/api/auth/config" >/dev/null; then
    echo "Production is up: http://$(hostname -I | awk '{print $1}'):$port"
    docker compose logs --no-log-prefix kitchen-carbs | grep -E "migrat|backup" | tail -5 || true
    exit 0
  fi
  sleep 2
done
echo "Production did not come up. Logs:" >&2; docker compose logs --tail 50 kitchen-carbs >&2
echo "To roll back: docker compose stop kitchen-carbs; cp data/backups/pre-deploy-$ts/app.db data/app.db; deploy the previous code." >&2
exit 1
