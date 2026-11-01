---
type: Architecture
title: "Environments: dev, QA, production"
description: "Dev runs sample data on the laptop; QA runs new code on a fresh copy of the production database; production is the kitchen. All read the Gemini key from .env."
tags: [architecture, data]
timestamp: 2026-10-27
status: draft
links:
  depends_on: [architecture/docker-server.md, architecture/migrations.md]
  governed_by: [rules/backup-before-change.md]
---
# Environments
| | data | port | how |
|---|---|---|---|
| dev | data-dev/ (sample data) | 8090 | tools/dev.sh |
| QA | data-qa/ = copy of production taken by tools/qa.sh | 8093 on the homelab | tools/qa.sh |
| production | data/ on the homelab | 8092 (HTTPS via the Cloudflare Tunnel) | tools/deploy.sh on the homelab |
- QA shows a banner so nobody logs a real meal there by mistake.
- Deploy order: tests → QA on a fresh copy → check QA → deploy (which backs up production first) → release notes
  and a GitHub release (okf/architecture/releases.md).
- Secrets: GEMINI_KEY and the FatSecret client in .env in the parent folder; never in the image or the repo.
- Production (first deployed 27 Oct): the homelab server, in ~/t1d/kitchen-carbs. Its address and login stay out of
  the repo.
  Its .env sets PROD_PORT=8092, QA_PORT=8093 (8090/8091 belong to the Omada controller there). The tablet opens the
  Cloudflare Tunnel's https name (okf/architecture/https.md). Code is copied with rsync, never data-dev/.
- Starting data: the foods, portions, photos, tags, size references, photo style and PIN from dev; dev's sample meals,
  test log entries, favorites of deleted foods and the fake Nightscout readings were left out.
- On the homelab, image builds use the host network (Docker's build network there can't resolve names).
