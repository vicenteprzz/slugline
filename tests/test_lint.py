"""Rule-based formatting checks."""

from slugline import parse
from slugline.lint import lint


def codes(text: str) -> list[str]:
    return [i.code for i in lint(parse(text))]


def test_clean_script_has_no_issues(example_text):
    assert lint(parse(example_text)) == []


def test_heading_without_int_ext_or_time():
    issues = lint(parse("Title: X\n\n.MONTAGE\n\nX.\n\nINT. BAR\n\nY.\n"))
    assert [(i.code, i.scene) for i in issues] == [("no-int-ext", "1"), ("no-time", "1"), ("no-time", "2")]


def test_empty_scene_and_cue_without_dialogue():
    found = codes("Title: X\n\nINT. A - DAY\n\nINT. B - DAY\n\nBOB\n(nods)\n")
    assert found == ["empty-scene", "empty-dialogue"]


def test_misspelled_character_is_flagged_but_numbered_ones_are_not():
    text = (
        "Title: X\n\nINT. A - DAY\n\nSHERIFF\nHi.\n\nSHERIF\nHi.\n\nMAN 1\nHi.\n\nMAN 2\nHi.\n\n"
        "MR. B\nHi.\n\nMR. D\nHi.\n\nMR B\nHi.\n"
    )
    messages = [i.message for i in lint(parse(text)) if i.code == "similar-characters"]
    assert len(messages) == 2
    assert any("SHERIF " in m and "SHERIFF" in m for m in messages)
    assert any("MR B" in m and "MR. B" in m and "punctuation" in m for m in messages)


def test_location_written_two_ways():
    found = codes("Title: X\n\nINT. BIG JOHN'S OFFICE - DAY\n\nX.\n\nINT. BIG JOHNS OFFICE - NIGHT\n\nY.\n")
    assert found == ["similar-locations"]


def test_scene_numbering_problems():
    found = codes("Title: X\n\nINT. A - DAY #1#\n\nX.\n\nINT. B - DAY #1#\n\nY.\n\nINT. C - DAY\n\nZ.\n")
    assert found == ["partial-numbering", "duplicate-number"]


def test_long_action_paragraph_is_a_note():
    issues = lint(parse("Title: X\n\nINT. A - DAY\n\n" + "He walks and walks. " * 30 + "\n"))
    assert [(i.severity, i.code) for i in issues] == [("info", "long-action")]
