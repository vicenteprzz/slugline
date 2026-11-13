"""Calendar, availability, daylight and rest in the shooting schedule."""

from datetime import date

import pytest

from slugline import budget, parse
from slugline.breakdown import breakdown
from slugline.constraints import Constraints, check, shooting_dates, sun_times
from slugline.schedule import Schedule, ShootDay

SCRIPT = """Title: Week

EXT. BEACH - DAWN

ANNA
Look.

INT. BAR - NIGHT

BOB
Another.

INT. OFFICE - DAY

ANNA
Hi.

INT. BAR - DAY

BOB
Closed.
"""


def test_constraints_are_cleaned():
    c = Constraints.from_dict({"start": "2027-03-01", "weekdays": [0, 1, 9, "x"], "city": "atlantis", "day_hours": 40,
                               "cast_off": {"ANNA": [["2027-03-05", "2027-03-02"], ["bad", "2027-01-01"]]}})
    assert c.start == "2027-03-01" and c.weekdays == [0, 1] and c.city == "" and c.day_hours == 18
    assert c.cast_off == {"ANNA": [["2027-03-02", "2027-03-05"]]}


def test_shooting_dates_skip_the_days_off():
    c = Constraints(start="2027-03-05", weekdays=[0, 1, 2, 3, 4])  # a Friday
    assert shooting_dates(c, 3) == ["2027-03-05", "2027-03-08", "2027-03-09"]


def test_daylight_matches_the_almanac():
    assert sun_times(date(2026, 6, 21), "madrid") == ("06:44", "21:48")
    assert sun_times(date(2026, 12, 21), "madrid") == ("08:34", "17:51")
    assert sun_times(date(2026, 6, 21), "nowhere") is None


def plan(*days):
    return Schedule(days=[ShootDay(scenes=scenes, date=when, call_time=call) for scenes, when, call in days])


def test_conflicts():
    b = breakdown(parse(SCRIPT))
    c = Constraints(city="madrid", cast_off={"BOB": [["2027-03-02", "2027-03-02"]]},
                    location_off={"OFFICE": [["2027-03-03", "2027-03-03"]]})
    schedule = plan((["1"], "2027-03-01", "08:00"), (["2", "4"], "2027-03-02", "18:00"), (["3"], "2027-03-03", "06:00"))
    found = {(p.kind, p.day, p.name) for p in check(schedule, b, c)}
    assert ("cast", 2, "BOB") in found  # Bob can't on the 2nd
    assert ("location", 3, "OFFICE") in found  # the office is closed on the 3rd
    assert ("dawn", 1, "") in found  # sunrise in Madrid is about 7:40 in March: an 8:00 call is late
    # Day 2 wraps at 05:00 (18:00 + 11 h); day 3 calls at 06:00: one hour of rest.
    rest = [p for p in check(schedule, b, c) if p.kind == "rest"]
    assert rest and rest[0].day == 3 and rest[0].detail["rest"] == 1.0


def test_reordering_moves_days_to_dates_that_work():
    b = breakdown(parse(SCRIPT))
    schedule = plan((["3"], "2027-03-01", ""), (["4"], "2027-03-02", ""))
    schedule.constraints = Constraints(cast_off={"ANNA": [["2027-03-01", "2027-03-01"]]}).to_dict()
    found = budget.reorder_days(b, schedule, budget.BudgetSettings())
    assert found.conflicts_before == 1 and found.conflicts_after == 0 and found.order == [1, 0]


def test_constraints_in_the_api_and_the_call_sheets():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from slugline.server import create_app

    client = TestClient(create_app(), headers={"x-slugline": "1"})
    sid = client.post("/api/scripts", params={"filename": "week.fountain"}, content=SCRIPT.encode()).json()["id"]
    assert client.post(f"/api/scripts/{sid}/schedule/dates").status_code == 404
    client.put(f"/api/scripts/{sid}/schedule", json={"days": [{"scenes": ["1", "3"]}, {"scenes": ["2", "4"]}]})
    assert client.post(f"/api/scripts/{sid}/schedule/dates").status_code == 422  # no start date yet
    saved = client.put(f"/api/scripts/{sid}/schedule/constraints", json={
        "start": "2027-03-05", "weekdays": [0, 1, 2, 3, 4], "city": "madrid",
        "cast_off": {"BOB": [["2027-03-08", "2027-03-08"]]},
    }).json()
    assert saved["constraints"]["city"] == "madrid"
    dated = client.post(f"/api/scripts/{sid}/schedule/dates").json()
    assert [d["date"] for d in dated["days"]] == ["2027-03-05", "2027-03-08"]
    assert {(p["kind"], p["name"]) for p in dated["problems"]} >= {("cast", "BOB")}
    assert dated["daylight"][0]["sunrise"] < dated["daylight"][0]["sunset"]
    # Editing the days keeps the constraints.
    kept = client.put(f"/api/scripts/{sid}/schedule", json={"days": [{"scenes": ["1", "3"], "date": "2027-03-05"},
                                                                     {"scenes": ["2", "4"], "date": "2027-03-08"}]}).json()
    assert kept["constraints"]["cast_off"] == {"BOB": [["2027-03-08", "2027-03-08"]]}

    pytest.importorskip("reportlab")
    sheet = client.get(f"/api/scripts/{sid}/export/call-sheets.pdf", params={"day": 1, "lang": "es"})
    assert sheet.status_code == 200 and sheet.content.startswith(b"%PDF")
