"""End-to-end checks on a real script: John's Boys (western short, 34 pages)."""

import json
from pathlib import Path

import pytest

from slugline.breakdown import breakdown, render_text
from slugline.cli import main
from slugline.parser import parse_file

EXAMPLE = Path(__file__).parent.parent / "examples" / "johns_boys.fountain"


@pytest.fixture(scope="module")
def play():
    return parse_file(EXAMPLE)


@pytest.fixture(scope="module")
def result(play):
    return breakdown(play)


def test_title_page(play):
    assert play.title == "John's Boys"
    assert play.title_page["author"] == "Vicente Pérez Pourtau"


def test_scenes(result):
    assert result.scene_count == 13
    assert result.scenes[0].heading == "INT. BIG JOHN'S OFFICE - NIGHT"
    assert result.scenes[-1].heading == "INT. BIG JOHN'S OFFICE - NIGHT"
    assert result.int_ext == {"INT": 9, "EXT": 4}


def test_intercut_is_not_a_new_scene(play):
    barn_sunrise = play.scenes[9]
    assert barn_sunrise.heading == "INT. BARN - SUNRISE"
    assert any("INTERCUT" in getattr(e, "text", "") for e in barn_sunrise.elements)


def test_cast(result):
    names = {c.name for c in result.characters}
    assert names == {
        "MR. B", "MR. X", "MR. D", "MR. G", "BIG JOHN", "MAN 1", "MAN 2",
        "SHERIFF", "SHERIFF'S DEPUTY", "BARTENDER #1", "BARTENDER #2", "BILLY'S FATHER",
    }
    # Mr. B is the lead: most words, in most scenes.
    assert result.characters[0].name == "MR. B"
    assert len(result.characters[0].scenes) == 10


def test_voice_over_counts_as_the_same_character(play):
    vo = [d for s in play.scenes for d in s.dialogues if "V.O." in d.extensions]
    assert {d.character for d in vo} == {"MR. X", "MR. B"}


def test_barn_is_the_main_location(result):
    barn = result.locations[0]
    assert barn.location == "BARN"
    assert barn.scenes == ["5", "6", "7", "8", "9", "10"]


def test_page_estimate_is_close_to_the_real_length(result):
    # The PDF has 34 pages of script; the estimate should be within ~10%.
    assert 30 <= result.page_count <= 38


def test_render_text_contains_sections(result):
    out = render_text(result)
    assert out.startswith("JOHN'S BOYS")
    for section in ("SCENES", "CHARACTERS", "LOCATIONS"):
        assert section in out


def test_cli_json(capsys):
    assert main([str(EXAMPLE), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["title"] == "John's Boys"
    assert len(data["scenes"]) == 13


def test_cli_missing_file(capsys):
    assert main(["does_not_exist.fountain"]) == 1
    assert "cannot read" in capsys.readouterr().err
