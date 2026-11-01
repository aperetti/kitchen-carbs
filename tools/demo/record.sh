#!/usr/bin/env bash
# Record the demo reels and the sizzle reel from made-up data, and (with --publish) upload them to the
# 'demo-media' GitHub release that the README shows. The videos are never committed.
#   tools/demo/record.sh             record and build into demo-out/final
#   tools/demo/record.sh --publish   ...then replace the files on the release
# Needs: dev data in data-dev/ (its foods and photos), Node (Playwright installs itself here), ffmpeg, pdftoppm, and gh for --publish.
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT="$PWD/demo-out"; DATA="$OUT/data"; PY="$PWD/.venv/bin/python"
rm -rf "$OUT"; mkdir -p "$OUT"
"$PY" tools/demo/prepare.py data-dev "$DATA"

python3 tools/demo/fake_ns.py & NS=$!
(cd app && exec env -i PATH="$PATH" HOME="$HOME" KC_ENV=demo KC_DATA="$DATA" ../.venv/bin/uvicorn server.main:app \
  --host 127.0.0.1 --port 8095 >"$OUT/server.log" 2>&1) & SRV=$!
trap 'kill $NS $SRV 2>/dev/null || true' EXIT
for i in $(seq 1 60); do curl -fs http://127.0.0.1:8095/api/session >/dev/null && break; sleep 0.5; done

"$PY" tools/demo/seed.py "$DATA/app.db"
(cd app && KC_DATA="$DATA" "$PY" -c "from server import nightscout; nightscout.sync_once()")   # CGM now, not in 5 minutes
[ -d tools/demo/node_modules/playwright ] || (cd tools/demo && npm install --no-audit --no-fund --silent && npx playwright install chromium)
node tools/demo/reels.js "$OUT"
curl -fs -o "$OUT/demo.pdf" "http://127.0.0.1:8095/api/export.pdf?start=$(date -d '-2 days' +%F)&end=$(date +%F)"
(cd tools/demo && "$PY" build.py "$OUT")

if [ "${1:-}" = "--publish" ]; then
  gh release view demo-media >/dev/null 2>&1 || gh release create demo-media --prerelease --title "Demo media" \
    --notes "Videos and GIFs for the README, made with tools/demo/record.sh from made-up data. Not a release of the app."
  gh release upload demo-media "$OUT"/final/*.gif "$OUT"/final/*.mp4 --clobber
  echo "Published to https://github.com/aperetti/kitchen-carbs/releases/tag/demo-media"
fi
