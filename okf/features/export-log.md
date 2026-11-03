---
type: Feature
title: "Export log"
description: "Download the log for a date range as CSV (for spreadsheets) or as a formatted PDF (to read, print or send to the care team)."
tags: [feature]
timestamp: 2026-10-26
status: draft
links:
  uses: [domain/meal-log.md]
  constrained_by: [rules/snapshot-log-values.md]
---
# Export log
CSV columns: date, time, food, portion, grams, qty, carbs, meal total, eaten, comments.

## PDF (decided 31 Oct)
Same date range and the same values as the CSV, laid out to read and print. Built on the home server (fpdf2, with the
app's own Kitchen Sans), so it downloads as a file on the tablet and phones alike. US Letter, portrait.
- First page: 'Kitchen Carbs · Meal log', the date range and when it was made; then the range at a glance: carbs per
  day (average), insulin given by kind (total and per day), and, with CGM data, time in range as a bar (below / in /
  above the family's target) with average, CV, GMI (14+ days) and sensor coverage, marked incomplete under 70 %.
- Then one section per day that has anything logged, oldest first: the day's carbs total, its fiber total (the meals'
  fiber, with how many foods had none; decided 2 Nov), insulin given and time in
  range, a small glucose trace for the day with the target band and meal times marked, and a table in time order:
  time, what (each food with its carbs, or the entry's values), carbs, BG, insulin, and notes (how much was eaten,
  comments, the corrected-total reason). A moved or later-changed row says 'edited'; the dates stay in the CSV.
- Lows stay in the warn colour; nothing is graded or advised (okf/rules/descriptive-stats-only.md). Insulin is only
  what was recorded; no calculated dose appears (okf/rules/no-dosing.md). Deleted rows are left out.
- Footer on every page: page numbers and 'Values as logged in Kitchen Carbs. Doses are what was recorded, not advice.'
- In the Log under the day: 'Export' with the date range and two buttons, 'CSV' and 'PDF'. Up to 92 days.
- The PDF's times follow the log's 12-hour setting (okf/features/review-log.md); the CSV keeps 24-hour times for spreadsheets.
