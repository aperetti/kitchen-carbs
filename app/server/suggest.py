"""Suggest a meal from the family's own logged meals (okf/features/suggest-meal.md). Pure functions; main.py reads the data.

meals: [{"day": "2026-11-18", "time": "12:10", "items": [{"food_id", "portion_id", "carbs"}]}], newest first or any order
foods: {food_id: {"name", "carbs_per_100g", "portions": [{"id", "label", "grams"}], "tags": {"breakfast", "fruit"}}},
       today's values, tag names in lower case
"""
from datetime import date
from statistics import median

SLOTS = ("breakfast", "lunch", "dinner")
DAYS = 90            # history looked at
HALF_LIFE = 30       # a meal this many days old counts half
MIN_MEALS = 3        # fewer of the chosen meal than this: every meal counts, the others at OTHER_MEALS
OTHER_MEALS = 0.2    # so that meal's own foods still come first
CARBS_MIN, CARBS_MAX = 5, 150
TAGGED = 0.1         # a food tagged for the meal but never logged for it: last in line, so swaps don't run out
PAIR, PAIR_MIN = 0.6, 3   # had in at least 60% of another food's meals (and 3 times): it comes along with that food
SIDE = 0.75          # or that food is in at least 75% of its meals (ketchup and nuggets) ...
SIDE_SHARE = 0.3     # ... and it's in at least 30% of that food's: a food had 3 times doesn't tag along with a staple
GROUP_MAX = 4        # foods in a group: nuggets, ketchup, carrots, dressing
SMALL = 10           # g: a food (with its sides) under this isn't added just for carbs
FILL_FROM = 4        # adding for carbs: the best fit of the next this many foods


def minutes(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:5])


def slot_of(hhmm: str, meal_times: dict) -> str:
    """The meal time nearest the clock time, going round midnight."""
    m = minutes(hhmm)
    gap = lambda s: min(abs(m - minutes(meal_times[s])), 1440 - abs(m - minutes(meal_times[s])))
    return min(SLOTS, key=gap)


def weight(m: dict, today: str) -> float:
    return m.get("boost", 1) * 0.5 ** ((date.fromisoformat(today) - date.fromisoformat(m["day"])).days / HALF_LIFE)


def usable(meals: list, foods: dict) -> list:
    """Each meal's items whose food is still in the food list; meals left empty are dropped."""
    out = []
    for m in meals:
        items = [i for i in m["items"] if i.get("food_id") in foods and foods[i["food_id"]]["portions"]]
        if items:
            out.append({**m, "items": items})
    return out


def for_slot(meals: list, slot: str, meal_times: dict) -> tuple[list, bool]:
    """That meal's history, or every meal when there are too few (the second value says so), the others counting less."""
    mine = [m for m in meals if slot_of(m["time"], meal_times) == slot]
    if len(mine) >= MIN_MEALS:
        return mine, False
    return mine + [{**m, "boost": OTHER_MEALS} for m in meals if slot_of(m["time"], meal_times) != slot], True


def portion_for(food_id: str, meals: list, foods: dict) -> dict:
    """The portion this food was most often had in, if it still exists; else its first."""
    f = foods[food_id]
    ids = [i["portion_id"] for m in meals for i in m["items"] if i["food_id"] == food_id]
    have = {p["id"]: p for p in f["portions"]}
    for pid in sorted(set(ids), key=ids.count, reverse=True):
        if pid in have:
            return have[pid]
    return f["portions"][0]


def portion_carbs(food: dict, p: dict) -> float:
    return p["grams"] * food["carbs_per_100g"] / 100


def half(x: float) -> float:
    return max(0.5, round(x * 2) / 2)


def typical_qty(food_id: str, meals: list, foods: dict, p: dict) -> float:
    """How many portions of it were usually had, from the carbs logged (so dry or cooked weighing doesn't matter)."""
    pc = portion_carbs(foods[food_id], p)
    carbs = [i["carbs"] for m in meals for i in m["items"] if i["food_id"] == food_id]
    return half(median(carbs) / pc) if pc > 0 and carbs else 1.0


