"""Production elements: the sheet model, AI extraction, editing, exports, CLI and API."""

import csv
import io
import json

import pytest

from slugline import parse
from slugline.breakdown import breakdown
from slugline.elements import (
    CATEGORY_KEYS,
    Element,
    ElementSheet,
    load_sheet,
    merge_extraction,
    save_sheet,
    to_payload,
    totals,
    update_scene,
)
from slugline.export import breakdown_sheets_pdf, elements_csv, write_csv

SCRIPT = """Title: Two Rooms

INT. KITCHEN - NIGHT

ANNA pours coffee. Bob watches the door.

ANNA
You came back.

EXT. STREET - LATER

Bob hails a taxi in the rain.

BOB
Taxi!
"""


def ai(category, name, notes=""):
    return Element(category, name, notes, "ai")


def manual(category, name, notes=""):
    return Element(category, name, notes, "manual")


# --- the sheet --------------------------------------------------------------

def test_merge_keeps_hand_edits_and_respects_removals():
    sheet = ElementSheet(
        scenes={"1": [ai("props", "Mug"), manual("props", "Kettle"), ai("set_dressing", "Clock")]},
        dismissed={"1": ["props|coffee pot"]},
    )
    found = {
        "1": [ai("props", "mug"), ai("props", "Coffee pot"), ai("props", "Kettle", "steaming"), ai("sound", "Rain")],
        "2": [ai("vehicles", "Taxi"), ai("vehicles", "Taxi")],
    }
    merged = merge_extraction(sheet, found, "claude-opus-5-5")

    assert [(e.name, e.source) for e in merged.for_scene("1")] == [
        ("Kettle", "manual"),  # hand edit kept; the suggestion with the same name doesn't duplicate it
        ("mug", "ai"),  # old suggestions are replaced by the new ones
        ("Rain", "ai"),  # sorted into category order: props before sound
    ]
    assert "Clock" not in [e.name for e in merged.for_scene("1")]
    assert [e.name for e in merged.for_scene("2")] == ["Taxi"]
    assert merged.model == "claude-opus-5-5" and merged.dismissed == {"1": ["props|coffee pot"]}


def test_update_scene_tracks_what_changed():
    sheet = ElementSheet(scenes={"1": [ai("props", "Mug"), ai("props", "Spoon"), ai("sound", "Rain", "heavy")]})
    update_scene(sheet, "1", [
        {"category": "props", "name": "Mug", "notes": ""},  # untouched suggestion
        {"category": "sound", "name": "Rain", "notes": "light"},  # edited suggestion
        {"category": "wardrobe", "name": "  Wet   coat ", "notes": ""},  # new, with messy spacing
    ])
    assert [(e.category, e.name, e.notes, e.source) for e in sheet.for_scene("1")] == [
        ("props", "Mug", "", "ai"),
        ("wardrobe", "Wet coat", "", "manual"),
        ("sound", "Rain", "light", "manual"),
    ]
    assert sheet.dismissed == {"1": ["props|spoon"]}

    # Adding a dismissed element back by hand un-dismisses it.
    update_scene(sheet, "1", [{"category": "props", "name": "SPOON", "notes": ""}])
    assert sheet.dismissed == {"1": ["props|mug"]}


@pytest.mark.parametrize(
    "item, message",
    [
        ({"category": "catering", "name": "Sandwiches"}, "Unknown category"),
        ({"category": "props", "name": "   "}, "needs a name"),
        ({"category": "props", "name": "x" * 121}, "120 characters"),
        ({"category": "props", "name": "Mug", "notes": "n" * 301}, "300 characters"),
    ],
)
def test_update_scene_rejects_bad_elements(item, message):
    with pytest.raises(ValueError, match=message):
        update_scene(None, "1", [item])


def test_totals_count_each_element_once_per_scene():
    b = breakdown(parse(SCRIPT))
    sheet = ElementSheet(scenes={
        "1": [ai("props", "Mug"), ai("sound", "Rain")],
        "2": [ai("sound", "rain", "heavier"), ai("vehicles", "Taxi")],
    })
    rows = [(t.category, t.name, t.scenes, t.eighths) for t in totals(sheet, b)]
    lengths = {s.number: s.eighths for s in b.scenes}
    assert rows == [
        ("props", "Mug", ["1"], lengths["1"]),
        ("vehicles", "Taxi", ["2"], lengths["2"]),
        ("sound", "Rain", ["1", "2"], lengths["1"] + lengths["2"]),
    ]
    payload = to_payload(sheet, b)
    assert payload["totals"][0]["name"] == "Mug" and payload["scenes"]["2"][1]["name"] == "Taxi"
    assert to_payload(None, b) is None


def test_sheets_are_saved_by_script_content():
    assert load_sheet(SCRIPT) is None
    sheet = ElementSheet(scenes={"1": [manual("props", "Mug")]}, dismissed={"2": ["vehicles|taxi"]}, model="m")
    save_sheet(SCRIPT, sheet)
    assert load_sheet(SCRIPT) == sheet
    assert load_sheet(SCRIPT.replace("\n", "\r\n")) == sheet  # same script, other line endings
    assert load_sheet(SCRIPT + "\nMore.\n") is None


