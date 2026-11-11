"""Revised drafts and the shooting schedule."""

import csv
import io
import json

import pytest

from slugline import parse
from slugline.breakdown import breakdown
from slugline.elements import Element, ElementSheet, load_or_carry, load_sheet, save_sheet, update_scene
from slugline.revisions import fingerprint, match_scenes
from slugline.schedule import (
    Schedule,
    ShootDay,
    day_stats,
    load_schedule,
    save_schedule,
    set_days,
    suggest,
    to_payload,
)
from slugline.schedule import load_or_carry as load_or_carry_schedule

DRAFT_1 = """Title: Two Rooms

INT. KITCHEN - NIGHT

ANNA pours coffee. Bob watches the door.

ANNA
You came back.

EXT. STREET - LATER

Bob hails a taxi in the rain.

BOB
Taxi!

INT. TAXI - NIGHT

The driver watches Bob in the mirror.

INT. HOTEL ROOM - NIGHT

Bob drops his bag on the bed.
"""

# Draft 2: a new scene after the kitchen, the street rewritten, the taxi cut,
# the hotel unchanged but renumbered.
DRAFT_2 = """Title: Two Rooms

INT. KITCHEN - NIGHT

ANNA pours coffee. Bob watches the door.

ANNA
You came back.

INT. HALLWAY - NIGHT

Bob stops at the mirror and fixes his tie.

EXT. STREET - LATER

Bob hails a taxi in the pouring rain. Nobody stops.

BOB
Taxi!

INT. HOTEL ROOM - NIGHT

Bob drops his bag on the bed.
"""


def prints(text):
    return [fingerprint(s) for s in parse(text).scenes]


# --- matching scenes ----------------------------------------------------------

def test_match_scenes_follows_renumbering_rewrites_and_cuts():
    m = match_scenes(prints(DRAFT_1), prints(DRAFT_2))
    assert {n: (s.old, s.status) for n, s in m.scenes.items()} == {
        "1": ("1", "unchanged"),
        "3": ("2", "changed"),
        "4": ("4", "unchanged"),
    }
    assert m.new == ["2"]
    assert m.omitted == [{"number": "3", "heading": "INT. TAXI - NIGHT"}]


def test_match_scenes_finds_moved_scenes_and_tells_same_headings_apart():
    a = "INT. BARN - NIGHT\n\nThe horses sleep.\n\nINT. BARN - NIGHT\n\nA lantern swings over the dead man.\n\nEXT. ROAD - DAY\n\nDust.\n"
    b = "EXT. ROAD - DAY\n\nDust.\n\nINT. BARN - NIGHT\n\nA lantern swings over the dead man.\n\nINT. BARN - NIGHT\n\nThe horses sleep.\n"
    m = match_scenes(prints(a), prints(b))
    assert {n: s.old for n, s in m.scenes.items()} == {"1": "3", "2": "2", "3": "1"}
    assert all(s.status == "unchanged" for s in m.scenes.values())


def test_one_changed_word_counts_as_a_change():
    a = "INT. A - DAY\n\nHe holds a revolver.\n"
    b = "INT. A - DAY\n\nHe holds a shotgun.\n"
    assert match_scenes(prints(a), prints(b)).scenes["1"].status == "changed"


# --- carrying a breakdown over -------------------------------------------------

def mark(category, name, source="manual"):
    return Element(category, name, "", source)


def test_breakdown_carries_over_to_a_revised_draft():
    save_sheet(DRAFT_1, ElementSheet(
        scenes={"1": [mark("props", "Coffee pot", "ai")], "2": [mark("vehicles", "Taxi")], "3": [mark("vehicles", "Cab")],
                "4": [mark("props", "Bag")]},
        dismissed={"2": ["sfx|rain"]},
        model="claude-opus-5-5",
    ))
    sheet = load_or_carry(DRAFT_2)

    assert {n: [e.name for e in items] for n, items in sheet.scenes.items()} == {
        "1": ["Coffee pot"], "3": ["Taxi"], "4": ["Bag"],
    }
    assert sheet.for_scene("1")[0].source == "ai"  # suggestions stay suggestions
    assert sheet.dismissed == {"3": ["sfx|rain"]}
    assert sheet.model == "claude-opus-5-5"
    assert sheet.needs_review() == ["3"]
    assert sheet.revision["new"] == ["2"]
    assert sheet.revision["omitted"] == [{"number": "3", "heading": "INT. TAXI - NIGHT", "elements": 1}]
    assert sheet.revision["from"]["title"] == "Two Rooms"
    # It was saved for the new draft, and the old draft's own breakdown is untouched.
    assert load_sheet(DRAFT_2) == sheet
    assert [e.name for e in load_sheet(DRAFT_1).for_scene("3")] == ["Cab"]

    # Saving a rewritten scene marks it as reviewed.
    update_scene(sheet, "3", [{"category": "vehicles", "name": "Taxi"}])
    assert sheet.needs_review() == [] and sheet.revision["scenes"]["3"]["status"] == "reviewed"


