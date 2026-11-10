---
type: Architecture
title: "Shared plate"
description: "The plate is one row on the server that every signed-in device reads and writes, so the family builds one meal together; each device keeps a copy for when the server can't be reached."
tags: [architecture, reliability]
timestamp: 2026-11-10
status: draft
links:
  implements: [domain/plate.md]
  uses: [architecture/storage.md, architecture/offline.md]
---
# Shared plate
Decided 10 Nov: one plate for the family across the kitchen tablet and the parents' phones.
- Stored: one row (migration 22) with the plate's rows, the plan it came from, a version number that goes up with
  every change, and when it changed. Rows are checked like a plan's rows (food or carbs typed by hand, sensible
  weights, at most 30), plus the row's own id and its photo path.
- Writing: every change on a device sends the whole plate a moment later (changes in quick succession, like dragging a
  weight, go as one). The last one sent wins; the plate is small and one person usually works on it at a time.
- Reading: while the app is open and showing, each device asks for the plate every 4 seconds and when it comes back
  to the front. A newer version replaces its own and redraws, with 'The plate was changed on another device.' A
  device that is mid-change (a weight being dragged or typed, or its own change not yet sent) waits until it is done.
- Saving the meal to the log empties the plate everywhere, so another device doesn't save the same meal again. A
  device that already has the meal summary open keeps its copy until it is closed; saving it there would log a second meal.
- Not shared: the meal's time guess and the meal summary, which belong to the device that saves it.
- Offline: each device keeps its last copy in its own storage (okf/architecture/offline.md). Changes made while the
  server can't be reached are sent when it is back, and then win over what is there.
- First start after the update: if the server's plate is empty and this device has rows, it sends its own.
