"""Reading scanned scripts: what happens after macOS has recognised the text."""

from slugline import ocr
from slugline.parser import parse_heading


def test_a_page_is_laid_out_column_for_column():
    # (left, top, right, text) as fractions of a 612 x 792 point page
    lines = [
        (0.15, 0.10, 0.6, "INT. KITCHEN - NIGHT"),
        (0.15, 0.13, 0.9, "Rain on the window."),
        (0.43, 0.16, 0.6, "ANNA"),
        (0.29, 0.18, 0.7, "Who's there?"),
    ]
    page = ocr._lay_out(lines, 612, 792).splitlines()
    assert page[7].lstrip() == "INT. KITCHEN - NIGHT" and page[7].index("INT") == 13
    assert page[11].lstrip() == "ANNA" and page[11].index("ANNA") == 37
    assert page[12].lstrip() == "Who's there?" and page[12].index("Who") == 25


def test_other_alphabets_are_lookalikes_or_smudges():
    assert ocr._latin("АДАМ") == "ADAM"
    assert ocr._latin("crouches ослторі восе") == "crouches"


def test_times_a_scan_misreads():
    assert parse_heading("INT. RECORDING STUDIO - DAX")[2] == "DAY"
    assert parse_heading("INT. APARTMENT - EARLY DAMN")[2] == "EARLY DAWN"
    assert parse_heading("INT. BAR - DAMP")[2] is None
    assert parse_heading("EXT. NIGHT - MULHOLLAND DRIVE")[1:] == ("MULHOLLAND DRIVE", "NIGHT")
    assert parse_heading("INT. NIGHT CLUB - BAR")[2] is None
