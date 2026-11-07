"""PDF-to-Fountain conversion, tested on layout text like pypdf produces."""

from slugline import parse
from slugline.pdf_import import pdf_text_to_fountain

TITLE = "                         John's Boys\n\n                          written by\n\n                      Vicente Pérez\n\nAddress\nPhone\n"

PAGE_1 = """INT. BARN - NIGHT

A rope hangs from a beam. Mr. B watches the
door.

KNOCK KNOCK

                         MR. X (V.O.) (CONT'D)
                  (with a somewhat broken
                   voice)
            I ran... and I didn't
                         (MORE)

                                                                             2."""

PAGE_2 = """
                         MR. X (V.O.) (CONT'D)
            look back.

                                                              CUT TO:
"""


def convert() -> str:
    return pdf_text_to_fountain("\f".join([TITLE, PAGE_1, PAGE_2]))


def test_title_page_without_contact_placeholders():
    out = convert()
    assert out.startswith("Title: John's Boys\nCredit: written by\nAuthor: Vicente Pérez\n\n")
    assert "Address" not in out and "Phone" not in out


def test_wrapped_action_is_joined():
    assert "A rope hangs from a beam. Mr. B watches the door." in convert()


def test_all_caps_action_is_forced():
    assert "\n!KNOCK KNOCK\n" in convert()


def test_page_numbers_are_dropped():
    assert "2." not in convert()


def test_dialogue_continued_after_page_break_is_one_block():
    play = parse(convert())
    (block,) = play.scenes[0].dialogues
    assert block.character == "MR. X"
    assert block.parentheticals == ["(with a somewhat broken voice)"]
    assert block.lines == ["I ran... and I didn't", "look back."]


def test_right_aligned_transition():
    play = parse(convert())
    assert play.scenes[0].elements[-1].text == "CUT TO:"


def test_first_page_without_title_page():
    out = pdf_text_to_fountain(PAGE_2.replace("CUT TO:", "") + "\fINT. A - DAY\n")
    assert not out.startswith("Title:")
