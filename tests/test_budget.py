"""The budget worked out from the breakdown and the schedule."""

import pytest

from slugline import budget, parse
from slugline.breakdown import breakdown
from slugline.elements import Element, ElementSheet
from slugline.schedule import Schedule, ShootDay

SCRIPT = """Title: Heist

INT. BANK - DAY

ANNA
Open it.

BOB
I can't.

EXT. STREET - NIGHT

ANNA
Run.

INT. BANK - NIGHT

BOB
Wait.

EXT. ROOF - NIGHT

ANNA
Jump.
"""


def setup(level="low", days=None, sheet=None, **settings):
    b = breakdown(parse(SCRIPT))
    plan = Schedule(days=[ShootDay(scenes=d) for d in days]) if days is not None else None
    result = budget.compute(b, plan, sheet, budget.BudgetSettings(level=level, **settings))
    lines = {line["key"]: line for c in result["chapters"] for line in c["lines"]}
    return result, lines


def test_quantities_follow_the_schedule():
    result, lines = setup(days=[["1", "3"], ["2"], ["4"]])
    assert result["days"] == 3 and result["scheduled_days"] == 3 and result["estimated_days"] == 0
    # ANNA works days 1, 2 and 3; BOB days 1 only: they are paid for the days in between too.
    assert lines["cast:ANNA"]["units"] == 3
    assert lines["cast:BOB"]["units"] == 1
    assert lines["cast:ANNA"]["rate"] == budget.LEVELS["low"]["rates"]["cast.lead"]
    assert lines["location:BANK"]["units"] == 1  # both bank scenes on one day
    assert lines["camera"]["units"] == 3
    director = lines["crew:director"]
    assert director["units"] == 3 + 3  # shooting days plus a day of preparation each
    assert result["subtotal"] == pytest.approx(sum(c["total"] for c in result["chapters"]))
    assert result["total"] == pytest.approx(result["subtotal"] + result["contingency"]["amount"])


def test_social_security_overtime_and_contingency():
    result, lines = setup(days=[["1", "3"], ["2"], ["4"]])
    crew = sum(line["total"] for key, line in lines.items() if key.startswith("crew:"))
    cast = sum(line["total"] for key, line in lines.items() if key.startswith("cast:"))
    social = budget.PERCENTAGES["social"]
    assert lines["overtime"]["total"] == round(crew * budget.PERCENTAGES["overtime"])
    assert lines["social:cast"]["total"] == round(cast * social)
    assert lines["social:crew"]["total"] == round((crew + lines["overtime"]["total"]) * social)
    assert result["contingency"]["amount"] == round(result["subtotal"] * budget.PERCENTAGES["contingency"])
    # All of them can be changed: no social security, no reserve.
    changed, lines = setup(days=[["1", "3"], ["2"], ["4"]], percentages={"social": 0, "contingency": 0})
    assert lines["social:crew"]["total"] == 0 and changed["contingency"]["amount"] == 0
    assert changed["total"] == changed["subtotal"] < result["subtotal"]
    assert budget.BudgetSettings.from_dict({"percentages": {"social": 5, "nope": 0.1}}).percentages == {}


def test_long_gaps_are_not_paid_as_hold():
    from slugline.budget import _paid_days

    assert _paid_days({0, 2, 3}) == (3, 1)  # one day off between: paid
    assert _paid_days({0, 10}) == (2, 0)  # released and called again


def test_moving_a_scene_changes_the_budget():
    together, _ = setup(days=[["1", "3"], ["2", "4"]])
    apart, lines = setup(days=[["1"], ["2"], ["3"], ["4"]])
    assert apart["days"] == 4 and lines["location:BANK"]["units"] == 2
    assert apart["total"] > together["total"]


def test_without_a_schedule_days_are_estimated():
    result, _ = setup()
    assert result["scheduled_days"] == 0 and result["days"] == result["estimated_days"] >= 1


def test_elements_and_quotes():
    sheet = ElementSheet(scenes={
        "2": [Element("vehicles", "Getaway car", "", "manual"), Element("sfx", "Explosion", "", "auto"),
              Element("extras", "Crowd", "", "auto")],
        "4": [Element("sfx", "Explosion", "", "auto")],
    })
    result, lines = setup(days=[["1", "3"], ["2"], ["4"]], sheet=sheet)
    car, boom, crowd = lines["element:vehicles|Getaway car"], lines["element:sfx|Explosion"], lines["extras"]
    assert (car["units"], car["unit"]) == (1, "days")
    assert (boom["units"], boom["to_quote"], boom["quoted"]) == (2, True, False)
    assert crowd["units"] == budget.LEVELS["low"]["extras"] * 1
    assert result["to_quote"]["count"] == 1
    quoted, lines = setup(days=[["1", "3"], ["2"], ["4"]], sheet=sheet, quotes={"element:sfx|Explosion": 18000})
    assert lines["element:sfx|Explosion"]["total"] == 18000 and quoted["to_quote"]["count"] == 0


