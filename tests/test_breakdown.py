import json
from pathlib import Path

from slugline.breakdown import breakdown, render_text
from slugline.cli import main
from slugline.parser import parse_file

EXAMPLE = Path(__file__).parent.parent / "examples" / "dust_and_iron.fountain"


def test_character_stats():
    b = breakdown(parse_file(EXAMPLE))
    by_name = {c.name: c for c in b.characters}
    assert set(by_name) == {"RUTH", "ELI", "SHERIFF", "McCALLISTER"}
    assert by_name["RUTH"].scenes == ["1", "2", "3"]
    assert by_name["ELI"].dialogue_blocks == 3
    assert by_name["SHERIFF"].words == len("We don't serve your kind here. Everybody knows your kind.".split())


def test_location_stats_group_repeated_locations():
    b = breakdown(parse_file(EXAMPLE))
    main_street = next(loc for loc in b.locations if loc.location == "SILVER CREEK - MAIN STREET")
    assert main_street.scenes == ["2", "5"]


def test_summary_counts():
    b = breakdown(parse_file(EXAMPLE))
    assert b.scene_count == 6
    assert b.int_ext == {"EXT": 3, "INT": 1, "?": 1, "INT/EXT": 1}
    assert b.time_of_day["NIGHT"] == 2


def test_render_text_contains_sections():
    out = render_text(breakdown(parse_file(EXAMPLE)))
    assert out.startswith("DUST AND IRON")
    for section in ("SCENES", "CHARACTERS", "LOCATIONS"):
        assert section in out


def test_cli_json(capsys):
    assert main([str(EXAMPLE), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["title"] == "Dust and Iron"
    assert len(data["scenes"]) == 6


def test_cli_missing_file(capsys):
    assert main(["does_not_exist.fountain"]) == 1
    assert "cannot read" in capsys.readouterr().err
