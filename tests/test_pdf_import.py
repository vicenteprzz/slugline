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


def test_letters_spaced_out_by_the_pdf_are_joined():
    cue = " " * 25
    lines = ["INT. GYM - DAY", ""]
    for name in ["MARTY", "MARTY", "M ARTY (CONT'D)", "MARY ANN"]:
        lines += [cue + name, " " * 12 + "Hi.", ""]
    play = parse(pdf_text_to_fountain("\n".join(lines)))
    assert [d.character for d in play.scenes[0].dialogues] == ["MARTY", "MARTY", "MARTY", "MARY ANN"]


# A shooting script laid out with wider margins: action at 11, dialogue at 27,
# cues at 48, scene numbers on both sides, revision headers, and a cue the PDF
# put at the end of the first line of dialogue.
WIDE_TITLE = (
    " " * 52 + "Rev. 12/17/20 (Blue)\n\n" + " " * 47 + "THE CAPE\n\n" + " " * 49 + "an origin\n\n"
    + " " * 52 + "by\n\n" + " " * 40 + "Ann Writer\n"
)


def _wide_page(number: int) -> str:
    a, d, c = " " * 11, " " * 27, " " * 48
    return "\n".join([
        f"02/09/20  (White Shooting Script)  {number}.",
        f"{number}          INT.  POLICE  STATION  -  NIGHT" + " " * 40 + f"{number}",
        "",
        f"{a}Rain  hammers  the  windows.  GORDON  waits  by  the  door",
        f"{a}with  a  file.",
        "",
        f"{c}GORDON",
        f"{d}Where  were  you?",
        "",
        f"{d}What  do  we  know? CAPE",
        f"{d}Nothing  yet.",
        "",
        f"{a}He  turns  away.",
        "",
        f"{c}CAPE",
        f"{d}Up  here.",
        "",
        f"{number + 1}          ON  THE  ROOF" + " " * 50 + f"{number + 1}",
        "",
        f"{a}Wind.",
        "",
        f"{c}CUT TO:" if number == 1 else "",
        "",
        f"{' ' * 80}(CONTINUED)",
    ])


def test_wide_margins_and_shooting_script_marks():
    pages = [WIDE_TITLE, _wide_page(1), _wide_page(3)]
    # A scanned page sits a few characters to the right of the others.
    pages[2] = "\n".join(" " * 6 + line if line.strip() else line for line in pages[2].splitlines())
    play = parse(pdf_text_to_fountain("\f".join(pages)))
    assert play.title == "THE CAPE"
    assert play.title_page["author"] == "Ann Writer"
    assert [(s.number, s.heading) for s in play.scenes] == [
        ("1", "INT. POLICE STATION - NIGHT"), ("2", "ON THE ROOF"),
        ("3", "INT. POLICE STATION - NIGHT"), ("4", "ON THE ROOF"),
    ]
    first = play.scenes[0]
    assert [(d.character, d.lines) for d in first.dialogues] == [
        ("GORDON", ["Where were you?"]), ("CAPE", ["What do we know?", "Nothing yet."]), ("CAPE", ["Up here."]),
    ]
    assert first.elements[0].text == "Rain hammers the windows. GORDON waits by the door with a file."
    assert [d.character for d in play.scenes[2].dialogues] == ["GORDON", "CAPE", "CAPE"]
    assert "White Shooting Script" not in pdf_text_to_fountain("\f".join(pages))


def test_centred_text_in_action_stays_on_its_lines():
    page = "\n".join([
        "INT. CINEMA - NIGHT",
        "",
        "The screen lights up:",
        "",
        " " * 23 + '"Modern Times". A story',
        " " * 21 + "of industry.",
        "",
        "The crowd claps.",
    ])
    text = pdf_text_to_fountain(page)
    assert '"Modern Times". A story\nof industry.' in text
    assert not parse(text).scenes[0].dialogues


def test_numbers_inside_the_margin_and_a_page_shifted_left():
    a, d, c = " " * 24, " " * 46, " " * 72

    def page(first: int, margin: str, speech: str, cue: str) -> str:
        return "\n".join([
            f"{margin}{first}   EXT.   SPACE",
            "",
            f"{margin}A  vast  sea  of  stars  serves  as  the  backdrop  for  the  battle  ahead.",
            f"{margin}Two  starfighters  dive  between  the  cruisers  as  the  fleet  opens  fire.",
            "",
            f"{cue}ANAKIN",
            f"{speech}There  isn't  a  droid  made  that  can",
            f"{speech}outfly  you,  Master.",
            "",
            f"{margin}{first + 1}   INT.   COCKPIT  -  SPACE",
            "",
            f"{margin}Obi-Wan  bounces  through  the  flak  with  a  frown  as  his  ship  shakes.",
            f"{margin}Alarms  ring  out  across  the  cockpit  while  the  droid  whistles.",
            "",
            f"{cue}OBI-WAN",
            f"{speech}Not  again.",
        ])

    title = " " * 60 + "STAR WARS\n" + " " * 50 + "EPISODE III: REVENGE OF THE SITH\n\n" + " " * 62 + "by\n\n" + " " * 58 + "George Lucas\n"
    pages = [title, page(1, a, d, c), page(3, a, d, c), page(5, "", " " * 22, " " * 48)]  # the last one sits at the page edge
    play = parse(pdf_text_to_fountain("\f".join(pages)))
    assert play.title == "STAR WARS - EPISODE III: REVENGE OF THE SITH"
    assert [s.number for s in play.scenes] == ["1", "2", "3", "4", "5", "6"]
    assert [d.character for s in play.scenes for d in s.dialogues] == ["ANAKIN", "OBI-WAN"] * 3
