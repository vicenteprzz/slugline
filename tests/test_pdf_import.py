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



def test_cues_glued_to_dialogue_and_headings_glued_to_action():
    d = " " * 12
    page = "\n".join([
        "INT. BANK -- DAY",
        "A man in a mask walks in.",
        f"{d}Three of a kind. Let's do this.GRUMPY",
        f"{d}Now.",
        "",
        f"{d}That's it? Three guys?CHUCKLES",
        "",
        "He loads the gun.",
        "EXT. STREET -- NIGHT",
        "The car speeds off.",
        f"{d}Faster!GRUMPY",
        f"{d}See you tomorrow. ******",
        "",
        f"{d}Then where's the money?CHUCKLES",
    ])
    play = parse(pdf_text_to_fountain(page))
    assert [(s.heading, s.day_night) for s in play.scenes] == [("INT. BANK -- DAY", "DAY"), ("EXT. STREET -- NIGHT", "NIGHT")]
    assert [s.location for s in play.scenes] == ["BANK", "STREET"]
    assert [(d.character, d.lines[0]) for d in play.scenes[0].dialogues] == [
        ("GRUMPY", "Three of a kind. Let's do this."), ("CHUCKLES", "That's it? Three guys?"),
    ]
    assert [d.character for d in play.scenes[1].dialogues] == ["GRUMPY", "CHUCKLES"]
    assert "*" not in pdf_text_to_fountain(page)



def test_names_a_scan_garbles_are_put_right():
    c, d = " " * 25, " " * 12
    lines = ["INT. BRIDGE - DAY", ""]
    for name in ["ANAKIN", "ANAKIN", "ANAKIN", "OBI-WAN", "OBI-WAN", "OBI-WAN", "GENERAL GRIEVOUS", "GENERAL GRIEVOUS",
                 "GENERAL GRIEVOUS", "ANAKIN---\u00ad", "OBI-WAN·", "GENER.¾ CRIEVOO~", "P.A.", "A.D.", "MAN 1", "MAN 2",
                 "ÁNGEL", "ÁNGELA", "ÁNGELA", "ÁNGELA", "CUT TO:"]:
        lines += [c + name, d + "Line.", ""]
    play = parse(pdf_text_to_fountain("\n".join(lines)))
    names = [x.character for x in play.scenes[0].dialogues]
    assert names.count("ANAKIN") == 4 and names.count("OBI-WAN") == 4 and names.count("GENERAL GRIEVOUS") == 4
    # Real names that only look alike stay apart.
    assert {"P.A.", "A.D.", "MAN 1", "MAN 2", "ÁNGEL", "ÁNGELA"} <= set(names)
    assert "CUT TO:" not in names



def test_headings_without_int_ext_and_a_title_page_with_only_the_title():
    a = " " * 10
    pages = [
        " " * 23 + "A COMPLETE UNKNOWN\n",
        "\n".join([
            f"127{' ' * 67}127EXT. THE VIKING MOTEL -- NIGHT",
            f"{a}Bob walks out.",
            "",
            f"128{' ' * 67}128THE NEWPORT FOLK FESTIVAL -- SUNDAY NIGHT CONCERT",
            f"{a}The crowd waits.",
            "",
            f"129{' ' * 67}129BACKSTAGE :",
            f"{a}Pete paces.",
            "",
            f"130{' ' * 67}130ONSTAGE :",
            f"{a}Bob plugs in.",
        ]),
    ]
    play = parse(pdf_text_to_fountain("\f".join(pages)))
    assert play.title == "A COMPLETE UNKNOWN"
    assert [(s.number, s.heading) for s in play.scenes] == [
        ("127", "EXT. THE VIKING MOTEL -- NIGHT"), ("128", "THE NEWPORT FOLK FESTIVAL -- SUNDAY NIGHT CONCERT"),
        ("129", "BACKSTAGE"), ("130", "ONSTAGE"),
    ]


def _numbered_page(page: int, scenes: list[str]) -> str:
    a, c, d = " " * 11, " " * 48, " " * 27
    lines = [f"{' ' * 30}KOTFM - Final Shooting Script - August 10, 2022{' ' * 10}{page}.", ""]
    for number in scenes:
        if number == "P1":  # a reel number printed before the scene number, on both sides
            lines.append(f"1 P1{' ' * 9}1 P1INT. LODGE - NIGHT")
        else:
            lines.append(f"{number}{' ' * 9}EXT. FIELD - DAY{' ' * 30}{number}")
        cue = "ERNEST ERNEST" if number == "A2" else "ERNEST"
        lines += ["", f"{a}Wind over the grass.", "", f"{c}{cue}", f"{d}Look.", ""]
    return "\n".join(lines)


def test_running_headers_lettered_scenes_and_doubled_names():
    title = " " * 30 + "KILLERS\n\n" + " " * 33 + "by\n\n" + " " * 30 + "Ann Writer\n"
    pages = [title, _numbered_page(1, ["P1", "P2"]), _numbered_page(2, ["1", "2"]), _numbered_page(3, ["A2", "3"]),
             _numbered_page(4, ["4"]), _numbered_page(5, ["5"]), _numbered_page(6, ["6"])]
    text = pdf_text_to_fountain("\f".join(pages))
    assert "Final Shooting Script" not in text  # the running header, page number and all
    play = parse(text)
    assert [s.number for s in play.scenes] == ["P1", "P2", "1", "2", "A2", "3", "4", "5", "6"]
    assert play.scenes[0].heading == "INT. LODGE - NIGHT"
    # ERNEST ERNEST is ERNEST, since ERNEST speaks on his own too.
    assert {d.character for s in play.scenes for d in s.dialogues} == {"ERNEST"}