def test_carry_over_needs_the_same_script():
    save_sheet(DRAFT_1, ElementSheet(scenes={"1": [mark("props", "Mug")]}))
    other = DRAFT_2.replace("Title: Two Rooms", "Title: Something Else")
    assert load_or_carry(other) is None
    # An empty breakdown (someone chose to start over) is not carried over.
    save_sheet(DRAFT_1, ElementSheet())
    assert load_or_carry(DRAFT_2) is None


def test_carry_over_without_title_pages_compares_headings():
    untitled_1 = DRAFT_1.split("\n", 2)[2]
    untitled_2 = DRAFT_2.split("\n", 2)[2]
    save_sheet(untitled_1, ElementSheet(scenes={"4": [mark("props", "Bag")]}))
    assert [e.name for e in load_or_carry(untitled_2).for_scene("4")] == ["Bag"]
    assert load_or_carry("INT. MOON BASE - DAY\n\nSilence.\n") is None


def test_the_latest_earlier_draft_wins(monkeypatch):
    import slugline.revisions as revisions

    times = iter(["2027-01-01T10:00:00+00:00", "2027-02-01T10:00:00+00:00"] + ["2027-03-01T10:00:00+00:00"] * 5)

    class Clock:
        @staticmethod
        def now(tz=None):
            from datetime import datetime

            return datetime.fromisoformat(next(times))

    monkeypatch.setattr(revisions, "datetime", Clock)
    save_sheet(DRAFT_1, ElementSheet(scenes={"4": [mark("props", "Old bag")]}))
    draft_1b = DRAFT_1.replace("Bob drops his bag", "Bob throws his bag")
    save_sheet(draft_1b, ElementSheet(scenes={"4": [mark("props", "New bag")]}))
    assert [e.name for e in load_or_carry(DRAFT_2).for_scene("4")] == ["New bag"]


# --- schedule -----------------------------------------------------------------

def test_suggest_blocks_day_and_night_work_and_keeps_locations_together(example_text):
    b = breakdown(parse(example_text))
    plan = suggest(b, 5)
    rows = {s.number: s for s in b.scenes}

    scheduled = [n for d in plan.days for n in d.scenes]
    assert sorted(scheduled, key=int) == [s.number for s in b.scenes]  # every scene, once
    shifts = [{rows[n].day_night == "NIGHT" for n in d.scenes} for d in plan.days]
    assert all(len(s) == 1 for s in shifts)  # no day mixes day and night work
    first_night = next(i for i, s in enumerate(shifts) if s == {True})
    assert all(s == {True} for s in shifts[first_night:])  # nights in one block at the end
    for day in plan.days:
        stats = day_stats(day, b, 5)
        # A day only runs over when a single scene is longer than a day.
        assert not stats.over or len(day.scenes) == 1


def test_smaller_days_mean_more_days(example_text):
    b = breakdown(parse(example_text))
    assert len(suggest(b, 3).days) > len(suggest(b, 5).days) > len(suggest(b, 12).days)
    with pytest.raises(ValueError):
        suggest(b, 0)


def test_set_days_validates_and_keeps_ids():
    b = breakdown(parse(DRAFT_1))
    plan = set_days(b, [{"id": "d1", "scenes": ["2", "1"], "date": "2027-03-01", "notes": "Rain cover"}, {"scenes": []}])
    assert [d.scenes for d in plan.days] == [["2", "1"], []]
    assert plan.days[0].id == "d1" and plan.days[1].id
    payload = to_payload(plan, b)
    assert payload["unscheduled"] == ["3", "4"]
    assert payload["days"][0]["stats"]["locations"] == ["STREET", "KITCHEN"]
    for days, message in [
        ([{"scenes": ["9"]}], "no scene 9"),
        ([{"scenes": ["1"]}, {"scenes": ["1"]}], "scheduled twice"),
        ([{"scenes": "1"}], "list of scene numbers"),
    ]:
        with pytest.raises(ValueError, match=message):
            set_days(b, days)


def test_schedule_carries_over_to_a_revised_draft():
    save_schedule(DRAFT_1, Schedule(days=[ShootDay(["3", "4"], "2027-03-01", "", "a"), ShootDay(["2", "1"], "", "", "b")],
                                    pages_per_day=4))
    plan = load_or_carry_schedule(DRAFT_2)
    assert [(d.id, d.scenes, d.date) for d in plan.days] == [("a", ["4"], "2027-03-01"), ("b", ["3", "1"], "")]
    assert plan.pages_per_day == 4 and plan.revision["new"] == ["2"]
    assert to_payload(plan, breakdown(parse(DRAFT_2)))["unscheduled"] == ["2"]
    assert load_schedule(DRAFT_2) == plan


