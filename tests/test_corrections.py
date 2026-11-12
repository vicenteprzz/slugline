"""Corrections made in the app: merged names, day or night set by hand, and
keyword suggestions made again."""

import pytest

from slugline import parse
from slugline.corrections import Corrections, apply
from slugline.elements import Element, ElementSheet, resuggest

SCRIPT = """Title: Gas

EXT. SUNRAY GAS - SERVICE STATION

A car pulls in.

REDHEAD
Fill it up.

EXT. SUNWAY GAS - SERVICE STATION - LATER

READHEAD
Thanks.

INT. DINER - NIGHT

A dog barks.

REDHEAD
Coffee.
"""


def test_merged_names_and_day_night_by_hand():
    fixes = Corrections()
    fixes.merge("characters", ["READHEAD", "REDHEAD"], "REDHEAD")
    fixes.merge("locations", ["SUNWAY GAS - SERVICE STATION"], "SUNRAY GAS - SERVICE STATION")
    fixes.set_day_night("1", "DAY")
    play = apply(parse(SCRIPT), fixes)
    assert [s.location for s in play.scenes] == ["SUNRAY GAS - SERVICE STATION"] * 2 + ["DINER"]
    assert [c for s in play.scenes for c in s.characters] == ["REDHEAD"] * 3
    # Scene 2 (LATER) follows scene 1, set by hand; scene 3 says NIGHT.
    assert [s.day_night for s in play.scenes] == ["DAY", "DAY", "NIGHT"]


def test_merges_follow_each_other_and_can_be_undone():
    fixes = Corrections()
    fixes.merge("characters", ["A"], "B")
    fixes.merge("characters", ["B"], "C")
    assert fixes.characters == {"A": "C", "B": "C"}
    fixes.merge("characters", ["C"], "A")  # changing your mind
    assert fixes.characters == {"B": "A", "C": "A"}
    fixes.unmerge("characters", "B")
    assert fixes.characters == {"C": "A"}
    with pytest.raises(ValueError):
        fixes.merge("props", ["X"], "Y")
    with pytest.raises(ValueError):
        fixes.set_day_night("1", "LUNCH")


def test_suggesting_again_keeps_claude_and_hand_work():
    sheet = ElementSheet(
        scenes={
            "1": [Element("props", "Old guess", "", "auto"), Element("props", "Hose", "", "manual")],
            "3": [Element("animals", "Dog", "", "ai")],
        },
        dismissed={"1": ["vehicles|car"]},
    )
    again = resuggest(SCRIPT, sheet)
    assert [(e.name, e.source) for e in again.for_scene("1")] == [("Hose", "manual")]  # car stays removed
    assert [(e.name, e.source) for e in again.for_scene("3")] == [("Dog", "ai")]


def test_api(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from slugline.server import create_app

    client = TestClient(create_app(), headers={"x-slugline": "1"})
    script = client.post("/api/scripts", params={"filename": "gas.fountain"}, content=SCRIPT.encode()).json()
    sid = script["id"]
    codes = {i["code"]: i for i in script["issues"]}
    assert codes["similar-characters"]["names"] == ["REDHEAD", "READHEAD"]
    assert any(i["code"] == "no-time" and i["scene"] == "1" for i in script["issues"])

    merged = client.post(f"/api/scripts/{sid}/corrections/merge",
                         json={"kind": "characters", "names": ["READHEAD"], "into": "REDHEAD"}).json()
    assert [c["name"] for c in merged["breakdown"]["characters"]] == ["REDHEAD"]
    assert "similar-characters" not in {i["code"] for i in merged["issues"]}

    dn = client.put(f"/api/scripts/{sid}/corrections/day-night", json={"scene": "1", "day_night": "DAY"}).json()
    assert [s["day_night"] for s in dn["breakdown"]["scenes"]] == ["DAY", "DAY", "NIGHT"]
    assert not any(i["code"] == "no-time" and i["scene"] == "1" for i in dn["issues"])
    assert client.put(f"/api/scripts/{sid}/corrections/day-night", json={"scene": "9", "day_night": "DAY"}).status_code == 404

    # Saved: a fresh app reading the same script sees the corrections.
    again = TestClient(create_app(), headers={"x-slugline": "1"}).get(f"/api/scripts/{sid}").json()
    assert again["corrections"]["characters"] == {"READHEAD": "REDHEAD"}

    undone = client.post(f"/api/scripts/{sid}/corrections/unmerge",
                         json={"kind": "characters", "name": "READHEAD"}).json()
    assert len(undone["breakdown"]["characters"]) == 2

    suggested = client.post(f"/api/scripts/{sid}/elements/suggest").json()
    assert {t["name"] for t in suggested["totals"]} >= {"Car", "Dog"}
