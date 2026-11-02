---
type: component
title: "Settings sidebar"
description: "Manage → Settings lists its section headings in a sidebar; tapping one scrolls to it and the one in view is marked."
tags: [design, admin]
timestamp: 2026-11-01
status: draft
links:
  implements: [features/connect-nightscout.md, features/nightscout-send.md, features/tidepool-sync.md, features/notify-family.md]
  uses_tokens: [design/foundations/color.md, design/foundations/typography.md]
---
# Settings sidebar
Decided 1 Nov: Nightscout moved from its own Manage tab into Settings, which had grown long, so Settings gained a
sidebar to move between its headings.
- Section order, as the family asked: Food lookup, Family accounts, Sign in another device, Change parent PIN,
  Insulin settings, Log, Nightscout, Tidepool, Notifications, Kitchen scale.
- Built from the page's own section headings (h2), so a new section appears without touching the sidebar.
- Wide screens: a narrow column on the left that stays put while the sections scroll. The heading in view is shown in
  ink with a bar beside it; the rest in the quiet vein colour.
- Phones: a row of headings across the top that stays put and scrolls sideways.
- Tapping a heading scrolls its section to the top; it is not a history step (okf guideline: every Manage step is a
  history entry applies to screens, not to places on one screen).
- Old links to #manage/nightscout open Settings at the Nightscout section.