def test_schedule_exports():
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")
    from slugline.export import schedule_csv, schedule_pdf

    b = breakdown(parse(DRAFT_1))
    plan = Schedule(days=[ShootDay(["4", "1"], "2027-03-01", "Hotel lobby closed until 9"), ShootDay(["3"])])
    rows = list(csv.DictReader(io.StringIO(schedule_csv(b, plan))))
    assert [(r["day"], r["order"], r["scene"]) for r in rows] == [("1", "1", "4"), ("1", "2", "1"), ("2", "1", "3"), ("", "", "2")]
    assert rows[0]["date"] == "2027-03-01"

    text = "\n".join(page.extract_text() for page in pypdf.PdfReader(io.BytesIO(schedule_pdf(b, plan))).pages)
    for expected in ("DAY 1 OF 2", "Mon 01 Mar 2027", "Hotel lobby closed until 9", "INT. HOTEL ROOM - NIGHT", "NOT SCHEDULED"):
        assert expected in text


def test_cli_schedule(tmp_path, capsys):
    from slugline.cli import main

    path = tmp_path / "two_rooms.fountain"
    path.write_text(DRAFT_1, encoding="utf-8")
    assert main(["schedule", str(path), "--pages", "1"]) == 0
    out = capsys.readouterr().out
    assert "SHOOTING SCHEDULE" in out and "DAY 1" in out and "INT. KITCHEN - NIGHT" in out
    assert load_schedule(DRAFT_1) is not None

    assert main(["schedule", str(path), "--json"]) == 0  # the saved one, not a new suggestion
    assert json.loads(capsys.readouterr().out)["pages_per_day"] == 1
    assert main(["schedule", str(path), "--pages", "0"]) == 1


def test_assistant_reads_the_schedule():
    from slugline.agent import ScriptAgent

    plan = {"value": None}
    agent = ScriptAgent(DRAFT_1, schedule=lambda: plan["value"], elements=lambda: None)
    assert "no shooting schedule" in json.loads(agent.run_tool("shooting_schedule", {})[0])["note"]
    plan["value"] = Schedule(days=[ShootDay(["4", "1"], "2027-03-01")])
    data = json.loads(agent.run_tool("shooting_schedule", {})[0])
    assert data["days"][0]["scenes"] == ["4", "1"] and data["days"][0]["date"] == "2027-03-01"
    assert data["days"][0]["cast"] == ["ANNA"] and data["unscheduled"] == ["2", "3"]


def test_api_schedule_and_new_drafts():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from slugline.server import create_app

    client = TestClient(create_app(), headers={"x-slugline": "1"})
    sid = client.post("/api/scripts", params={"filename": "v1.fountain"}, content=DRAFT_1.encode()).json()["id"]
    assert client.get(f"/api/scripts/{sid}/export/schedule.pdf").status_code == 404

    plan = client.post(f"/api/scripts/{sid}/schedule", json={"pages_per_day": 1}).json()
    assert plan["pages_per_day"] == 1 and plan["unscheduled"] == []
    assert client.post(f"/api/scripts/{sid}/schedule", json={"pages_per_day": 0}).status_code == 422

    days = [{"id": "x", "scenes": ["4", "1", "2"], "date": "2027-03-01", "notes": ""}]
    saved = client.put(f"/api/scripts/{sid}/schedule", json={"days": days}).json()
    assert saved["days"][0]["scenes"] == ["4", "1", "2"] and saved["unscheduled"] == ["3"]
    bad = client.put(f"/api/scripts/{sid}/schedule", json={"days": [{"scenes": ["1", "1"]}]})
    assert bad.status_code == 422 and "twice" in bad.json()["detail"]
    assert client.get(f"/api/scripts/{sid}/export/schedule.csv").status_code == 200

    client.put(f"/api/scripts/{sid}/elements/2", json={"elements": [{"category": "vehicles", "name": "Taxi"}]})

    # The revised draft opens with both carried over.
    v2 = client.post("/api/scripts", params={"filename": "v2.fountain"}, content=DRAFT_2.encode()).json()
    assert v2["schedule"]["days"][0]["scenes"] == ["4", "1", "3"]
    assert v2["schedule"]["unscheduled"] == ["2"]
    assert v2["elements"]["scenes"]["3"][0]["name"] == "Taxi"
    assert v2["elements"]["revision"]["scenes"]["3"]["status"] == "changed"

    # Starting the new draft's breakdown empty sticks, and doesn't touch the old draft.
    cleared = client.delete(f"/api/scripts/{v2['id']}/elements").json()
    assert cleared["scenes"] == {} and cleared["revision"] is None
    again = client.post("/api/scripts", params={"filename": "v2.fountain"}, content=DRAFT_2.encode()).json()
    assert again["elements"]["scenes"] == {}
    assert client.get(f"/api/scripts/{sid}").json()["elements"]["scenes"]["2"][0]["name"] == "Taxi"

    assert client.delete(f"/api/scripts/{sid}/schedule").json() == {"ok": True}
    assert client.get(f"/api/scripts/{sid}").json()["schedule"] is None