# --- exports ----------------------------------------------------------------

def test_elements_csv_and_write_csv(tmp_path):
    b = breakdown(parse(SCRIPT))
    sheet = ElementSheet(scenes={"2": [ai("vehicles", "Taxi", "yellow"), manual("sfx", "Rain")]})
    rows = list(csv.DictReader(io.StringIO(elements_csv(b, sheet))))
    assert rows == [
        {"scene": "2", "heading": "EXT. STREET - LATER", "department": "Vehicles", "element": "Taxi", "notes": "yellow", "source": "suggested"},
        {"scene": "2", "heading": "EXT. STREET - LATER", "department": "Special effects", "element": "Rain", "notes": "", "source": "manual"},
    ]
    names = sorted(p.name for p in write_csv(b, tmp_path, elements=sheet))
    assert names == ["characters.csv", "elements.csv", "locations.csv", "scenes.csv"]
    assert "elements.csv" not in [p.name for p in write_csv(b, tmp_path / "empty", elements=ElementSheet())]


def test_breakdown_sheets_pdf():
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")
    b = breakdown(parse(SCRIPT))
    sheet = ElementSheet(scenes={"2": [ai("vehicles", "Taxi", "yellow")]})
    pages = pypdf.PdfReader(io.BytesIO(breakdown_sheets_pdf(b, sheet))).pages
    assert len(pages) == 2  # one sheet per scene
    first, second = (p.extract_text() for p in pages)
    assert "INT. KITCHEN - NIGHT" in first and "Taxi" not in first
    assert "EXT. STREET - LATER" in second and "Taxi" in second and "yellow" in second
    for heading in ("CAST", "PROPS", "VEHICLES", "SPECIAL EFFECTS", "PRODUCTION NOTES"):
        assert heading in second
    assert "No lines: ANNA" not in second and "BOB" in second
    # Without elements it still prints blank sheets to fill in by hand.
    assert len(pypdf.PdfReader(io.BytesIO(breakdown_sheets_pdf(b))).pages) == 2


# --- AI extraction ----------------------------------------------------------

pytest.importorskip("anthropic")

from fake_api import FakeAPI, text  # noqa: E402

from slugline import llm  # noqa: E402


def elements_reply(scenes: dict[str, list[tuple[str, str, str]]]) -> list[dict]:
    return [text(json.dumps({"scenes": [
        {"number": n, "elements": [{"category": c, "name": name, "notes": notes} for c, name, notes in items]}
        for n, items in scenes.items()
    ]}))]


def test_extract_elements_request_and_result():
    api = FakeAPI(elements_reply({
        "1": [("props", "Coffee mug", ""), ("catering", "Bagels", ""), ("props", " ", "")],
        "2": [("vehicles", "Taxi", "yellow"), ("sfx", "Rain", "rain towers")],
        "9": [("props", "Ghost prop", "")],
    }))
    found = llm.extract_elements(SCRIPT, client=api.client)

    assert {n: [(e.category, e.name, e.notes, e.source) for e in items] for n, items in found.items()} == {
        "1": [("props", "Coffee mug", "", "ai")],  # unknown categories and empty names dropped
        "2": [("vehicles", "Taxi", "yellow", "ai"), ("sfx", "Rain", "rain towers", "ai")],
    }
    request = api.requests[0]
    schema = request["output_config"]["format"]["schema"]
    item = schema["properties"]["scenes"]["items"]["properties"]["elements"]["items"]
    assert item["properties"]["category"]["enum"] == CATEGORY_KEYS
    assert "scenes 1, 2" in request["messages"][0]["content"]
    assert request["system"][-1]["cache_control"] == {"type": "ephemeral"}


def test_later_batches_reuse_earlier_names(monkeypatch):
    monkeypatch.setattr(llm, "SCENES_PER_REQUEST", 1)
    api = FakeAPI(
        elements_reply({"1": [("props", "Coffee mug", "")]}),
        elements_reply({"2": [("props", "Coffee mug", "empty")]}),
    )
    llm.extract_elements(SCRIPT, client=api.client)
    assert "Names already used" not in api.requests[0]["messages"][0]["content"]
    assert "Coffee mug (props)" in api.requests[1]["messages"][0]["content"]


def test_break_down_elements_merges_with_the_saved_sheet():
    save_sheet(SCRIPT, ElementSheet(scenes={"2": [manual("wardrobe", "Raincoat")]}, dismissed={"2": ["vehicles|taxi"]}))
    api = FakeAPI(elements_reply({"2": [("vehicles", "Taxi", ""), ("sfx", "Rain", "")]}))
    sheet = llm.break_down_elements(SCRIPT, client=api.client)
    assert [(e.name, e.source) for e in sheet.for_scene("2")] == [("Raincoat", "manual"), ("Rain", "ai")]
    assert load_sheet(SCRIPT) == sheet and sheet.model == "claude-opus-5-5"


# --- assistant, CLI and API -------------------------------------------------

