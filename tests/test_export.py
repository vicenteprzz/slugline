"""CSV and PDF exports, and the breakdown fields they are built from."""

import csv
import io

import pytest

from slugline import parse
from slugline.breakdown import breakdown
from slugline.cli import main
from slugline.export import characters_csv, locations_csv, report_pdf, scenes_csv, strip_color
from slugline.lint import lint
from slugline.llm import Analysis, SceneNote


@pytest.fixture(scope="module")
def result(example_text):
    return breakdown(parse(example_text))


def rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def test_day_night_groups_relative_times(result):
    assert result.day_night == {"NIGHT": 7, "DUSK": 4, "DAWN": 1, "DAY": 1}
    assert [s.day_night for s in result.scenes[1:4]] == ["DUSK", "DUSK", "DUSK"]  # SUNSET, CONTINUOUS, MOMENTS LATER


def test_characters_named_in_action_without_dialogue():
    play = parse(
        "INT. A - DAY\n\nANNA\nHi.\n\nBOB\nHi.\n\n"
        "INT. B - DAY\n\nBob waits by the door. A bob of the head.\n\nANNA\nStill here?\n\n"
        "INT. C - DAY\n\nanna is mentioned in lowercase only. Bobby is someone else.\n\nCARL\nYes.\n"
    )
    result = breakdown(play)
    assert [s.silent for s in result.scenes] == [[], ["BOB"], []]
    assert {c.name: c.silent_scenes for c in result.characters}["BOB"] == ["2"]


def test_scene_words_and_start_pages(result):
    first = result.scenes[0]
    assert first.start_page == 1.0
    assert first.words["BIG JOHN"] > first.words["MR. G"] > 0
    assert sum(sum(s.words.values()) for s in result.scenes) == sum(c.words for c in result.characters)
    pages = [s.start_page for s in result.scenes]
    assert pages == sorted(pages) and pages[-1] > 30


def test_scenes_csv(result):
    data = rows(scenes_csv(result))
    assert len(data) == 13
    assert data[1]["location"] == "MAIN STREET, OGALLALA"  # the comma survives quoting
    assert data[1]["day_night"] == "DUSK" and data[1]["length"] == "6/8"
    assert data[1]["silent_characters"] == "MR. D; MR. G"
    assert "summary" not in data[0]


def test_scenes_csv_with_analysis(result):
    analysis = Analysis(model="m", scenes=[SceneNote("2", "They ride in.", "tense", -1, 3)])
    data = rows(scenes_csv(result, analysis))
    assert (data[1]["summary"], data[1]["tone"], data[1]["valence"], data[1]["tension"]) == ("They ride in.", "tense", "-1", "3")
    assert data[0]["summary"] == ""


def test_characters_and_locations_csv(result):
    cast = rows(characters_csv(result))
    assert cast[0]["character"] == "MR. B" and cast[0]["scenes"] == "10"
    places = rows(locations_csv(result))
    assert places[0] == {"location": "BARN", "scenes": "6", "scene_list": "5; 6; 7; 8; 9; 10", "eighths": "148", "length": "18 4/8"}


def test_strip_colors_follow_the_stripboard_convention():
    assert strip_color("INT", "DAY") == "#ffffff"
    assert strip_color("EXT", "DAY") != strip_color("EXT", "NIGHT")
    assert strip_color("INT/EXT", "NIGHT") == strip_color("EXT", "NIGHT")
    assert strip_color(None, None) == "#eeeeee"


def test_report_pdf(result, example_text):
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")
    analysis = Analysis(model="m", logline="Four men and a barn.", scenes=[SceneNote("1", "John gives the job.", "menacing", -1, 3)])
    data = report_pdf(result, lint(parse(example_text)), analysis)
    assert data.startswith(b"%PDF")
    text = "\n".join(page.extract_text() for page in pypdf.PdfReader(io.BytesIO(data)).pages)
    for expected in ("John's Boys", "Stripboard", "BIG JOHN'S OFFICE", "Four men and a barn.", "John gives the job.", "Cast", "Locations"):
        assert expected in text


def test_cli_export(tmp_path, capsys):
    pytest.importorskip("reportlab")
    out = tmp_path / "out"
    assert main(["export", "examples/johns_boys.fountain", "--csv", str(out), "--pdf", str(out / "report.pdf")]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["characters.csv", "locations.csv", "report.pdf", "scenes.csv"]
    assert (out / "scenes.csv").read_bytes().startswith(b"\xef\xbb\xbf")  # BOM, for Excel


def test_cli_export_needs_a_target(capsys):
    assert main(["export", "examples/johns_boys.fountain"]) == 1
    assert "nothing to export" in capsys.readouterr().err


def test_cli_lint(capsys):
    assert main(["lint", "examples/johns_boys.fountain"]) == 0
    assert "No formatting issues" in capsys.readouterr().out
