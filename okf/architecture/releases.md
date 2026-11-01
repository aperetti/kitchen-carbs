---
type: Architecture
title: "Release notes and GitHub releases"
description: "Every production deploy gets a dated version, a plain-language note in CHANGELOG.md, a git tag and a GitHub release with the same note."
tags: [architecture]
timestamp: 2026-11-01
status: draft
links:
  depends_on: [architecture/environments.md]
---
# Release notes and GitHub releases
- CHANGELOG.md keeps an 'Unreleased' section at the top. Each change adds a line there as it is made, written for
  the family (what changed on screen and why), not as commit messages.
- After a deploy succeeds, `tools/release.sh --deployed` turns 'Unreleased' into the version heading, commits it, tags the commit
  and publishes. Versions are the deploy date, v2026.11.01, with .2, .3 for a second or third deploy that day.
- Publishing pushes main and the tags to the GitHub remote (origin) and makes a GitHub release for each tag that
  doesn't have one, using that version's section of CHANGELOG.md as the release text. A deploy made before GitHub
  was set up is tagged locally and published on the next run.
- Nothing is released that didn't reach production: tagging needs --deployed and is run after deploy, never
  before. Without it the script only publishes tags that already exist.
- Release notes never include the server's address, the family's emails or anything from the database.
