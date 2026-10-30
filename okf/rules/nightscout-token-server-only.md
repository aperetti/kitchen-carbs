---
type: Rule
title: "Token stays on the server"
description: "The Nightscout token lives only in the Docker server's settings; the tablet never sees it."
tags: [nightscout, security]
timestamp: 2026-10-27
status: draft
links:
  applies_to: [architecture/nightscout-client.md]
---
# Token stays on the server
The tablet asks the local server for readings; the server calls Nightscout.
