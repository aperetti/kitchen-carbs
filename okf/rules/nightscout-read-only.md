---
type: Rule
title: "Nightscout read-only"
description: "The app only reads from Nightscout. It never writes treatments, carbs or notes there."
tags: [nightscout, safety]
timestamp: 2026-10-27
status: draft
links:
  applies_to: [domain/glucose-reading.md, architecture/nightscout-client.md]
---
# Nightscout read-only
Carbs entered in the pump or loop app already reach Nightscout; writing them again from here would double-count.