def defaults(meals: list) -> dict:
    totals = [sum(i["carbs"] for i in m["items"]) for m in meals]
    counts = [len({i["food_id"] for i in m["items"]}) for m in meals]
    return {"carbs": min(CARBS_MAX, max(CARBS_MIN, round(median(totals)))) if totals else None,
            "count": min(5, max(1, round(median(counts)))) if counts else 0}


def rank(meals: list, foods: dict, today: str, chosen: list, avoid: set, like: str | None = None, slot: str = "") -> list:
    """Candidate foods, best first: how often had (recent meals count more), more when often had with the foods
    already chosen, and twice as much when sharing a tag with `like` (the food being swapped out)."""
    sets = [(weight(m, today), {i["food_id"] for i in m["items"]}) for m in meals]
    had = {k: sum(k in ids for _, ids in sets) for k in chosen}   # meals with each chosen food
    score, together = {}, {}
    for w, ids in sets:
        for f in ids:
            score[f] = score.get(f, 0) + w
            # share of each chosen food's meals that also had this one: 1 = always together
            together[f] = together.get(f, 0) + sum(1 / had[k] for k in chosen if k in ids and k != f)
    for f, x in foods.items():   # tagged for this meal ('Lunch') but not had yet
        if slot in x["tags"] and f not in score and x["portions"] and x["carbs_per_100g"] > 0:
            score[f] = TAGGED
    tags = foods[like]["tags"] - set(SLOTS) - {"snack"} if like in foods else set()   # a meal tag says nothing about the food
    out = []
    for f, s in score.items():
        if f in avoid or f in chosen:
            continue
        s *= 1 + 2 * together.get(f, 0)
        if tags and foods[f]["tags"] & tags:
            s *= 2
        out.append((s, foods[f]["name"], f))
    out.sort(key=lambda x: (-x[0], x[1]))
    return [f for _, _, f in out]


def companions(meals: list) -> dict:
    """{"sides": {k: [f]}, "pairs": {k: [f]}}, closest first. f is a side of k when k is in at least SIDE of f's meals
    (ketchup is nearly always with nuggets, though nuggets don't always get ketchup); f pairs with k when it's in at
    least PAIR of k's meals. Sides follow any food in a group; pairs only the food leading it."""
    sets = [{i["food_id"] for i in m["items"]} for m in meals]
    n, both = {}, {}
    for ids in sets:
        for k in ids:
            n[k] = n.get(k, 0) + 1
            for f in ids - {k}:
                both[(k, f)] = both.get((k, f), 0) + 1
    pairs, sides = {}, {}
    for (k, f), c in both.items():
        if c >= PAIR_MIN and c / n[f] >= SIDE and c / n[k] >= SIDE_SHARE:
            sides.setdefault(k, []).append((c / n[f], f))
        elif c >= PAIR_MIN and c / n[k] >= PAIR:
            pairs.setdefault(k, []).append((c / n[k], f))
    best = lambda d: {k: [f for _, f in sorted(v, key=lambda x: (-x[0], x[1]))] for k, v in d.items()}
    return {"pairs": best(pairs), "sides": best(sides)}


def related(comp: dict, a: str, b: str) -> bool:
    return any(a in comp[k].get(b, []) or b in comp[k].get(a, []) for k in ("pairs", "sides"))


def groups_of(order: list, comp: dict) -> list:
    """The foods shown, in order, as groups: a food joins the group of an earlier food it goes with."""
    out = []
    for f in order:
        g = next((g for g in out if any(related(comp, f, x) for x in g)), None)
        g.append(f) if g else out.append([f])
    return out


