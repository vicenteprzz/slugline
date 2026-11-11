"""Final Draft import, day out of days and call sheets."""

import csv
import io
import json

import pytest

from slugline import parse
from slugline.breakdown import breakdown
from slugline.elements import Element, ElementSheet
from slugline.fdx_import import fdx_to_fountain
from slugline.schedule import Schedule, ShootDay, day_out_of_days, set_days, to_payload

FDX = """<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<FinalDraft DocumentType="Script" Template="No" Version="5">
 <Content>
  <Paragraph Type="Scene Heading" Number="1"><Text>INT. KITCHEN - NIGHT</Text></Paragraph>
  <Paragraph Type="Action"><Text>ANNA pours </Text><Text Style="Bold">coffee</Text><Text>.</Text></Paragraph>
  <Paragraph Type="Action"><Text>KNOCK KNOCK</Text></Paragraph>
  <Paragraph Type="Character"><Text>ANNA</Text></Paragraph>
  <Paragraph Type="Parenthetical"><Text>quietly</Text></Paragraph>
  <Paragraph Type="Dialogue"><Text>You came back.</Text></Paragraph>
  <Paragraph Type="Character"><Text>McCLANE (V.O.)</Text></Paragraph>
  <Paragraph Type="Dialogue"><Text>Yippee.</Text></Paragraph>
  <DualDialogue>
   <Paragraph Type="Character"><Text>BOB</Text></Paragraph>
   <Paragraph Type="Dialogue"><Text>No.</Text></Paragraph>
   <Paragraph Type="Character"><Text>ANNA</Text></Paragraph>
   <Paragraph Type="Dialogue"><Text>Yes.</Text></Paragraph>
  </DualDialogue>
  <Paragraph Type="Transition"><Text>CUT TO:</Text></Paragraph>
  <Paragraph Type="Scene Heading" Number="2A"><Text>ext. street - later</Text></Paragraph>
  <Paragraph Type="Action"><Text>#3 is painted on the door.</Text></Paragraph>
  <Paragraph Type="Scene Heading"><Text>MONTAGE</Text></Paragraph>
  <Paragraph Type="Transition"><Text>Fade out.</Text></Paragraph>
 </Content>
 <TitlePage><Content>
  <Paragraph><Text>Two Rooms</Text></Paragraph>
  <Paragraph><Text>written by</Text></Paragraph>
  <Paragraph><Text>Ana Gil</Text></Paragraph>
 </Content></TitlePage>
</FinalDraft>
"""


# --- Final Draft ----------------------------------------------------------------

def test_fdx_becomes_a_parsed_screenplay():
    play = parse(fdx_to_fountain(FDX.encode()))
    assert play.title == "Two Rooms" and play.title_page["author"] == "Ana Gil"
    assert [(s.number, s.heading) for s in play.scenes] == [
        ("1", "INT. KITCHEN - NIGHT"), ("2A", "EXT. STREET - LATER"), ("3", "MONTAGE"),
    ]
    kitchen = play.scenes[0]
    assert kitchen.elements[0].text == "ANNA pours coffee."  # text runs joined
    assert kitchen.elements[1].text == "KNOCK KNOCK"  # all caps stays action, not a cue
    anna, mcclane, bob, anna_dual = kitchen.dialogues
    assert (anna.character, anna.parentheticals, anna.lines) == ("ANNA", ["(quietly)"], ["You came back."])
    assert (mcclane.character, mcclane.extensions) == ("McCLANE", ["V.O."])
    assert (bob.dual, anna_dual.dual) == (False, True)
    assert play.scenes[1].elements[0].text == "#3 is painted on the door."  # not read as a section


def test_fdx_from_a_path_and_bad_files(tmp_path):
    path = tmp_path / "two.fdx"
    path.write_text(FDX, encoding="utf-8")
    assert "INT. KITCHEN - NIGHT #1#" in fdx_to_fountain(path)
    for data, message in [(b"not xml", "Final Draft XML"), (b"<html><body/></html>", "not a Final Draft")]:
        with pytest.raises(RuntimeError, match=message):
            fdx_to_fountain(data)


