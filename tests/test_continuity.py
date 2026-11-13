"""Days of the story, costume changes and continuity between scenes."""

import pytest

from slugline import continuity, parse
from slugline.breakdown import breakdown
from slugline.elements import Element, ElementSheet

SCRIPT = """Title: Week

INT. FLAT - NIGHT

ANNA
Can't sleep.

INT. FLAT - CONTINUOUS

BOB
Me neither.

INT. KITCHEN - MORNING

ANNA
Coffee?

EXT. STREET - DAY

ANNA
Bye.

INT. OFFICE - THE NEXT DAY

BOB
Late again.

EXT. PARK - THREE WEEKS LATER

SUPER: Summer.

ANNA
It's hot.

INT. FLAT - LATER

ANNA
Home.
"""


def test_suggested_story_days():
    play = parse(SCRIPT)
    days = continuity.story_days(play)
    # night 1, continuous, morning = day 2, same day, the next day, weeks later, later that day
    assert [days[s.number] for s in play.scenes] == [1, 1, 2, 2, 3, 4, 4]
    assert continuity.label(1, "NIGHT") == "N1" and continuity.label(2, "DAY") == "D2"


def test_a_day_set_by_hand_moves_the_scenes_after_it():
    play = parse(SCRIPT)
    days = continuity.story_days(play, {"3": 5})
    assert [days[s.number] for s in play.scenes] == [1, 1, 5, 5, 6, 7, 7]


def test_spanish_headings():
    play = parse("INT. CASA - NOCHE\n\nANA\nHola.\n\nINT. CASA - DÍA SIGUIENTE\n\nANA\nAdiós.\n\n"
                 "EXT. CALLE - DOS SEMANAS DESPUÉS\n\nANA\nVolví.\n")
    assert list(continuity.story_days(play).values()) == [1, 2, 3]


def test_costume_plot_and_continuity_warnings():
    play = parse(SCRIPT)
    days = continuity.story_days(play)
    rows = breakdown(play).scenes
    plot = {p.character: [(c.number, c.day, c.scenes) for c in p.changes] for p in continuity.costume_plot(rows, days)}
    assert plot["ANNA"] == [(1, 1, ["1"]), (2, 2, ["3", "4"]), (3, 4, ["6", "7"])]
    sheet = ElementSheet(scenes={
        "3": [Element("makeup", "Cut on the lip", "", "manual"), Element("makeup", "Makeup", "", "auto")],
        "6": [Element("wardrobe", "Red dress", "", "manual"), Element("wardrobe", "Coat", "", "auto")],
    })
    found = [(w.element, w.has, w.missing, w.day) for w in continuity.warnings(rows, sheet, days)]
    # The cut is in scene 3 (day 2): scene 4, later that day with Anna, doesn't have it.
    # The dress is in 6 (day 4): 7 is later that day. Generic or suggested costume is not followed.
    assert found == [("Cut on the lip", "3", "4", 2), ("Red dress", "6", "7", 4)]


def test_story_days_in_the_api_and_exports():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from slugline.server import create_app

    client = TestClient(create_app(), headers={"x-slugline": "1"})
    script = client.post("/api/scripts", params={"filename": "week.fountain"}, content=SCRIPT.encode()).json()
    sid = script["id"]
    assert [s["story_label"] for s in script["breakdown"]["scenes"]] == ["N1", "N1", "D2", "D2", "D3", "D4", "D4"]
    assert script["continuity"]["days"] == 4

    moved = client.put(f"/api/scripts/{sid}/corrections/story-day", json={"scene": "5", "day": 10}).json()
    assert [s["story_day"] for s in moved["breakdown"]["scenes"]][4:] == [10, 11, 11]
    assert moved["corrections"]["story_days"] == {"5": 10}
    assert client.put(f"/api/scripts/{sid}/corrections/story-day", json={"scene": "5", "day": 0}).status_code == 422
    back = client.put(f"/api/scripts/{sid}/corrections/story-day", json={"scene": "5", "day": None}).json()
    assert back["breakdown"]["scenes"][4]["story_day"] == 3

    plot = client.get(f"/api/scripts/{sid}/export/costume-plot.csv", params={"lang": "es"})
    assert plot.status_code == 200 and "Día de historia" in plot.text and "ANNA" in plot.text
    scenes = client.get(f"/api/scripts/{sid}/export/scenes.csv").text
    assert scenes.splitlines()[0].endswith("story_day") and ",N1" in scenes