def test_hand_changes_and_extra_lines():
    _, lines = setup(days=[["1"]], rates={"camera": 500}, units={"vans": 2},
                     extra=[{"chapter": "04", "concept": "Bank vault set", "units": 1, "rate": 9000}])
    assert lines["camera"]["rate"] == 500 and lines["camera"]["edited"]
    assert lines["vans"]["units"] == 2
    assert lines["extra:0"]["total"] == 9000 and lines["extra:0"]["chapter"] == "04"


def test_levels_scale():
    short, _ = setup("short", days=[["1", "3"], ["2"], ["4"]])
    low, _ = setup("low", days=[["1", "3"], ["2"], ["4"]])
    medium, _ = setup("medium", days=[["1", "3"], ["2"], ["4"]])
    assert short["total"] < low["total"] < medium["total"]


def test_scene_costs_add_up_to_what_shooting_them_costs():
    result, _ = setup(days=[["1", "3"], ["2"], ["4"]])
    costs = {s["number"]: s["cost"] for s in result["scenes"]}
    assert set(costs) == {"1", "2", "3", "4"} and all(c > 0 for c in costs.values())
    # Scene 2 has a shooting day to itself; scene 1 shares one with scene 3.
    assert costs["2"] > costs["1"]
    assert result["scenes"][0]["cost"] == max(costs.values())


def test_settings_are_cleaned():
    s = budget.BudgetSettings.from_dict({"level": "huge", "rates": {"a": -5, "b": "x", "c": 10},
                                         "extra": [{"chapter": "99", "concept": "  ", "units": "x"}]})
    assert s.level == budget.DEFAULT_LEVEL and s.rates == {"c": 10}
    assert s.extra == [{"chapter": "04", "concept": "Other", "units": 1.0, "rate": 0.0}]


def test_every_budget_word_is_translated_in_the_app():
    import json
    from pathlib import Path

    es_ts = (Path(__file__).parents[1] / "web" / "src" / "es.ts").read_text(encoding="utf-8")
    def entry(key: str, value: str) -> bool:
        quoted = f"{json.dumps(key, ensure_ascii=False)}: {json.dumps(value, ensure_ascii=False)}"
        return quoted in es_ts or f"  {key}: {json.dumps(value, ensure_ascii=False)}" in es_ts

    missing = [k for k, v in budget.BUDGET_ES.items() if not entry(k, v)]
    assert not missing
    result, _ = setup(days=[["1", "3"], ["2"], ["4"]])
    concepts = {line["concept"] for c in result["chapters"] for line in c["lines"]}
    names = {"ANNA", "BOB", "BANK", "STREET", "ROOF"}
    assert concepts - names <= set(budget.BUDGET_ES)
    assert {c["label"] for c in result["chapters"]} <= set(budget.BUDGET_ES)


def test_api_exports_and_new_drafts():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from slugline.server import create_app

    client = TestClient(create_app(), headers={"x-slugline": "1"})
    sid = client.post("/api/scripts", params={"filename": "heist.fountain"}, content=SCRIPT.encode()).json()["id"]
    first = client.get(f"/api/scripts/{sid}/budget").json()
    assert first["total"] > 0 and first["previous"] is None

    changed = client.put(f"/api/scripts/{sid}/budget", json={"level": "short", "rates": {"camera": 100}}).json()
    assert changed["level"] == "short" and changed["total"] < first["total"]
    assert client.put(f"/api/scripts/{sid}/budget", json={"level": "galactic"}).status_code == 422

    csv = client.get(f"/api/scripts/{sid}/export/budget.csv", params={"lang": "es"})
    assert csv.status_code == 200 and "Personal artístico" in csv.text and "TOTAL" in csv.text
    pytest.importorskip("reportlab")
    pdf = client.get(f"/api/scripts/{sid}/export/budget.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    # A rewrite adds a scene: the new draft keeps the level and rates and says what changed.
    draft = SCRIPT + "\nEXT. HARBOUR - NIGHT\n\nANNA\nGo.\n"
    sid2 = client.post("/api/scripts", params={"filename": "heist2.fountain"}, content=draft.encode()).json()["id"]
    second = client.get(f"/api/scripts/{sid2}/budget").json()
    assert second["level"] == "short" and second["settings"]["rates"] == {"camera": 100}
    assert second["previous"]["total"] == changed["total"]
    assert second["total"] > changed["total"]