def test_cli_and_api_read_fdx(tmp_path, capsys):
    from slugline.cli import main

    path = tmp_path / "two.fdx"
    path.write_text(FDX, encoding="utf-8")
    assert main([str(path)]) == 0
    assert "TWO ROOMS — 3 scenes" in capsys.readouterr().out

    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from slugline.server import create_app

    client = TestClient(create_app())
    ok = client.post("/api/scripts", params={"filename": "two.fdx"}, content=FDX.encode())
    assert ok.status_code == 200 and ok.json()["breakdown"]["title"] == "Two Rooms"
    bad = client.post("/api/scripts", params={"filename": "two.fdx"}, content=b"<html/>")
    assert bad.status_code == 422 and "Final Draft" in bad.json()["detail"]


# --- day out of days ------------------------------------------------------------

SCRIPT = """Title: Four Days

INT. A - DAY

ANNA
One.

INT. B - DAY

BOB
Two.

Anna waits by the door.

INT. C - NIGHT

CARL
Three.

INT. D - NIGHT

ANNA
Four.

BOB
Four.
"""


def test_day_out_of_days_codes():
    b = breakdown(parse(SCRIPT))
    plan = Schedule(days=[ShootDay(["1"]), ShootDay(["3"]), ShootDay(["2"]), ShootDay(["4"])], actors={"ANNA": "Ana Gil"})
    dood = {c.character: c for c in day_out_of_days(plan, b)}
    assert dood["ANNA"].codes == ["SW", "H", "W", "WF"]  # named in scene 2's action: on set that day
    assert (dood["ANNA"].work, dood["ANNA"].hold, dood["ANNA"].actor) == (3, 1, "Ana Gil")
    assert dood["BOB"].codes == ["", "", "SW", "WF"]
    assert dood["CARL"].codes == ["", "SWF", "", ""]
    assert [c.character for c in day_out_of_days(plan, b)] == ["ANNA", "CARL", "BOB"]  # by first day


def test_call_time_address_and_actors_are_validated():
    b = breakdown(parse(SCRIPT))
    plan = set_days(b, [{"scenes": ["1"], "call_time": "06:45", "address": "Calle Mayor 1"}], actors={"ANNA": " Ana Gil "})
    assert (plan.days[0].call_time, plan.days[0].address, plan.actors) == ("06:45", "Calle Mayor 1", {"ANNA": "Ana Gil"})
    assert to_payload(plan, b)["day_out_of_days"][0]["actor"] == "Ana Gil"
    # Actors are kept when they aren't sent again, and an empty name removes one.
    assert set_days(b, [{"scenes": []}], previous=plan).actors == {"ANNA": "Ana Gil"}
    assert set_days(b, [{"scenes": []}], previous=plan, actors={"ANNA": ""}).actors == {}
    for kwargs, message in [
        ({"days": [{"scenes": [], "call_time": "7am"}]}, "07:30"),
        ({"days": [{"scenes": [], "address": "x" * 301}]}, "too long"),
        ({"days": [], "actors": {"ZED": "Someone"}}, "not a character"),
    ]:
        with pytest.raises(ValueError, match=message):
            set_days(b, **kwargs)


# --- call sheets --------------------------------------------------------------

def test_call_sheets_pdf():
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")
    from slugline.export import call_sheets_pdf, day_out_of_days_csv

    b = breakdown(parse(SCRIPT))
    plan = Schedule(
        days=[ShootDay(["1", "2"], "2027-03-01", "Bring rain gear", call_time="07:00", address="Calle Mayor 1, Madrid"),
              ShootDay(["4"], "2027-03-02", call_time="18:00"), ShootDay(["3"])],
        actors={"ANNA": "Ana Gil"},
    )
    sheet = ElementSheet(scenes={"2": [Element("props", "Umbrella", "black")]})

    pages = pypdf.PdfReader(io.BytesIO(call_sheets_pdf(b, plan, sheet))).pages
    assert len(pages) == 3
    first = pages[0].extract_text()
    for expected in ("CALL SHEET", "1 of 3", "Mon 01 Mar 2027", "07:00", "Calle Mayor 1, Madrid", "Bring rain gear",
                     "INT. A - DAY", "Ana Gil", "SW", "Umbrella (2)", "Advance schedule · day 2", "call 18:00"):
        assert expected in first, expected
    assert "Advance schedule" not in pages[2].extract_text()  # the last day has nothing after it

    one = pypdf.PdfReader(io.BytesIO(call_sheets_pdf(b, plan, day=2))).pages
    assert len(one) == 1 and "2 of 3" in one[0].extract_text() and "On hold today" not in one[0].extract_text()
    with pytest.raises(ValueError, match="no day 7"):
        call_sheets_pdf(b, plan, day=7)

    rows = list(csv.reader(io.StringIO(day_out_of_days_csv(b, plan))))
    assert rows[0][:4] == ["character", "actor", "day 1 (2027-03-01)", "day 2 (2027-03-02)"]
    assert rows[1] == ["ANNA", "Ana Gil", "SW", "WF", "", "2", "0"]


