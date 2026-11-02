---
type: Journey
title: "Parent journey: from photo to logged meal"
description: "The path a parent takes from setting up a food to reviewing the day, and where the app helps or could cause a mistake."
tags: [journey]
timestamp: 2026-10-27
status: draft
links:
  involves: [features/sign-in.md, features/install-app.md, features/food-lookup.md, features/manual-log.md, features/photo-style-setup.md, features/scan-label.md, features/favorite-plates.md, features/connect-nightscout.md, features/meal-glucose-view.md, features/glucose-stats-view.md, features/photo-pipeline.md, features/manage-foods.md, features/browse-foods.md, features/view-food.md, features/build-plate.md, features/kitchen-scale.md, features/log-meal.md, features/annotate-meal.md, features/review-log.md, features/export-log.md, features/fill-in-fiber.md, features/meal-dose-summary.md, features/confirm-food.md, features/notify-family.md, features/tidepool-sync.md, features/nightscout-send.md, features/rate-meal.md]
steps:
  - id: sign-in
    phase: Set up (once)
    name: Sign in each device
    doing: "Opens the app on the kitchen tablet and each phone and signs in once with a family Google account."
    screen: "Sign-in screen"
    thinking: "I don't want anyone on the home network seeing or changing his meals."
    risk: "A shared or old Google account getting in, or the tablet signing itself out at dinner."
    helps: "Only listed accounts get in; devices stay signed in for 30 days and renew while used; the PIN still guards Manage."
    features: [features/sign-in.md, features/install-app.md]
  - id: connect
    phase: Set up (once)
    name: Connect Nightscout
    doing: "Creates a token in Nightscout and pastes the site address and token into the app; optionally turns on sending the log's carbs and insulin to Nightscout for OpenAPS forecasts."
    screen: "Manage → Settings → Nightscout (parent PIN)"
    thinking: "I want the forecast to know what he ate and what I gave, without anything counted twice."
    risk: "Using the API secret, which gives full write access; long-acting insulin counted as rapid-acting; the same insulin sent from two places."
    helps: "Reading needs only a readable token; sending is off until switched on and needs a role limited to treatments; long-acting goes as a note; a warning about double counting sits beside each switch; token stays on the home server. Tidepool can be connected in Settings to receive the log's carbs, meter BG and insulin, each switched on separately."
    features: [features/connect-nightscout.md, features/nightscout-send.md, features/tidepool-sync.md]
  - id: style-setup
    phase: Set up (once)
    name: Set the photo style
    doing: "Photographs the empty plate, bowl and dressing container, adds size references (e.g. a filled 1-cup measure), and adjusts the style prompt."
    screen: "Manage → Photo style (parent PIN)"
    thinking: "I want every photo to look like our kitchen, in our dishes."
    risk: "A style prompt that invites Gemini to change the food."
    helps: "The 'keep the food and amount exactly' instruction is fixed and always sent; base photos keep containers consistent."
    features: [features/photo-style-setup.md]
  - id: shoot
    phase: Set up (once per food)
    name: Weigh and photograph
    doing: "Serves a normal portion on the usual plate, weighs it, and photographs it on the quartz counter from the same spot."
    screen: "Phone or tablet camera"
    thinking: "Is this how much he actually eats?"
    risk: "Weighing the dry pasta instead of the cooked pasta gives the wrong grams."
    helps: "Base photos of the family's own dishes and the style prompt keep every styled photo consistent; grams are entered next to each photo."
    features: [features/photo-pipeline.md]
  - id: add
    phase: Set up (once per food)
    name: Add the food
    doing: "Enters name, carbs per 100 g with its source, and the weighed grams for each portion. Uploads the photos."
    screen: "Manage foods (parent PIN)"
    thinking: "Which source do I trust: the label or USDA?"
    risk: "Typo in carbs/100 g changes every portion."
    helps: "Carbs shown live as you type; food stays 'not verified' until confirmed."
    features: [features/manage-foods.md, features/photo-pipeline.md]
  - id: scan
    phase: Set up (once per food)
    name: Scan a nutrition label
    doing: "For a packaged food, photographs the barcode or the Nutrition Facts panel; for a generic food, searches USDA by name."
    screen: "Manage → Add a food → Look up → Photograph the nutrition label"
    thinking: "Did it read 27 g or 21 g?"
    risk: "A misread digit, a serving given only in cups, or fiber counted the wrong way."
    helps: "Label shown beside every number; warnings for anything that doesn't add up; serving size and total carbohydrate each confirmed against the label before saving; fiber kept beside the carbs for reference, never subtracted. Foods saved before fiber was kept get it from their own source with 'Fill in fiber', checked food by food."
    features: [features/scan-label.md, features/food-lookup.md, features/fill-in-fiber.md]
  - id: style
    phase: Set up (once per food)
    name: Review styled photos
    doing: "Compares each Gemini-styled photo with the original and accepts or regenerates it."
    screen: "Photo review, side by side"
    thinking: "Does the styled plate still show the same amount?"
    risk: "Gemini changes the amount on the plate."
    helps: "Side-by-side view; the original is always kept; estimated stand-ins are labelled."
    features: [features/photo-pipeline.md]
  - id: favorite
    phase: Mealtime
    name: Use a favorite plate
    doing: "For a usual meal, opens Favorites and taps 'Put on plate' instead of finding each food."
    screen: "Foods → Favorites"
    thinking: "Same breakfast as most days."
    risk: "Today's plate differs a little from the favorite."
    helps: "Every item lands on the plate with its grams, ready to tune; carbs use current values."
    features: [features/favorite-plates.md]
  - id: find
    phase: Mealtime
    name: Find the food
    doing: "Searches or scrolls to the food while cooking."
    screen: "Foods list"
    thinking: "Quick, dinner is ready."
    risk: "Picks white pasta when it was whole-wheat."
    helps: "Large thumbnails and plain names; variants are separate foods."
    features: [features/browse-foods.md]
  - id: match
    phase: Mealtime
    name: Match the plate
    doing: "Flips through portion photos to find the one that looks like the plate in front of them."
    screen: "Food view"
    thinking: "His plate is between small and medium."
    risk: "Choosing by eye when the plate is in between."
    helps: "Half-portion steps on the plate; grams shown under every photo for the scale."
    features: [features/view-food.md]
  - id: plate
    phase: Mealtime
    name: Build the plate
    doing: "Taps each food, sets its weight (slider, typed grams, or Use from the kitchen scale) and reads the total."
    screen: "Plate bar"
    thinking: "What's the total?"
    risk: "Forgetting the juice or a side."
    helps: "Plate list stays visible with every item and its carbs; a food this person hasn't checked shows its carbs and a Confirm button."
    features: [features/build-plate.md, features/kitchen-scale.md, features/confirm-food.md]
  - id: dose
    phase: Mealtime
    name: Check the summary and the dose
    doing: "Taps Save to log; reads the meal, the BG and insulin on board, and the dose worked out from their own ratios, then gives it with the pump or pen."
    screen: "Meal summary (modal over the plate)"
    thinking: "Does this match what the pump says?"
    risk: "Wrong ratios, an old CGM reading, or insulin still on board being missed; trusting the number without checking."
    helps: "Every step is shown; the CGM reading is used only if under 15 minutes old; IOB from Nightscout comes off the correction, or it says none was found; rounded down to 0.05 u; check against the pump."
    features: [features/meal-dose-summary.md, features/build-plate.md]
  - id: record
    phase: Mealtime
    name: Record BG and insulin
    doing: "Adds a log entry with the meter reading and the insulin the pump or pen gave; carbs too if it wasn't a food-list meal."
    screen: "Log → Add entry"
    thinking: "I want the care team to see what I actually gave."
    risk: "Reading the app's totals as advice, or a typo in units (25 instead of 2.5)."
    helps: "Insulin in the log is only ever what was typed, never the summary's number; units shown with one decimal place and 'u' everywhere."
    features: [features/manual-log.md]
  - id: save
    phase: Mealtime
    name: Save the meal
    doing: "Taps Save; time defaults to now."
    screen: "Plate → Save to log"
    thinking: "Done, let's eat."
    risk: "Server off: meal not saved."
    helps: "Saved on the tablet and synced later, with a 'waiting to sync' line. 'Pin as favorite' keeps a usual plate for next time."
    features: [features/log-meal.md, features/favorite-plates.md]
  - id: notified
    phase: Mealtime
    name: Other parent is told
    doing: "The parent at work gets a notification on their phone: 'Meal logged · 48 g carbs', the time, foods, BG and insulin typed."
    screen: "Phone notification → Log"
    thinking: "I want to know he ate and what was given without calling home."
    risk: "Reading the notification as a dose suggestion, or test meals from QA reaching a phone."
    helps: "Shows only what was logged, never the calculated dose; QA sends nothing; turned on per device in Manage → Settings."
    features: [features/notify-family.md]
  - id: after
    phase: After the meal
    name: Note what was eaten
    doing: "Marks All / Most / Half / Little / None and adds a comment like 'left the crusts'."
    screen: "Log → meal entry"
    thinking: "He only ate half; I'll tell the pump/care team."
    risk: "Expecting the app to change carbs for 'half eaten'."
    helps: "Clear wording: this is a note; carbs stay as served."
    features: [features/annotate-meal.md]
  - id: curve
    phase: After the meal
    name: See how glucose went
    doing: "Opens the meal 3 hours later and looks at the curve with start, peak and 2-hour values next to the eaten note."
    screen: "Log → meal entry, glucose curve"
    thinking: "He went high, but he also had juice at 7."
    risk: "Reading one curve as proof a portion was wrong, or a sensor gap as a flat line."
    helps: "Overlapping meals shown together; gaps shown as gaps; no good/bad grading. The rise in the first hour and the minutes to peak are shown as numbers; the parent rates how fast it rose, and each food then shows how its meals were rated."
    features: [features/meal-glucose-view.md, features/rate-meal.md]
  - id: review
    phase: Later
    name: Review and share
    doing: "Looks at the day and 14-day statistics next to carbs; exports a CSV for the care team appointment."
    screen: "Log, Export"
    thinking: "Why was Tuesday's dinner high?"
    risk: "Editing old meals would make history unreliable."
    helps: "Past days are read-only; comments and eaten notes are in the export."
    features: [features/review-log.md, features/export-log.md, features/glucose-stats-view.md]
---
# Parent journey
Primary user is a parent at the counter. The child looks at photos alongside but does not edit data.
