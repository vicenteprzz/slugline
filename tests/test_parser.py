"""Fountain syntax rules, tested on small inline snippets."""

import pytest

from slugline import Action, Dialogue, Transition, parse
from slugline.parser import format_eighths, parse_heading


@pytest.mark.parametrize(
    "heading, expected",
    [
        ("INT. BARN - NIGHT", ("INT", "BARN", "NIGHT")),
        ("EXT. BRIGHTON RANCH - FRONT DOOR - DAY", ("EXT", "BRIGHTON RANCH - FRONT DOOR", "DAY")),
        ("EXT. ALLEY, OGALLALA - MOMENTS LATER", ("EXT", "ALLEY, OGALLALA", "MOMENTS LATER")),
        ("INT./EXT. WAGON - NIGHT", ("INT/EXT", "WAGON", "NIGHT")),
        ("I/E CAR - MOVING - day", ("INT/EXT", "CAR - MOVING", "DAY")),
        ("EXT. DESERT", ("EXT", "DESERT", None)),
    ],
)
def test_parse_heading(heading, expected):
    assert parse_heading(heading) == expected


def test_title_page_with_multiline_value():
    play = parse("Title: John's Boys\nAuthor: V. P.\nNotes:\n\tFirst draft.\n\tWestern.\n\nINT. A - DAY\n")
    assert play.title == "John's Boys"
    assert play.title_page["notes"] == "First draft.\nWestern."
    assert len(play.scenes) == 1


def test_scene_numbers_and_forced_heading():
    play = parse("INT. A - DAY #1#\n\nX.\n\n.FLASHBACK #1A#\n\nY.\n\nEXT. B - NIGHT\n\nZ.\n")
    assert [s.number for s in play.scenes] == ["1", "1A", "3"]
    assert play.scenes[1].heading == "FLASHBACK"
    # No INT./EXT. and no time: another shot in the same place as the scene before.
    assert (play.scenes[1].int_ext, play.scenes[1].location, play.scenes[1].continues) == ("INT", "A", True)
    assert not play.scenes[2].continues


def test_shot_descriptions_are_not_part_of_the_location():
    play = parse(
        "EXT. BODEGA - MOVING POV TOWARD THE WINDOW - NIGHT\n\nA.\n\n"
        "EXT. ROOFTOP - ON THE RUSTED SEARCHLIGHT - NIGHT\n\nB.\n\n"
        "INT. RANCH - CORRAL - DAY\n\nC.\n\nEXT. BODEGA - NIGHT\n\nD.\n"
    )
    assert [s.location for s in play.scenes] == ["BODEGA", "ROOFTOP", "RANCH - CORRAL", "BODEGA"]
    assert play.scenes[0].heading == "EXT. BODEGA - MOVING POV TOWARD THE WINDOW - NIGHT"


def test_extensions_are_not_part_of_the_name():
    play = parse("INT. A - DAY\n\nMR. X (V.O.) (CONT'D)\nI ran.\n")
    d = play.scenes[0].dialogues[0]
    assert d.character == "MR. X"
    assert d.extensions == ["V.O.", "CONT'D"]


def test_parenthetical_is_separated_from_dialogue():
    play = parse("INT. A - DAY\n\nMR. B\n(not looking at him)\nEasy, kid.\n")
    d = play.scenes[0].dialogues[0]
    assert d.parentheticals == ["(not looking at him)"]
    assert d.lines == ["Easy, kid."]


def test_forced_character_keeps_mixed_case():
    play = parse("INT. A - DAY\n\n@McCALLISTER (O.S.)\nCount them twice.\n")
    assert play.scenes[0].characters == ["McCALLISTER"]


def test_dual_dialogue():
    play = parse("INT. A - DAY\n\nMR. B\nNo.\n\nMR. D ^\nYes.\n")
    assert [d.dual for d in play.scenes[0].dialogues] == [False, True]


def test_notes_and_boneyard_are_removed():
    play = parse("INT. A - DAY\n\nHe waits. [[add vultures]]\n\n/* MR. B\nCut line.\n*/\n\nShe leaves.\n")
    assert play.scenes[0].elements == [Action("He waits."), Action("She leaves.")]


def test_transitions_and_centered_text():
    play = parse("INT. A - DAY\n\nX.\n\nCUT TO:\n\n> FADE OUT.\n\n>THE END<\n")
    assert play.scenes[0].elements[1:] == [
        Transition("CUT TO:"),
        Transition("FADE OUT."),
        Action("THE END"),  # centered: the > < markers are not printed
    ]


def test_forced_action_is_not_a_character():
    play = parse("INT. A - DAY\n\n!KNOCK KNOCK\nThe door opens.\n")
    assert play.scenes[0].elements == [Action("KNOCK KNOCK\nThe door opens.")]


def test_sections_and_synopses_are_skipped():
    play = parse("# ACT ONE\n\n= They meet.\n\nINT. A - DAY\n\nX.\n")
    assert play.preamble == []


def test_uppercase_action_followed_by_blank_is_action():
    play = parse("INT. ROOM - DAY\n\nBANG\n\nNothing moves.\n")
    assert play.scenes[0].elements == [Action("BANG"), Action("Nothing moves.")]
    assert play.scenes[0].dialogues == []


