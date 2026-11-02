"""Meal summary dose (okf/features/meal-dose-summary.md), bounded by okf/rules/no-dosing.md."""
from datetime import datetime

import pytest

from server import dose
from test_app import app  # noqa: F401  (fixture)

SETTINGS = {"carb_ratio": [{"start": "00:00", "value": 15}, {"start": "06:00", "value": 12}, {"start": "11:00", "value": 15}],
            "isf": [{"start": "00:00", "value": 50}], "target": [{"start": "00:00", "value": 120}]}


def test_steps_and_rounding_down():
    r = dose.calc(62, 210, 0.6, dose.check_settings(SETTINGS), "18:30")
    assert (r["carb_ratio"], r["carb_u"], r["correction_u"], r["iob_off"]) == (15, 4.13, 1.8, 0.6)
    assert r["total_exact"] == 5.333 and r["dose"] == 5.3            # 5.33 rounded down, not to nearest
    assert dose.calc(45, None, None, dose.check_settings(SETTINGS), "07:15")["dose"] == 3.75   # breakfast block 1:12


def test_rounding_step_is_the_parents():
    """okf/domain/insulin-settings.md: 0.05, 0.1, 0.5 or 1 u, always down; settings saved before it default to 0.05."""
    assert dose.calc(62, 210, 0.6, SETTINGS, "18:30")["dose"] == 5.3                # older saved settings: no round_to
    for step, want in ((0.1, 5.3), (0.5, 5.0), (1, 5.0)):
        r = dose.calc(62, 210, 0.6, dose.check_settings({**SETTINGS, "round_to": step}), "18:30")
        assert (r["dose"], r["round_to"]) == (want, step)
    assert dose.calc(39, None, None, dose.check_settings({**SETTINGS, "round_to": 0.5}), "18:30")["dose"] == 2.5  # 2.6 down
    with pytest.raises(ValueError, match="0.05, 0.1, 0.5 or 1"):
        dose.check_settings({**SETTINGS, "round_to": 0.25})


def test_iob_only_comes_off_the_correction():
    s = dose.check_settings(SETTINGS)
    big = dose.calc(30, 170, 5, s, "12:00")                          # correction 1 u, IOB 5 u: correction gone, carbs stay
    assert big["iob_off"] == 1 and big["dose"] == 2
    low = dose.calc(30, 95, 2, s, "12:00")                           # BG under target: IOB not used, correction lowers it
    assert low["iob_used"] is False and low["iob_off"] == 0 and low["dose"] == 1.5
    assert dose.calc(5, 40, None, s, "12:00")["dose"] == 0           # never below zero


def test_settings_are_checked():
    for bad, msg in (({**SETTINGS, "carb_ratio": [{"start": "06:00", "value": 12}]}, "00:00"),
                     ({**SETTINGS, "isf": [{"start": "00:00", "value": 2}]}, "between 5 and 500"),
                     ({**SETTINGS, "target": [{"start": "25:00", "value": 120}]}, "isn't a time"),
                     ({**SETTINGS, "target": []}, "at least one")):
        with pytest.raises(ValueError, match=msg):
            dose.check_settings(bad)
    unsorted = {**SETTINGS, "carb_ratio": [{"start": "11:00", "value": 15}, {"start": "00:00", "value": 10}]}
    assert [b["start"] for b in dose.check_settings(unsorted)["carb_ratio"]] == ["00:00", "11:00"]


