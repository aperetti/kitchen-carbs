---
type: Rule
title: "Glucose units"
description: "Store mg/dL as Nightscout does; display in the family's unit (mg/dL or mmol/L) everywhere, consistently."
tags: [nightscout, data, safety]
timestamp: 2026-10-27
status: draft
links:
  applies_to: [domain/glucose-reading.md, domain/target-range.md]
---
# Glucose units
Decision (27 Oct): the family uses **mg/dL**, so no conversion is shown. Every glucose value or chart still names its unit. mmol/L support (÷ 18.016, one decimal) stays possible but is not built in v1.