def test_heading_needs_blank_line_before():
    play = parse("INT. ROOM - DAY\n\nShe reads the sign:\nEXT. NOT A HEADING\n")
    assert len(play.scenes) == 1


def test_unnumbered_scenes_fall_back_to_position():
    play = parse("INT. A - DAY\n\nX.\n\nEXT. B - NIGHT\n\nY.\n")
    assert [s.number for s in play.scenes] == ["1", "2"]


def test_dialogue_word_count():
    assert Dialogue("A", lines=["I ran...", "and I didn't look back."]).word_count == 7


@pytest.mark.parametrize("eighths, text", [(1, "1/8"), (8, "1"), (11, "1 3/8"), (16, "2")])
def test_format_eighths(eighths, text):
    assert format_eighths(eighths) == text


def test_fade_in_is_not_a_title_page():
    play = parse("FADE IN:\n\nINT. A - DAY\n\nX.\n")
    assert play.title_page == {}
    assert play.preamble == [Action("FADE IN:")]
    assert len(play.scenes) == 1


def test_bom_and_old_mac_line_endings():
    play = parse("\ufeffTitle: X\r\rINT. A - DAY\r\rBOB\rHi.\r")
    assert play.title == "X"
    assert play.scenes[0].characters == ["BOB"]


def test_last_dash_part_is_only_a_time_if_it_reads_like_one():
    assert parse_heading("EXT. RANCH - CORRAL") == ("EXT", "RANCH - CORRAL", None)
    assert parse_heading("INT. BAR - 3 AM") == ("INT", "BAR", "3 AM")
    assert parse_heading("INT. BARN - A FEW MINUTES LATER") == ("INT", "BARN", "A FEW MINUTES LATER")


def test_day_night_is_inherited_by_relative_times():
    play = parse(
        "EXT. A - SUNSET\n\nX.\n\nEXT. B - CONTINUOUS\n\nX.\n\n"
        "INT. C - NIGHT\n\nX.\n\nINT. C - LATER\n\nX.\n\nEXT. D - THE NEXT MORNING\n\nX.\n"
    )
    assert [s.day_night for s in play.scenes] == ["DUSK", "DUSK", "NIGHT", "NIGHT", "DAY"]


def test_emphasis_markers_are_not_printed():
    play = parse("INT. A - DAY\n\nBOB\n*Really* _now_, **ok** and \\*literal\\*.\n\nHe ***runs***.\n")
    scene = play.scenes[0]
    assert scene.dialogues[0].lines == ["Really now, ok and *literal*."]
    assert scene.elements[1] == Action("He runs.")


def test_scene_line_numbers_survive_notes_and_boneyard():
    play = parse("Title: X\n\n/* cut\nthis */\n\nINT. A - DAY\n\nX. [[a\nnote]]\n\nEXT. B - DAY\n\nY.\n")
    assert [s.line for s in play.scenes] == [6, 11]


def test_relative_times_and_typos_inherit_day_or_night():
    play = parse(
        "INT. CLUB - NIGHT\n\nA.\n\nINT. HALLWAY - SOON\n\nB.\n\nINT. ROOM 503 - AFTER\n\nC.\n\n"
        "INT. KAISER - CONTINIOUS\n\nD.\n\nEXT. FARM - LATE AFTEROON\n\nE.\n\n"
        "INT. LAWRENCE’S PARLOR - LATERN\n\nF.\n\nEXT. CONTINENTAL HOTEL\n\nG.\n"
    )
    assert [s.location for s in play.scenes] == [
        "CLUB", "HALLWAY", "ROOM 503", "KAISER", "FARM", "LAWRENCE'S PARLOR", "CONTINENTAL HOTEL"]
    assert [s.day_night for s in play.scenes] == ["NIGHT", "NIGHT", "NIGHT", "NIGHT", "DAY", "DAY", "DAY"]


def test_every_scene_gets_its_own_number():
    play = parse(
        "INT. A - DAY #1#\n\nA.\n\nINT. B - DAY\n\nB.\n\nINT. C - DAY #2#\n\nC.\n\n"
        "INT. D - DAY #2#\n\nD.\n\nINT. E - DAY\n\nE.\n\nINT. F - DAY\n\nF.\n"
    )
    # B would be scene 2, but the script gives 2 to C: B comes after 1.
    assert [s.number for s in play.scenes] == ["1", "1A", "2", "2A", "5", "6"]
    # The script's own numbers are kept, so the duplicate is still reported.
    assert [s.scene_number for s in play.scenes] == ["1", None, "2", "2", None, None]
    unnumbered = parse("INT. A - DAY\n\nA.\n\nINT. B - DAY\n\nB.\n")
    assert [s.number for s in unnumbered.scenes] == ["1", "2"]



def test_ways_of_speaking_without_brackets_are_not_new_characters():
    play = parse(
        "INT. CLUB - NIGHT\n\nBOB\nHi.\n\nBOB SINGS ON RADIO\nHow does it feel.\n\n"
        "JOHNNY CASH V.O.\nHello.\n\nANA CANTA\nLa la.\n\nFAN VOICES SING\nYeah.\n"
    )
    assert [(d.character, d.extensions) for d in play.scenes[0].dialogues] == [
        ("BOB", []), ("BOB", ["SINGS ON RADIO"]), ("JOHNNY CASH", ["V.O."]), ("ANA", ["CANTA"]),
        ("FAN VOICES SING", []),
    ]