def test_doubled_name_stays_when_it_is_the_name():
    play = parse("INT. SHIP - DAY\n\nJAR JAR\nHello.\n")
    assert play.scenes[0].dialogues[0].character == "JAR JAR"


def test_extensions_in_brackets():
    play = parse("INT. CAR - DAY\n\nMARTY [PHONE]\nHello?\n\nRACHEL (V.O.)\nIt's me.\n")
    assert [(d.character, d.extensions) for d in play.scenes[0].dialogues] == [("MARTY", ["PHONE"]), ("RACHEL", ["V.O."])]


def test_two_speakers_at_once_and_names_the_pdf_spaces_out():
    c, d = " " * 30, " " * 20
    page = "\n".join([
        "INT. ROOF - NIGHT", "",
        f"{c}BATMAN", f"{d}Down.", "",
        f"{c}SELINA", f"{d}Up.", "",
        f"{c}BATMAN          SELINA", f"{d}Now.", "",
        f"{c}TION     MEDON", f"{d}Senator.", "",
        f"{c}GREAT -- NOW I GOT YOU ON BATMAN", f"{d}Hm.", "",
        f"{c}BATMAN", f"{d}Again.", "",
    ])
    scene = parse(pdf_text_to_fountain(page)).scenes[0]
    assert [(x.character, x.dual) for x in scene.dialogues] == [
        ("BATMAN", False), ("SELINA", False), ("BATMAN", False), ("SELINA", True),
        ("TION MEDON", False), ("BATMAN", False), ("BATMAN", False),
    ]


def test_a_real_name_of_two_words_is_kept():
    play = parse("INT. CLUB - NIGHT\n\nBOB\nHey.\n\nBOB\nHo.\n\nNEUWIRTH\nYo.\n\nNEUWIRTH\nYa.\n\nBOB NEUWIRTH\nMe.\n")
    assert play.scenes[0].dialogues[-1].character == "BOB NEUWIRTH"


def _scanned_page(lines: list[str]) -> str:
    a = " " * 22
    out = []
    for line in lines:
        out += [line, "", f"{a}Something happens here, slowly.", ""]
    return "\n".join(out)


def test_garbled_headings_are_found_by_the_script_numbering():
    from slugline.lint import lint

    a = " " * 22
    page = _scanned_page([
        f"{a}21   INT.  HANGAR - TRADE FEDERATION CRUISER",
        f"{a}22   INT.  ELEVATOR - TRADE FEDERATION CRUISER",
        f"{a[:-6]}------23- IN'l'~  MAIN  HANGAR- -TRADE-FEDERATION ---£RKUt!±IoSl",  # a scan's smudge
        f"(  · r··{a[8:]}24   INT.  ELEVATOR ..",
        f"{a}25   INT.  MAIN HANGAR - TRADE FEDERATION CRUISER",
        f"{a}26   OMITTED",
        f"{a}27   INT.  ELEVATOR SHAFT - PRE-DAWN",
        f"{a}29   EXT.  SPACE - BATTLE",
        f"{a}30   EXT.  SPACE - LATER",
    ])
    play = parse(pdf_text_to_fountain(page))
    assert [(s.number, s.heading) for s in play.scenes][2:4] == [
        ("23", "INT. MAIN HANGAR - TRADE FEDERATION CRUISER"),
        ("24", "INT. ELEVATOR - TRADE FEDERATION CRUISER"),
    ]
    assert "26" not in [s.number for s in play.scenes] and play.omitted == ["26"]
    found = {i.code: i for i in lint(play)}
    # 26 is cut by the script; 28 is nowhere: said, not skipped in silence.
    assert found["omitted-scenes"].params["missing"] == "26"
    assert found["missing-scenes"].params == {"missing": "28", "a": "27", "b": "29"}


def test_a_heading_written_as_a_sentence_and_a_number_on_the_right():
    page = "\n".join([
        "P10                                                                 P10CUT TO AN OSAGE COUPLE.", "",
        "P11                                                                 P11CUT TO Chauffeur opening the door.", "",
        "P12                                                                 P12CUT TO A CAR.", "",
        "P13                                                                 P13CUT TO THE RANCH.", "",
        "P14                                                                 P14CUT TO THE CHURCH.", "",
        "P15                                                                 P15CUT TO THE FIELDS.", "",
        "1          INT. TRAIN CAR - DAY                                                1", "",
        "Rain.", "",
        "2 1        OUTSIDE THE ELEVATOR HALLWAY                                        2", "",
        "Dark.", "",
        "3          INT. STATION - NIGHT                                                3", "",
    ])
    numbers = {s.number: s.heading for s in parse(pdf_text_to_fountain(" " * 30 + "OSAGE\f" + page)).scenes}
    assert numbers["P11"] == "CUT TO CHAUFFEUR OPENING THE DOOR"
    assert numbers["2"] == "OUTSIDE THE ELEVATOR HALLWAY"
