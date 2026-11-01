# Kitchen Carbs

A kitchen-tablet app for looking up carbs by portion, adding up a plate, logging meals, and seeing
glucose after meals from Nightscout. It shows carbs only and never suggests insulin doses.

The design and rules come from the OKF concept map in `okf/` (see `PLAN.md`).

## Environments

| | data | port | start |
|---|---|---|---|
| dev | `data-dev/` (sample data) | 8090 | `tools/dev.sh` |
| QA | `data-qa/`, a fresh copy of production | 8093 on the homelab | `tools/qa.sh` |
| production | `data/` | 8092 on the homelab, HTTPS via Cloudflare | `tools/deploy.sh` |

All three read `GEMINI_KEY`, `FAT_SECRET_CLIENT_ID` and `FAT_SECRET_CLIENT_SECRET` (FatSecret OAuth 2.0; add the server's public IP to the key's allowlist in the FatSecret developer portal) from `.env`, written as `NAME=value`, (in this folder or the parent folder). Keep `.env` out of git and
off the image; Docker passes it in when the container starts. Ports change with `DEV_PORT`, `QA_PORT`, `PROD_PORT`. Dev and production both default to 8090, so on the same machine stop the dev server or set `DEV_PORT`.

### HTTPS
The app serves plain http. In production a Cloudflare Tunnel provides HTTPS in front of port 8092. Browsers only
allow the camera (live barcode scanner) and Bluetooth (kitchen scale) on a secure address: the Cloudflare https name,
or http://localhost in dev. Opened by LAN IP over plain http, those two fall back to photo or typed entry.

### First install on the server
1. Install Docker with the compose plugin, copy this folder over, and put `GEMINI_KEY=...` in `.env`.
2. `tools/deploy.sh --yes` (there is nothing in QA to check yet).
3. On the tablet, open `http://<server IP>:8090` and add it to the home screen.
4. **Manage**: create a parent PIN, connect Nightscout with a `readable` token (not the API secret),
   then scan labels or check the sample foods.

### Releasing a change
1. `tools/qa.sh` copies production's data into `data-qa/` and starts the new code on it (port 8091).
   New migrations run on the copy; production is only read. The QA screen shows a banner.
2. Check QA on the tablet.
3. `tools/deploy.sh` runs the tests in Docker, asks whether QA was checked, copies production to
   `data/backups/pre-deploy-<time>/`, then restarts production. Pending migrations make their own backup too.
4. `tools/qa.sh stop` when done.

### Database migrations
Schema changes live in `app/server/migrations.py` as a numbered list; the database records the last one
applied. To change tables for a feature, **append** a migration; never edit or reorder shipped ones.
Each runs in a transaction after a backup to `data/backups/pre-migration-...db`; if one fails it rolls back
and the app won't start, leaving the data as it was. A database newer than the code is refused.

### Restoring a backup
`docker compose stop kitchen-carbs`, copy the backup over `data/app.db`, deploy the code that matches it.

## Develop
```
tools/dev.sh                                    # http://localhost:8090, reloads on change
cd app && ../.venv/bin/python -m pytest tests   # all tests
```

## Notes
- Meals are grouped by the home computer's local day; past days are read-only.
- The tablet keeps foods, the plate and unsent meals in its browser, so the app keeps working if the
  server goes down while it is open. Reloading needs the server.
- Sample foods and photos are placeholders: values are "Not verified" and photos are "Estimated".

## Production on the homelab
Production runs on `user@server` in `~/t1d/kitchen-carbs`; the keys are in `~/t1d/.env` and the ports in
`~/t1d/kitchen-carbs/.env` (`PROD_PORT=8092`, `QA_PORT=8093`).
To ship a new version from the laptop:

    rsync -a --exclude .venv --exclude data-dev --exclude data --exclude data-qa \
      --exclude __pycache__ --exclude .pytest_cache --exclude .env ./ user@server:t1d/kitchen-carbs/
    ssh user@server 't1d/kitchen-carbs/tools/qa.sh'       # check http://server:8093
    ssh user@server 't1d/kitchen-carbs/tools/deploy.sh'

The schema is frozen at version 1 since the first deploy: new tables or columns are new migrations.

## Google sign-in (Firebase)
Off until a Firebase project is set (okf/architecture/auth.md). To turn it on:
1. Firebase console → your project → Authentication → Sign-in method → enable **Google**.
2. Authentication → Settings → **Authorized domains**: add the Cloudflare Tunnel name the tablet opens
   (e.g. `kitchen.example.com`), and `localhost` for dev.
3. Project settings → Your apps → Web app → copy the config into `~/t1d/.env` on the server:

       FIREBASE_API_KEY=...
       FIREBASE_AUTH_DOMAIN=<project>.firebaseapp.com
       FIREBASE_PROJECT_ID=<project>
       KC_ALLOWED_EMAILS=parent@gmail.com,other.parent@gmail.com

4. Deploy. Every device then signs in once with Google and stays signed in for 30 days (renewed while used).
   The allow list can be edited later in Manage → Settings → Family accounts; the PIN still guards Manage.

## License
Kitchen Carbs is free software under the GNU General Public License, version 3 (see [LICENSE](LICENSE)).
Bundled third-party files keep their own licenses: IBM Plex Sans under the SIL Open Font License 1.1
(`app/web/fonts/OFL.txt`, `app/server/fonts/OFL.txt`), and the barcode reader under MIT and Apache-2.0
(`app/web/vendor/licenses/`).

It is a carb-counting and logging aid, not a medical device, and comes with no warranty (sections 15–16 of the
license). Doses it shows are arithmetic on the settings a parent enters; check them against the care team's plan.