def test_api_call_sheets_and_cast():
    pytest.importorskip("fastapi")
    pytest.importorskip("reportlab")
    from fastapi.testclient import TestClient

    from slugline.server import create_app

    client = TestClient(create_app())
    sid = client.post("/api/scripts", params={"filename": "four.fountain"}, content=SCRIPT.encode()).json()["id"]
    assert client.get(f"/api/scripts/{sid}/export/call-sheets.pdf").status_code == 404  # no schedule yet

    client.post(f"/api/scripts/{sid}/schedule", json={"pages_per_day": 1})
    days = [{"id": "a", "scenes": ["1", "2"], "call_time": "07:00", "address": "Base camp"}, {"id": "b", "scenes": ["3", "4"]}]
    saved = client.put(f"/api/scripts/{sid}/schedule", json={"days": days, "actors": {"BOB": "Bob Ross"}}).json()
    assert saved["days"][0]["call_time"] == "07:00" and saved["actors"] == {"BOB": "Bob Ross"}
    assert {c["character"]: c["actor"] for c in saved["day_out_of_days"]}["BOB"] == "Bob Ross"
    bad = client.put(f"/api/scripts/{sid}/schedule", json={"days": [{"scenes": [], "call_time": "noon"}]})
    assert bad.status_code == 422

    # A new suggested plan keeps the cast list.
    replanned = client.post(f"/api/scripts/{sid}/schedule", json={"pages_per_day": 2}).json()
    assert replanned["actors"] == {"BOB": "Bob Ross"}

    one = client.get(f"/api/scripts/{sid}/export/call-sheets.pdf", params={"day": 1})
    assert one.status_code == 200 and 'filename="four-call-sheet-day-1.pdf"' in one.headers["content-disposition"]
    assert client.get(f"/api/scripts/{sid}/export/call-sheets.pdf", params={"day": 99}).status_code == 404
    dood = client.get(f"/api/scripts/{sid}/export/day-out-of-days.csv")
    assert dood.status_code == 200 and "Bob Ross" in dood.text


def test_assistant_sees_call_times_and_day_out_of_days():
    from slugline.agent import ScriptAgent

    plan = Schedule(days=[ShootDay(["1"], call_time="06:00", address="Base camp"), ShootDay(["4"])], actors={"ANNA": "Ana Gil"})
    agent = ScriptAgent(SCRIPT, schedule=lambda: plan, elements=lambda: None)
    data = json.loads(agent.run_tool("shooting_schedule", {})[0])
    assert data["days"][0]["call_time"] == "06:00" and data["days"][0]["meeting_point"] == "Base camp"
    anna = next(c for c in data["day_out_of_days"]["cast"] if c["character"] == "ANNA")
    assert anna == {"character": "ANNA", "actor": "Ana Gil", "work_days": 2, "hold_days": 0, "by_day": {"1": "SW", "2": "WF"}}


def test_cli_prints_day_out_of_days_and_writes_call_sheets(tmp_path, capsys):
    pytest.importorskip("reportlab")
    from slugline.cli import main

    path = tmp_path / "four.fountain"
    path.write_text(SCRIPT, encoding="utf-8")
    sheets = tmp_path / "calls.pdf"
    assert main(["schedule", str(path), "--pages", "1", "--call-sheets", str(sheets)]) == 0
    out = capsys.readouterr().out
    assert "DAY OUT OF DAYS" in out and "ANNA" in out
    assert sheets.read_bytes().startswith(b"%PDF")
