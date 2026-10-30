# Kitchen Carbs — plan

A kitchen-tablet app for looking up carbs by portion, adding up a plate, and logging meals
for a child with type 1 diabetes. It shows carbs only and never calculates insulin doses.

**The design and features are defined in the OKF concept map in [`okf/`](okf/index.md).**
OKF is used only for planning; the app does not read it. Change the map first, then the code.
Run `python3 tools/okf_check.py` to validate it (`--mermaid` prints a diagram).

## Decisions
| Topic | Decision | Concept |
|---|---|---|
| Device | Kitchen tablet, LAN, offline-tolerant | architecture/offline.md |
| Server | One Docker container (Python FastAPI) on the home computer | architecture/docker-server.md |
| Storage | SQLite + photo files on a Docker volume, nightly backup | architecture/storage.md |
| Photos | Your photos are the baseline; Gemini restyles them; estimated stand-ins are labelled | features/photo-pipeline.md |
| Scope v1 | Browse, view food, plate total, meal log, CSV export, parent food editor | features/ |
| Carbs | Grams you weighed × carbs/100 g from the source; whole grams | domain/carb-value.md |
| Look | Quartz-matched neutrals, one ink-blue accent, IBM Plex Sans, no AI-look patterns | design/index.md |
| Log | Eaten (all/most/half/little/none) + comments; edits same day only | features/annotate-meal.md |

Review page (concept map, look, journey, all commentable): `python3 tools/build_review.py`, then republish
`review/index.html` → https://claude.ai/artifact/FD6RPftybWoBf4xHxHtzZg

## How the map is grounded
- **Feature** → `uses` domain concepts, `constrained_by` rules
- **component** (ODSF) → `implements` features, `uses_tokens` foundations
- **Architecture** → `serves` features, `stores` domain concepts
- No orphans, no broken links (checked by tools/okf_check.py)

## Build status (27 Oct 2026)
All five stages are built in `app/` (see README.md to run it):
1. Docker + SQLite schema from domain/ — done
2. Foods list + food view with 4 sample foods and placeholder photos — done
3. Plate + log (eaten, comments, same-day edits) + CSV export — done
4. Parent PIN, food editor, photo pipeline (Gemini restyle + estimated stand-ins) — done
5. Offline: tablet-side food cache + meal queue — done (no service worker; see architecture/offline.md)
Plus Nightscout: read-only sync, meal glucose curve, day/7/14-day statistics — done.
Since then: tags, favorite plates, nutrition-label scanning, migrations, dev/QA/production environments.
Not yet tried for real: the Docker build and the qa/deploy scripts (Docker isn't installed on the dev machine), and Gemini photo styling.
