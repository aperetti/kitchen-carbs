#!/usr/bin/env bash
# Development server with sample data in ./data-dev (okf/architecture/environments.md).
#   tools/dev.sh            http://localhost:8090 (localhost counts as secure, so the camera and scale work;
#                           okf/architecture/https.md)
# Reads GEMINI_KEY and FAT_SECRET_CLIENT_ID / FAT_SECRET_CLIENT_SECRET from kitchen-carbs/.env, or the parent folder's .env.
set -euo pipefail
cd "$(dirname "$0")/.."
for f in .env ../.env; do [ -f "$f" ] && { set -a; . "$f"; set +a; break; }; done
[ -n "${GEMINI_KEY:-}" ] || echo "warning: GEMINI_KEY not set; photo styling and label scanning will fail" >&2
[ -x .venv/bin/uvicorn ] || { python3 -m venv .venv && .venv/bin/pip install -q -r app/requirements.txt pytest httpx; }
export KC_ENV=dev KC_DATA="$PWD/data-dev"
cd app
exec ../.venv/bin/uvicorn server.main:app --host 0.0.0.0 --port "${DEV_PORT:-8090}" --reload