def most(u: float) -> float:
    """The most of a food suggested before another food is added instead: a quarter more than usual, or half a portion."""
    return max(u + 0.5, half(u * 1.25))


def fit(rows: list, target: float, loose: bool = False) -> list:
    """Half-portion steps, never under half a portion, until the total is as close to the target as it gets. Each food
    stays near how much of it is usually had (half to one and a half times); loose lets it go further, when there's
    nothing more to add."""
    for r in rows:
        r.setdefault("usual", r["qty"])
        u = r["usual"]
        r["min"], r["max"] = (0.5, min(8.0, max(4.0, 2 * u))) if loose else (half(u * 0.5), most(u))
        if r.get("locked"):   # its serving is set
            r["min"] = r["max"] = r["qty"]
        r["qty"] = min(r["max"], max(r["min"], r["qty"]))
    total = lambda: sum(r["qty"] * r["pc"] for r in rows)
    for _ in range(200):
        best, gap = None, abs(total() - target)
        for r in rows:
            if r["pc"] <= 0:
                continue
            for d in (0.5, -0.5):
                q = r["qty"] + d
                if r["min"] <= q <= r["max"]:
                    g = abs(total() + d * r["pc"] - target)
                    if g < gap - 1e-9:
                        best, gap = (r, q), g
        if not best:
            break
        best[0]["qty"] = best[1]
    return rows