def test_summary_endpoint(app):
    client, main = app
    assert client.get("/api/dose?carbs=40&at=18:30").json()["ready"] is False      # no settings, no number
    assert client.put("/api/dose-settings", json=SETTINGS, headers={"X-Parent-Pin": ""}).status_code == 401
    assert client.put("/api/dose-settings", json={**SETTINGS, "isf": []}).status_code == 422
    assert client.put("/api/dose-settings", json={**SETTINGS, "round_to": 0.3}).status_code == 422
    assert client.put("/api/dose-settings", json={**SETTINGS, "round_to": 0.5}).json()["settings"]["round_to"] == 0.5
    assert client.put("/api/dose-settings", json=SETTINGS).json()["updated"] == "2026-10-27"
    now_ms = int(datetime(2026, 10, 27, 18, 30).timestamp() * 1000)
    with main.db.connect() as c:
        c.execute("INSERT INTO glucose(date_ms, sgv, direction) VALUES (?, 220, 'Flat')", (now_ms - 5 * 60000,))
    r = client.get("/api/dose?carbs=45&at=18:30").json()                          # fresh CGM, no Nightscout IOB
    assert r["bg_source"] == "cgm" and r["calc"]["bg"] == 220 and r["calc"]["iob"] is None and r["calc"]["dose"] == 5
    assert client.get("/api/dose?carbs=45&at=18:30&bg=120").json()["calc"]["dose"] == 3   # typed meter BG wins
    assert client.get("/api/dose?carbs=45&at=18:30&use_cgm=false").json()["calc"]["correction_u"] is None   # box cleared
    with main.db.connect() as c:
        c.execute("DELETE FROM glucose")
        c.execute("INSERT INTO glucose(date_ms, sgv, direction) VALUES (?, 220, 'Flat')", (now_ms - 20 * 60000,))
    r = client.get("/api/dose?carbs=45&at=18:30").json()                          # 20 min old: not used
    assert r["cgm"]["age_min"] == 20 and r["bg_source"] is None and r["calc"]["correction_u"] is None
    assert client.get("/api/dose?carbs=45&at=18:30&bg=10").status_code == 422


def test_summary_uses_fresh_iob_only(app, monkeypatch):
    client, main = app
    client.put("/api/dose-settings", json=SETTINGS)
    now_ms = int(datetime(2026, 10, 27, 18, 30).timestamp() * 1000)
    with main.db.connect() as c:
        main.db.set_setting(c, "ns_url", "http://ns.test"); main.db.set_setting(c, "ns_token", "t")
    live = {"bg": {"date_ms": now_ms - 3 * 60000, "sgv": 210, "direction": "FortyFiveUp"},
            "iob": {"units": 0.6, "mills": now_ms - 2 * 60000, "source": "Loop"}, "error": None}
    monkeypatch.setattr(main.nightscout, "live", lambda url, token: live)
    r = client.get("/api/dose?carbs=62&at=18:30").json()
    assert r["iob_fresh"] and r["calc"]["iob_off"] == 0.6 and r["calc"]["dose"] == 5.3
    live["iob"] = {"units": 0.6, "mills": now_ms - 40 * 60000, "source": "Loop"}
    r = client.get("/api/dose?carbs=62&at=18:30").json()
    assert not r["iob_fresh"] and r["calc"]["iob"] is None and r["calc"]["dose"] == 5.9


def test_nightscout_iob_shapes(monkeypatch):
    from server import nightscout
    answers = {}
    def fake(url, token, path, params):
        a = answers.get(path)
        if isinstance(a, Exception):
            raise a
        return a
    monkeypatch.setattr(nightscout, "_get", fake)
    answers["/api/v2/properties/iob"] = {"iob": {"iob": 1.25, "mills": 1793115000000, "source": "OpenAPS"}}
    assert nightscout.iob("u", "t") == {"units": 1.25, "mills": 1793115000000, "source": "OpenAPS"}
    answers["/api/v2/properties/iob"] = nightscout.NightscoutError("404")
    answers["/api/v1/devicestatus.json"] = [{"created_at": "2026-10-27T18:28:00Z", "pump": {"iob": {"bolusiob": 0.8}}}]
    assert nightscout.iob("u", "t")["units"] == 0.8
    answers["/api/v1/devicestatus.json"] = [{"created_at": "2026-10-27T18:28:00Z", "loop": {"iob": {"iob": 2.1, "timestamp": "2026-10-27T18:25:00Z"}}}]
    assert nightscout.iob("u", "t")["source"] == "Loop"
    answers["/api/v2/properties/iob"] = [{"sgv": 120}]                    # something else entirely: no guess
    answers["/api/v1/devicestatus.json"] = [{"created_at": "2026-10-27T18:28:00Z", "device": "xdrip"}]
    assert nightscout.iob("u", "t") is None