def test_assistant_reads_the_live_sheet():
    from slugline.agent import ScriptAgent

    current = {"sheet": None}
    agent = ScriptAgent(SCRIPT, elements=lambda: current["sheet"])
    assert "No elements" in json.loads(agent.run_tool("list_elements", {"scene": ""})[0])["note"]

    current["sheet"] = ElementSheet(scenes={"1": [ai("props", "Mug")], "2": [ai("props", "mug", "chipped")]})
    everything = json.loads(agent.run_tool("list_elements", {"scene": ""})[0])
    assert everything == [{"department": "Props", "element": "Mug", "scenes": ["1", "2"], "eighths": everything[0]["eighths"]}]
    assert json.loads(agent.run_tool("list_elements", {"scene": "2"})[0]) == [
        {"department": "Props", "element": "mug", "notes": "chipped"}
    ]
    assert agent.run_tool("list_elements", {"scene": "7"})[1] is True


def test_cli_elements(tmp_path, monkeypatch, capsys):
    from slugline.cli import main

    path = tmp_path / "two_rooms.fountain"
    path.write_text(SCRIPT, encoding="utf-8")
    api = FakeAPI(elements_reply({"2": [("vehicles", "Taxi", "yellow")]}))
    monkeypatch.setattr(llm, "make_client", lambda: api.client)

    assert main(["elements", str(path)]) == 0
    out = capsys.readouterr().out
    assert "2. EXT. STREET - LATER" in out and "Vehicles: Taxi (yellow)" in out and "Suggested by Claude" in out

    assert main(["elements", str(path), "--json"]) == 0  # the saved sheet: no new request
    assert json.loads(capsys.readouterr().out)["totals"][0]["name"] == "Taxi"
    assert len(api.requests) == 1

    out_dir = tmp_path / "out"
    pytest.importorskip("reportlab")
    assert main(["export", str(path), "--csv", str(out_dir), "--sheets", str(out_dir / "sheets.pdf")]) == 0
    assert (out_dir / "elements.csv").exists() and (out_dir / "sheets.pdf").read_bytes().startswith(b"%PDF")


def test_api_extract_edit_and_export(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from slugline.server import create_app

    client = TestClient(create_app(), headers={"x-slugline": "1"})
    api = FakeAPI(elements_reply({"1": [("props", "Mug", "")], "2": [("vehicles", "Taxi", "")]}))
    monkeypatch.setattr(llm, "make_client", lambda: api.client)

    status = client.get("/api/status").json()
    assert [c["key"] for c in status["categories"]] == CATEGORY_KEYS
    script = client.post("/api/scripts", params={"filename": "two.fountain"}, content=SCRIPT.encode()).json()
    assert script["elements"] is None
    sid = script["id"]
    assert client.get(f"/api/scripts/{sid}/export/elements.csv").status_code == 404

    extracted = client.post(f"/api/scripts/{sid}/elements").json()
    assert [t["name"] for t in extracted["totals"]] == ["Mug", "Taxi"]

    edited = client.put(f"/api/scripts/{sid}/elements/2", json={"elements": [
        {"category": "vehicles", "name": "Taxi", "notes": ""},
        {"category": "sfx", "name": "Rain", "notes": "rain towers"},
    ]}).json()
    assert [(e["name"], e["source"]) for e in edited["scenes"]["2"]] == [("Taxi", "ai"), ("Rain", "manual")]
    assert client.get(f"/api/scripts/{sid}").json()["elements"] == edited

    bad = client.put(f"/api/scripts/{sid}/elements/2", json={"elements": [{"category": "catering", "name": "Bagels"}]})
    assert bad.status_code == 422 and "Unknown category" in bad.json()["detail"]
    assert client.put(f"/api/scripts/{sid}/elements/77", json={"elements": []}).status_code == 404

    assert "Rain" in client.get(f"/api/scripts/{sid}/export/elements.csv").text
    # A fresh upload of the same script finds the saved, edited breakdown.
    again = client.post("/api/scripts", params={"filename": "two.fountain"}, content=SCRIPT.encode()).json()
    assert again["elements"] == edited

    pytest.importorskip("reportlab")
    sheets = client.get(f"/api/scripts/{sid}/export/breakdown-sheets.pdf")
    assert sheets.headers["content-type"] == "application/pdf"
    assert 'filename="two-breakdown-sheets.pdf"' in sheets.headers["content-disposition"]


def test_api_extract_without_credentials_is_a_502():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from slugline.server import create_app

    client = TestClient(create_app(), headers={"x-slugline": "1"})
    sid = client.post("/api/scripts", params={"filename": "two.fountain"}, content=SCRIPT.encode()).json()["id"]
    response = client.post(f"/api/scripts/{sid}/elements")
    assert response.status_code == 502 and "ANTHROPIC_API_KEY" in response.json()["detail"]
    # Editing by hand still works without any AI.
    ok = client.put(f"/api/scripts/{sid}/elements/1", json={"elements": [{"category": "props", "name": "Mug"}]})
    assert ok.status_code == 200 and ok.json()["totals"][0]["name"] == "Mug"
