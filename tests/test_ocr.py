"""Reading scanned scripts: what happens after macOS has recognised the text."""

from slugline import ocr
from slugline.parser import parse_heading


def test_a_page_is_laid_out_column_for_column():
    # (left, top, right, text) as fractions of a 612 x 792 point page; a scan's
    # lines are 12.6 points apart, not 12, and a blank line sits before the cue.
    row = lambda n: n * 12.6 / 792  # noqa: E731
    lines = [
        (0.15, row(7), 0.6, "INT. KITCHEN - NIGHT"),
        (0.15, row(9), 0.9, "Rain on the window."),
        (0.43, row(11), 0.6, "ANNA"),
        (0.29, row(12), 0.7, "Who's there?"),
        (0.29, row(13), 0.7, "Show yourself."),
    ]
    page = [line for line in ocr._lay_out(lines, 612, 792).splitlines()]
    text = [line.strip() for line in page]
    k = text.index("ANNA")
    assert text[k + 1:k + 3] == ["Who's there?", "Show yourself."]  # no blank row inside the speech
    assert text[k - 1] == "" and text[k - 2] == "Rain on the window."
    assert page[k].index("ANNA") == 37 and page[k + 1].index("Who") == 25
    assert page[text.index("INT. KITCHEN - NIGHT")].index("INT") == 13


def test_other_alphabets_are_lookalikes_or_smudges():
    assert ocr._latin("АДАМ") == "ADAM"
    assert ocr._latin("crouches ослторі восе") == "crouches"


def test_times_a_scan_misreads():
    assert parse_heading("INT. RECORDING STUDIO - DAX")[2] == "DAY"
    assert parse_heading("INT. APARTMENT - EARLY DAMN")[2] == "EARLY DAWN"
    assert parse_heading("INT. BAR - DAMP")[2] is None
    assert parse_heading("EXT. NIGHT - MULHOLLAND DRIVE")[1:] == ("MULHOLLAND DRIVE", "NIGHT")
    assert parse_heading("INT. NIGHT CLUB - BAR")[2] is None
