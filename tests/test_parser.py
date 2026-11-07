from pathlib import Path

import pytest

from slugline import Action, Dialogue, Transition, parse, parse_file
from slugline.parser import format_eighths, parse_heading

EXAMPLE = Path(__file__).parent.parent / "examples" / "dust_and_iron.fountain"


@pytest.fixture(scope="module")
def play():
    return parse_file(EXAMPLE)


@pytest.mark.parametrize(
    "heading, expected",
    [
        ("INT. SALOON - NIGHT", ("INT", "SALOON", "NIGHT")),
        ("EXT. SILVER CREEK - MAIN STREET - DAY", ("EXT", "SILVER CREEK - MAIN STREET", "DAY")),
        ("INT./EXT. RUTH'S WAGON - NIGHT", ("INT/EXT", "RUTH'S WAGON", "NIGHT")),
        ("I/E CAR - MOVING - day", ("INT/EXT", "CAR - MOVING", "DAY")),
        ("EXT. DESERT", ("EXT", "DESERT", None)),
        ("FLASHBACK - THE RANCH FIRE", (None, "FLASHBACK", "THE RANCH FIRE")),
    ],
)
def test_parse_heading(heading, expected):
    assert parse_heading(heading) == expected


def test_title_page(play):
    assert play.title == "Dust and Iron"
    assert play.title_page["author"] == "Vicente Pérez"
    assert "Sample script" in play.title_page["notes"]


def test_scene_count_and_numbers(play):
    # 5 regular scenes + 1 forced heading (.FLASHBACK), inserted as 3A
    assert len(play.scenes) == 6
    assert [s.number for s in play.scenes] == ["1", "2", "3", "3A", "4", "5"]


def test_unnumbered_scenes_fall_back_to_position():
    play = parse("INT. A - DAY\n\nX.\n\nEXT. B - NIGHT\n\nY.\n")
    assert [s.scene_number for s in play.scenes] == [None, None]
    assert [s.number for s in play.scenes] == ["1", "2"]


def test_forced_scene_heading(play):
    flashback = play.scenes[3]
    assert flashback.heading == "FLASHBACK - THE RANCH FIRE"
    assert flashback.int_ext is None


def test_character_extensions_are_not_part_of_the_name(play):
    street = play.scenes[1]
    names = [d.character for d in street.dialogues]
    assert names == ["ELI", "RUTH", "ELI", "RUTH"]
    assert street.dialogues[0].extensions == ["V.O."]
    assert street.dialogues[3].extensions == ["CONT'D"]


def test_parenthetical_is_separated_from_dialogue(play):
    line = play.scenes[0].dialogues[1]
    assert line.character == "RUTH"
    assert line.parentheticals == ["(not looking at him)"]
    assert line.lines == ["Far enough that you stop asking."]


def test_forced_character_keeps_mixed_case(play):
    wagon = play.scenes[4]
    assert wagon.characters == ["McCALLISTER"]
    assert wagon.dialogues[0].extensions == ["O.S."]


def test_dual_dialogue(play):
    sheriff_lines = [d for d in play.scenes[2].dialogues if d.character == "SHERIFF"]
    assert [d.dual for d in sheriff_lines] == [False, True]


def test_notes_and_boneyard_are_removed(play):
    all_text = " ".join(
        e.text for s in play.scenes for e in s.elements if isinstance(e, (Action, Dialogue))
    )
    assert "vultures" not in all_text
    assert "Then you know why I came" not in all_text


def test_transitions(play):
    assert isinstance(play.scenes[1].elements[-1], Transition)
    assert play.scenes[1].elements[-1].text == "CUT TO:"
    last = play.scenes[-1].elements
    assert Transition("FADE OUT.") in last
    # >THE END< is centered action, not a transition
    assert Action(">THE END<") in last


def test_forced_action_is_not_a_character(play):
    first = play.scenes[-1].elements[0]
    assert first == Action("THE STREET IS EMPTY.")


def test_sections_and_synopses_are_skipped(play):
    assert play.preamble == []


def test_uppercase_action_followed_by_blank_is_action():
    play = parse("INT. ROOM - DAY\n\nBANG!\n\nNothing moves.\n")
    assert play.scenes[0].elements == [Action("BANG!"), Action("Nothing moves.")]
    assert play.scenes[0].dialogues == []


def test_heading_needs_blank_line_before():
    play = parse("INT. ROOM - DAY\n\nShe reads the sign:\nEXT. NOT A HEADING\n")
    assert len(play.scenes) == 1


@pytest.mark.parametrize("eighths, text", [(1, "1/8"), (8, "1"), (11, "1 3/8"), (16, "2")])
def test_format_eighths(eighths, text):
    assert format_eighths(eighths) == text


def test_every_scene_is_at_least_one_eighth(play):
    assert all(s.eighths >= 1 for s in play.scenes)
