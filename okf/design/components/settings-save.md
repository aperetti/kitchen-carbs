---
type: component
title: "Settings save bar"
description: "Manage → Settings saves every change with one floating 'Unsaved changes' bar, the same one the log uses; the sections have no Save buttons of their own."
tags: [design, admin]
timestamp: 2026-11-03
status: draft
links:
  implements: [features/connect-nightscout.md, features/nightscout-send.md, features/tidepool-sync.md, domain/insulin-settings.md, features/review-log.md]
  guided_by: [design/guidelines/navigation.md, design/guidelines/phone-layout.md]
---
# Settings save bar
Decided 3 Nov: Settings had a different Save button in each section (Save contact, Change PIN, Save insulin settings,
Save accounts, Test and save, Save range, Save, and switches that saved as soon as they were tapped). The family asked
for the log's save bar instead.
- Nothing in Settings is saved as it's typed or tapped. As soon as anything differs from what is saved, the changed
  section gets the warn-coloured border and the bar floats up: 'Unsaved changes', 'Save changes', 'Discard'. Putting
  everything back by hand hides it. On a phone it is pinned to the bottom of the screen; on a tablet it sticks to the
  bottom of the settings column.
- Covered: Food lookup (contact email and region), Tags (renaming), Photo style (speed and the style description),
  Family accounts, Change parent PIN (current and new PIN both
  typed), Insulin settings, Log (earlier days, 12-hour clock), Nightscout connection and target range, and the
  Send to Nightscout and Tidepool options once they're on.
- Save changes saves each changed section in page order. A problem stops there and shows in the bar, named by its
  section, and that section stays changed; the ones before it are saved. The Nightscout connection is still tested
  before it's kept, and the Tidepool login and Nightscout token roles are still checked.
- Discard puts every section back as saved.
- Starting to send stays its own button, never the bar: 'Connect' for a first Nightscout connection, 'Check and send'
  and 'Connect and send' while Send to Nightscout or Tidepool is off. A general Save never starts sending the child's
  data to another service.
- Buttons that act at once rather than change a setting stay as they are: Add tag, Remove, a base photo's Add photo,
  Replace and Remove, Add size reference, a size reference's Edit with its own Save (one card at a time), 'Reset to the
  default' (fills the box; the bar saves it), Approve (sign in another device), Send now,
  Resend everything, Turn off, Remove, Disconnect, Sign out, Notify this device, Send a test, Open raw viewer.
- While there are unsaved changes, leaving Settings (another Manage tab, another app tab, Back, Lock) is held back
  with 'Save or discard the changes first' and the bar gives a small shake, as in the log.