def suggest(meals: list, foods: dict, meal_times: dict, slot: str, today: str, target: float | None = None,
            keep: list | None = None, swap: str | None = None, exclude: set | None = None, locked: dict | None = None) -> dict:
    """keep: the foods shown, in order (the one being swapped included); the result's items are in the order to show.
    locked: {food: servings} kept as they are, never swapped or dropped; the other foods are sized around them."""
    locked = {f: q for f, q in (locked or {}).items() if f in foods and q > 0}
    keep = list(keep or []) + [f for f in locked if f not in (keep or [])]
    meals = usable(meals, foods)
    hist, everything = for_slot(meals, slot, meal_times)
    d = defaults([m for m in hist if "boost" not in m] or hist)   # how big and how many: that meal's own, if any
    out = {"meal": slot, "based_on": len(hist), "all_meals": everything, "own": sum("boost" not in m for m in hist), "default_carbs": d["carbs"], "items": [],
           "added": None, "target": None, "total": 0}
    if not hist:
        return out
    target = d["carbs"] if target is None else target
    comp = companions(meals)   # every meal: what goes with what doesn't depend on the time of day
    exclude = set(exclude or set())
    avoid = exclude | ({swap} if swap else set())
    flat = lambda gs: [f for g in gs for f in g]
    usual = {}

    def carbs_usual(f):   # the carbs of a food at its usual amount
        if f not in usual:
            p = portion_for(f, hist, foods)
            usual[f] = (p, portion_carbs(foods[f], p), locked.get(f) or typical_qty(f, hist, foods, p))
        return usual[f][1] * usual[f][2]

    top = lambda f: locked.get(f) or most(usual[f][2])   # the most of it before another food comes in

    def with_sides(lead, gs):   # the food, what it's usually had with, and the sides of each, up to GROUP_MAX
        g, have = [lead], set(flat(gs))
        add = lambda c: len(g) < GROUP_MAX and c not in g and c not in avoid and c not in have and g.append(c)
        for f in g:   # grows as it goes: a side's own sides come too
            for c in comp["sides"].get(f, []) + (comp["pairs"].get(f, []) if f == lead else []):
                add(c)
        return sorted(g, key=lambda f: -carbs_usual(f))   # led by the food with the carbs: nuggets, then the ketchup

    def new_group(gs, like=None, skip=frozenset(), least=0):
        """The next best food (not one in skip) with its sides; with least, the first whose group has that many carbs."""
        nxt = rank(hist, foods, today, flat(gs), avoid | skip, like=like, slot=slot)
        groups = (with_sides(f, gs) for f in nxt)
        first = None
        for g in groups:
            first = first or g
            if sum(carbs_usual(f) for f in g) >= least:
                return g
        return first

    def fill(gs, target, least):   # of the FILL_FROM best groups with at least `least` carbs, the closest to the target
        nxt = rank(hist, foods, today, flat(gs), avoid, slot=slot)
        cands = [g for g in (with_sides(f, gs) for f in nxt) if sum(carbs_usual(f) for f in g) >= least][:FILL_FROM]
        have = sum(carbs_usual(f) for f in flat(gs))
        return min(cands, key=lambda g: abs(have + sum(carbs_usual(f) for f in g) - target), default=None)

    order = [f for f in (keep or []) if f in foods and (f not in exclude or f == swap)]
    if swap and swap not in order:
        order.append(swap)
    groups = groups_of(order, comp)
    if swap in locked:   # a locked food stays
        swap = None
    if swap:   # its sides go with it (the ketchup with the nuggets); the new food, with its own, takes its place
        gone = {swap}
        gone |= {x for x in comp["sides"].get(swap, []) if x in order and x not in locked and carbs_usual(x) < carbs_usual(swap) and
                 not any(x in comp["sides"].get(y, []) for y in order if y not in gone and y != x)}
        at = order.index(swap) - sum(f in gone for f in order[:order.index(swap)])
        order = [f for f in order if f not in gone]
        g = new_group([order], like=swap, skip=frozenset(gone))   # the sides that left don't come back on their own
        if g:
            order[at:at] = g
            out["added"] = g[0]
        groups = [order]
    elif not order:   # a fresh meal: as many foods as that meal usually has
        while len(flat(groups)) < d["count"]:
            g = new_group(groups)
            if not g:
                break
            groups.append(g)
    # more carbs than the foods reach at a quarter over their usual amounts: another food (with its sides)
    # rather than bigger portions; fewer, and the rest reach the target without the last one: it goes
    # (not on a swap, which would take the new food straight off again)
    usual_total = lambda gs: sum(carbs_usual(f) for f in flat(gs))
    most_total = lambda gs: sum(carbs_usual(f) and usual[f][1] * top(f) for f in flat(gs))
    while len(groups) > 1 and not swap:   # the last group without a locked food
        n = next((n for n in range(len(groups) - 1, -1, -1) if not set(groups[n]) & set(locked)), None)
        rest = groups[:n] + groups[n + 1:] if n is not None else None
        if not rest or usual_total(groups) <= target * 1.15 or most_total(rest) < target:
            break
        groups = rest
    while len(flat(groups)) < 8 and most_total(groups) < target:
        # of the next few best foods, the one whose usual carbs best fill what's missing, if better than not
        short = target - most_total(groups)
        g = fill(groups, target, least=min(SMALL, (target - usual_total(groups)) / 2))
        if not g or abs(usual_total(groups + [g]) - target) >= short:
            break
        groups.append(g)
    rows = []
    for f in flat(groups):
        carbs_usual(f)
        p, pc, q = usual[f]
        rows.append({"food_id": f, "p": p, "pc": pc, "qty": q, "locked": f in locked})
    fit(rows, target)
    if abs(sum(r["qty"] * r["pc"] for r in rows) - target) > max(5, target * 0.1):   # nothing more to add: stretch
        fit(rows, target, loose=True)
    out["items"] = [{"food_id": r["food_id"], "food_name": foods[r["food_id"]]["name"], "portion_id": r["p"]["id"],
                     "portion_label": r["p"]["label"], "portion_grams": r["p"]["grams"], "qty": r["qty"],
                     "carbs": round(r["qty"] * r["pc"], 2), "locked": r["locked"]} for r in rows]
    out["target"] = round(target)
    out["total"] = round(sum(r["qty"] * r["pc"] for r in rows))   # exact, rounded once (okf/rules/whole-gram-rounding.md)
    return out
