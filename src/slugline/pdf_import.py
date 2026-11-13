"""Convert a PDF screenplay to Fountain.

Screenplay PDFs keep the industry layout, so the left indentation of each line
tells us what it is: action and headings at the left margin, dialogue further
in, parentheticals further, character cues further still, and transitions and
page numbers at the right. Where those columns fall depends on the page
margins and the font, so they are measured on each script (see `_columns`).

Real PDFs also bring scene numbers beside the headings, CONTINUED lines at
page breaks, and, when they were scanned, extra spaces and stray braces.

The conversion works on the extracted text, so it can be tested without a PDF.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from slugline.parser import DUAL_MARK, DUAL_WIDE, SCENE_PREFIX

PAGE_NUMBER = re.compile(r"^\d+\.?$")
CUE_BASE = re.compile(r"\s*\(.*$")
# Two speakers at once: the PDF prints both names on the cue line, far apart
# ("BATMAN        SELINA"). Some PDFs also space out a single name ("TION
# MEDON"), so the gap is kept as a mark (DUAL_MARK) and the parser decides:
# two speakers when both names speak on their own, one name otherwise.
_UP = "A-ZÁÉÍÓÚÜÑÀÈÌÒÙÇ"
_NAME = rf"[{_UP}][{_UP}0-9.'’#/-]*(?: [{_UP}0-9.'’#/-]+)*"
DUAL_CUE = re.compile(rf"^(\s{{6,}})({_NAME})(\s{{3,}})({_NAME})\s*$")
WIDE_GAP = 10  # two speakers' names sit columns apart; a spaced-out name, a few spaces
# Title page placeholders that templates leave behind; they are not real data.
PLACEHOLDERS = {"address", "phone", "e-mail", "email", "contact"}
BYLINES = {"written by", "by", "screenplay by"}
# "12   INT. HOUSE - NIGHT   12": a heading with its scene number on each side.
# Scene numbers: 12, 12A, and with a letter in front, as prologues use (P1, A12).
# A page or reel number can come before it: "1 P1   1 P1INT. OSAGE LODGE".
NUMBERED = re.compile(r"^(?:\d{1,4} (?=[A-Z]))?((?:[A-Z]{1,2}\d{1,4}|\d{1,4})[A-Z]{0,2})\s{2,}(\S.*?)(?:\s{2,}\1)?$")
# Page-break noise: (CONTINUED), CONTINUED: (2), (CONT'D), and the same scanned
# with braces or cut short at the page edge.
CONTINUED = re.compile(r"^[({]?\s*CONT(INUED|'D)?\s*[:)}]?\s*([({]\s*\d+\s*[)}])?$", re.IGNORECASE)
MORE = re.compile(r"^[({]\s*MORE\s*[)}]$", re.IGNORECASE)
LETTERS = re.compile(r"[A-Za-z]")
REVISION = re.compile(r"^rev\b|\d{1,2}/\d{1,2}/\d{2,4}|draft", re.IGNORECASE)
# A page header with CONTINUED in it, such as "02/09/20 CONTINUED: 58.", spaced out or not.
CONTINUED_HEADER = re.compile(r"C\s?O\s?N\s?T\s?I\s?N\s?U\s?E\s?D\s?:")
# Revision stars at the end of a line and stray marks a scan leaves before a name.
REVISION_MARKS = re.compile(r"(\s+\*+)+\s*$")  # "SEBASTIAN *" or "SEBASTIAN ******"
# Capitals at the end of a line of dialogue: a name the PDF moved there, even
# glued to the last word ("Let's do this.GRUMPY").
TRAILING_NAME = re.compile(
    r"(?:(?<=[\s.?!,;:)\-\"'…’])|^)([A-Z][A-Z0-9.'’#&/-]*(?: [A-Z][A-Z0-9.'’#&/-]*){0,3})(\s*\([^)]*\)?)?\s*$"
)
NOT_NAMES = {"OK", "NO", "YES", "TV", "FBI", "CIA", "USA", "LA", "NYC", "DNA", "ATM", "SWAT", "GCPD", "NOW", "HEY", "WHAT"}
LEADING_JUNK = re.compile(r"^(?:[^\w(\"']|_)+")  # marks before a name; accented letters are letters (ÁNGEL)
# Revision page headers: "02/09/20 (White February Shooting Script) 3." or
# "3 02/09/20 CONTINUED: (2)".
DATED_HEADER = re.compile(
    r"^(\d+[A-Z]?\s+)?\d{1,2}/\d{1,2}/\d{2,4}\s*(\(|C\s?O\s?N|$)"  # 02/09/20 (White ...) 3.
    r"|^(\w+\s+)?Rev\.\s*\("  # Green Rev. (mm/dd/yy) 157.
)
MARGIN_MARK = re.compile(r"^\s*(?:[Il|!.,'`]|[^\w\s]{2,3})\s{5,}(?=\S)")
SPEECH_MARKS = set(".-!?—–…")  # a line of just "..." can be dialogue
SCENE_NUMBER_MARK = re.compile(r"\s*#[\w.\-]+#\s*$")
NOISE = set("·•~_|\\^¬")


def _squeeze(text: str) -> str:
    """One space between words: justified and scanned PDFs put several."""
    return re.sub(r"\s{2,}", " ", text).strip()


def _caps(text: str) -> bool:
    letters = LETTERS.findall(CUE_BASE.sub("", text))
    return bool(letters) and all(c.isupper() for c in letters)


@dataclass
class _Columns:
    action: int  # left margin
    dialogue: int
    cue: int

    def kind_limit(self) -> int:
        """Lines starting before this column are action or headings."""
        return int((self.action + self.dialogue) / 2)

    def shifted(self, by: int) -> _Columns:
        return _Columns(self.action + by, self.dialogue + by, self.cue + by)

    def kind(self, indent: int, s: str) -> str:
        if indent < (self.action + self.dialogue) / 2:
            return "action"
        if indent >= self.cue + max(15, self.cue - self.dialogue):
            return "right"
        if indent >= self.dialogue + 3 and _caps(s) and s.endswith(":"):
            return "right"  # CUT TO: set at the cue column
        if s[0] in "({":
            return "parenthetical"
        if indent >= (self.dialogue + self.cue) / 2:
            return "cue" if _caps(s) else "parenthetical"
        return "dialogue"


def _columns(lines: list[str]) -> _Columns:
    """Find where action, dialogue and cues start in this script."""
    indents: Counter[int] = Counter()
    rows = []
    for raw in lines:
        s = raw.strip()
        # Page numbers, scene numbers and revision headers don't show the columns.
        squeezed = _squeeze(s)
        if s and not PAGE_NUMBER.match(s) and not re.match(r"\d+[A-Z]{0,2}\s{2,}", s) \
                and not DATED_HEADER.match(squeezed) and not CONTINUED.match(squeezed):
            indent = len(raw) - len(raw.lstrip())
            indents[indent] += 1
            rows.append((indent, s))
    if not rows:
        return _Columns(0, 12, 25)
    # The left margin is where the long lines start: action runs the full
    # width of the page, dialogue never does. (Without long lines, it is the
    # leftmost column most lines use; scene numbers sit further left, but
    # there are few of them.)
    wide = Counter(i for i, s in rows if len(_squeeze(s)) >= 45)
    floor = max(1, len(rows) // 50)
    action = wide.most_common(1)[0][0] if wide else min((i for i, n in indents.items() if n >= floor), default=min(indents))
    speech = Counter(i for i, s in rows if i > action + 3 and not _caps(s) and s[0] not in "({")
    dialogue = speech.most_common(1)[0][0] if speech else action + 12
    names = Counter(i for i, s in rows if i > dialogue + 3 and _caps(s) and len(s) < 40 and not s.endswith(":"))
    cue = names.most_common(1)[0][0] if names else dialogue + 13
    return _Columns(action, dialogue, cue)


def _running_key(line: str) -> str:
    """A page header or footer without its page number or date, to compare pages."""
    return re.sub(r"\d+", "#", _squeeze(line)).strip(" .")


HEADING_SPECKS = re.compile(r"[^\w\s.,'’/&()#:\-–—!?\"]|\s[._,'’]+(?:\s|$)")
# A scene cut from the draft, or moved to another number: "OMITTED", "OMITTEDMOVED TO 65A", "MOVED TO A89".
OMITTED = re.compile(r"^\W*(?:OMIT(?:TED)?(?:\b|(?=[A-Z]))|MOVED TO\b)", re.IGNORECASE)
# "36-37   36-37OMITTED": a run of scenes cut at once.
OMITTED_RANGE = re.compile(r"^\s*(\d{1,4})\s*[-–]\s*(\d{1,4})\s{2,}(?:\d{1,4}\s*[-–]\s*\d{1,4})?\s*OMIT", re.IGNORECASE)
NUMBER_PARTS = re.compile(r"^([A-Z]{0,2})(\d{1,4})([A-Z]{0,2})$")
MAX_GAP = 15  # a longer run of missing numbers is a cut, not a misreading


def _continued_like(text: str) -> bool:
    """CONTINUED: as a scan smudges it ("COJITUlUE,D: . {J4)")."""
    word = re.sub(r"[^A-Za-z]", "", text.split(":")[0]).upper()
    return 6 <= len(word) <= 11 and word != "CONTINUOUS" and SequenceMatcher(None, word, "CONTINUED").ratio() >= 0.6


def _strict_heading(line: str) -> tuple[str, str] | None:
    """(number, text) of a numbered heading read cleanly: "25   INT. MAIN HANGAR"."""
    m = NUMBERED.match(line.strip())
    if not m:
        return None
    number, rest = m.group(1), _squeeze(m.group(2))
    rest = re.sub(rf"^\d{{1,4}} (?={re.escape(number)})", "", rest)
    if rest.startswith(number) and not rest[len(number):len(number) + 1].isdigit():
        rest = rest[len(number):].lstrip()
    if OMITTED.match(rest) or CONTINUED.match(rest) or CONTINUED_HEADER.search(rest) or _continued_like(rest):
        return None  # "2   OMIT": a scene cut from the script, not a scene
    if SCENE_PREFIX.match(rest) or (len(LETTERS.findall(rest)) >= 3 and _caps(rest)):
        return number, rest
    return None


def _clean_heading(text: str, known: list[str]) -> str:
    """A heading a scan or a PDF garbled, made readable: junk out, INT./EXT.
    put right, and the place matched to one the script already names when
    every word is that place's word misread (CRUISE1 for CRUISER, never
    DOORWAY for HALLWAY). Empty when nothing readable is left."""
    text = re.sub(r"\s{6,}\S.*\b(?:19|20)\d\d\b.*$", "", text)  # a page header glued on
    text = re.sub(r"[^A-Za-z0-9 .,'’/&()#:\-]", " ", text).strip(" -.,'’")
    words = text.split()
    prefix = ""
    if words and not SCENE_PREFIX.match(text):
        first = re.sub(r"[^A-Z]", "", words[0].upper())
        if first in {"LNT", "IT"} or first.startswith("IN") and len(first) <= 4:
            prefix, text = "INT. ", " ".join(words[1:])
        elif first in {"XT", "FXT"} or first.startswith("EX") and len(first) <= 4:
            prefix, text = "EXT. ", " ".join(words[1:])
    text = re.sub(r"(?<=[A-Za-z]{4})-(?=[A-Za-z]{4})", " ", text)  # TRADE-FEDERATION, not PRE-DAWN
    text = re.sub(r"\s+-+\s*|\s*-{2,}\s*|\s*-+\s+|(?<=\W)-+|-+(?=\W|$)", " - ", text)
    letters = LETTERS.findall(text)
    if sum(c.isupper() for c in letters) >= 0.6 * max(1, len(letters)):
        text = " ".join(w for w in text.split() if not any(c.islower() for c in w))  # scan noise
    else:
        text = text.upper()  # a heading written as a sentence: "CUT TO Osage playing golf."
    # Specks: tokens with no letter or number, a number stuck to a word (CRUISE1),
    # a lone letter at the end.
    text = " ".join(w for w in text.split() if w == "-" or re.search(r"[A-Z0-9]", w))
    text = re.sub(r"\b([A-Z]{3,})\d\b", r"\1", text)
    text = re.sub(r"(?:\s+-)+\s+", " - ", f" {text} ").strip(" -.,'’")
    text = re.sub(r"(?:\s+-)?\s+[A-Z]$", "", text).strip(" -.,'’")
    text = re.sub(r"^(INT|EXT)\s*\.?\s+", r"\1. ", prefix + text)
    if not re.search(r"\b(?!INT\b|EXT\b)[A-Z]{3,}", text):
        return ""  # nothing left to read
    # "INT. ELEVATOR" cut short: the one heading that goes on from it.
    for joint in (" - ", " "):
        longer = [h for h in known if h.startswith(text + joint)]
        if len(longer) == 1:
            return longer[0]
    vocabulary = {w for h in known for w in re.findall(r"[A-Z]{3,}", h)}
    misread = [w for w in re.findall(r"[A-Z]{3,}", text) if w not in vocabulary]
    if misread and all(any(abs(len(w) - len(v)) <= 2 and SequenceMatcher(None, w, v).ratio() >= 0.8 for v in vocabulary)
           for w in misread):
        key = re.sub(r"[^A-Z]", "", text)
        best, score = None, 0.0
        for heading in known:
            ratio = SequenceMatcher(None, key, re.sub(r"[^A-Z]", "", heading)).ratio()
            if ratio > score:
                best, score = heading, ratio
        if best and score >= 0.8:
            return best
    return text


def _recover_headings(pages: list[list[str]]) -> list[str]:
    """Find the scene headings a PDF garbled, using the script's own numbers.

    When scene 22 is followed by scene 25, scenes 23 and 24 are looked for
    between them: a line that starts with the number, whatever junk a scan
    left around it ("------23- IN'l'~ MAIN HANGAR- -TRADE-FEDERATION ---£RKU"),
    or a heading the PDF didn't write in capitals ("P11   P11CUT TO Chauffeur
    opening the car door"). The line is rewritten as a clean heading, so it
    is read like any other. What can't be found is reported by the checks."""
    # A speck in the margin before a numbered heading ("0      57   INT. DOORWAY")
    # is not the scene number: blank it.
    speck = re.compile(r"^\s*[^\sA-Za-z]{1,2}\s{3,}(?=[A-Z]{0,2}\d{1,4}[A-Z]{0,2}\s{2,}\S)|^\s*\S{1,3}\s{8,}(?=[A-Z]{0,2}\d{1,4}[A-Z]{0,2}\s{2,}\S)")
    for page in pages:
        for i, line in enumerate(page):
            page[i] = speck.sub(lambda m: " " * len(m.group(0)), line)
    for page in pages:
        for i in range(len(page) - 1, -1, -1):
            cut = OMITTED_RANGE.match(page[i])
            if cut and 0 < int(cut.group(2)) - int(cut.group(1)) < 50:
                page[i:i + 1] = [f"{n}   {n}OMITTED" for n in range(int(cut.group(1)), int(cut.group(2)) + 1)]
    spots = [(p, i) for p, page in enumerate(pages) for i in range(len(page))]
    strict = []
    for k, (p, i) in enumerate(spots):
        found = _strict_heading(pages[p][i])
        parts = NUMBER_PARTS.match(found[0]) if found else None
        if parts:
            strict.append((k, parts.group(1), int(parts.group(2)), found[1]))
    known = list(dict.fromkeys(h for *_, h in strict if SCENE_PREFIX.match(h) and not HEADING_SPECKS.search(h)))
    # A clean heading that fits the numbering (94 < 95 < 96) is a heading
    # wherever the page puts it: a scanned page can sit off the margins.
    # ...and so is one next to its neighbour in the same run (P1 before P2, P3 after
    # it), when nothing else has its number.
    numbers = Counter((series, n) for _, series, n, _ in strict)
    for i_, (k, series, n, heading) in enumerate(strict):
        a = strict[i_ - 1][2] if i_ else -1
        b = strict[i_ + 1][2] if i_ + 1 < len(strict) else -1
        same = {(s, m) for _, s, m, _ in strict[max(0, i_ - 1):i_ + 2]}
        if not (a < n < b or (series, n - 1) in same or (series, n + 1) in same) or numbers[(series, n)] > 1:
            continue
        if True:
            p, i = spots[k]
            number = NUMBERED.match(pages[p][i].strip()).group(1)
            if HEADING_SPECKS.search(heading):
                heading = _clean_heading(heading, known) or heading
            # "-- UNTIL WE SOAR OVER THE BIKE": a numbered shot; "HENRY'S aousE": a scan's case.
            heading = re.sub(r"^[-–—.\s]+", "", heading).upper()
            heading = re.sub(rf"\s+{re.escape(number)}\s+", " ", heading)
            if heading:
                pages[p][i] = f"{number}   {number}{heading}"
    by_series: dict[str, list[tuple[int, int]]] = {}
    for k, series, n, _ in strict:
        by_series.setdefault(series, []).append((k, n))
    for series, marks in by_series.items():
        # A run of numbers, not letters for inserts (A14 goes between 13 and 14).
        numbers = {n for _, n in marks}
        if series and (len(numbers) < 5 or len(numbers) < 0.6 * (max(numbers) - min(numbers) + 1)):
            continue
        # The ends of the run: "P1" before the first one found, the one after the last.
        edges = []
        if marks[0][1] > 1:
            before = max([k for k, *_ in strict if k < marks[0][0]], default=-1)
            edges.append((before, 0, marks[0][0], marks[0][1]))
        after = min([k for k, *_ in strict if k > marks[-1][0]], default=len(spots))
        edges.append((marks[-1][0], marks[-1][1], after, marks[-1][1] + 2))
        for low_k, a, high_k, b in edges:
            for missing in range(max(a + 1, b - 3), b):
                number = f"{series}{missing}"
                pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(number)}(?![0-9])(?![A-Z]{{1,2}}\b)")
                for k in range(low_k + 1, high_k):
                    p, i = spots[k]
                    line = pages[p][i]
                    m = pattern.match(line.lstrip())
                    if not m or not series:  # only a lettered run (P1); a bare "1" is too common
                        continue
                    after_text = re.sub(rf"^\s*{re.escape(number)}(?![0-9])", "", line.lstrip()[m.end():]).strip()
                    after_text = re.sub(rf"\s+{re.escape(number)}\W*$", "", after_text)
                    heading = _clean_heading(after_text, known)
                    if len(re.findall(r"[A-Z]{3,}", heading)) >= 2:
                        pages[p][i] = f"{number}   {number}{heading}"
                        break
        for j, ((ka, a), (kb, b)) in enumerate(zip(marks, marks[1:])):
            if not 1 < b - a <= MAX_GAP:
                continue
            # Between the scenes around the gap, and one further each way: a
            # montage can print its shots out of order (65, 66, then 64).
            low = marks[j - 1][0] + 1 if j else ka + 1
            high = marks[j + 2][0] if j + 2 < len(marks) else kb
            taken: set[int] = set()
            for missing in range(a + 1, b):
                number = f"{series}{missing}"
                # 106 is not 106A; "P11CUT TO" is still P11.
                pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(number)}(?![0-9])(?![A-Z]{{1,2}}\b)")
                for k in [*range(ka + 1, kb), *range(low, ka), *range(kb + 1, high)]:
                    if k in taken or any(k == mark for mark, _ in marks):
                        continue
                    p, i = spots[k]
                    line = pages[p][i]
                    m = pattern.search(line)
                    if not m or m.start() > 45:
                        continue
                    # Before the number, only margin specks a scan leaves ("Cf", "\\if", "0"),
                    # set apart from it; never words.
                    before = line[:m.start()]
                    if re.search(r"[A-Za-z]{3,}", before) or len(re.findall(r"[A-Za-z0-9]", before)) > 3:
                        continue
                    if re.match(r" ?[a-z]", line[m.end():]):  # "57 hours later"
                        continue
                    after = re.sub(rf"^[\W_]*{re.escape(number)}(?![0-9])", "", line[m.end():].strip())
                    after = re.sub(rf"\s+{re.escape(number)}\W*$", "", after)  # the number on the right
                    if CONTINUED.match(after.strip()) or CONTINUED_HEADER.search(after) or OMITTED.match(after.strip()):
                        continue  # "147   CONTINUED:" is the page, not the scene
                    if after[:1].isdigit():
                        continue  # "2 1   OUTSIDE": a number split in two; the right margin says which
                    heading = _clean_heading(after, known)
                    if len(re.findall(r"[A-Z]{3,}", heading)) < 1 or len(heading) < 4:
                        continue
                    pages[p][i] = f"{number}   {number}{heading}"
                    taken.add(k)
                    break
                else:
                    # The right-hand number can survive when the left one doesn't:
                    # "7A   OUTSIDE IN THE ... ELEVATOR HALLWAY   147", "... PRE-DAWN  2 5".
                    spaced = r"\s?".join(re.escape(c) for c in number)
                    right = re.compile(rf"\s{{2,}}{spaced}\s*$")
                    for k in range(ka + 1, kb):
                        p, i = spots[k]
                        line = pages[p][i]
                        m = right.search(line)
                        if k in taken or not m or len(line) - len(line.lstrip()) > 20:
                            continue
                        text = re.sub(r"^\s*\S{0,4}\d\S{0,3}(?:\s\S{1,2})?\s{2,}", "", line[:m.start()])  # the left number, garbled
                        if not text.strip() or CONTINUED.match(text.strip()) or OMITTED.match(text.strip()):
                            continue
                        heading = _clean_heading(text, known)
                        if len(re.findall(r"[A-Z]{3,}", heading)) < 2:
                            continue
                        pages[p][i] = f"{number}   {number}{heading}"
                        taken.add(k)
                        break
    return known


MISREAD = {"0": "O", "5": "S", "1": "I", "l": "I"}
# A capital word with one digit (or an l) a scan put in for a letter: AZ0TEA, PI5O, C0CHE, MARC0, KlTCHEN.
MISREAD_WORD = re.compile(r"\b([A-ZÁÉÍÓÚÑ]{2,}[015l][A-ZÁÉÍÓÚÑ]+|[A-ZÁÉÍÓÚÑ]+[015l][A-ZÁÉÍÓÚÑ]{2,}|[A-ZÁÉÍÓÚÑ]{3,}[05])\b")


def _misread_letters(line: str) -> str:
    """Letters a scan read as digits, inside capital words. Numbers, scene
    numbers (A10) and words with digits of their own (R2-D2, MP5) stay."""
    def fix(m: re.Match) -> str:
        word = m.group(1)
        number = re.match(r"^[A-Z]{1,2}\d+", word)
        # "P1INT." and "A12CUT TO": a scene number glued to its heading, the number printed before it too.
        if number and re.search(rf"(?<!\S){re.escape(number.group(0))}(?!\S)", line[:m.start()]):
            return word
        if re.search(r"\d(?:INT|EXT|I/E)", word):
            return word
        return "".join(MISREAD.get(c, c) for c in word)

    return MISREAD_WORD.sub(fix, line)


def _dual_cue(line: str) -> str:
    """Mark two names far apart on a cue line; never a heading ("INT.     KITCHEN")."""
    m = DUAL_CUE.match(line)
    if not m or SCENE_PREFIX.match(m.group(2) + " ") or HEADING_WORD.match(m.group(2)):
        return line
    wide = len(m.group(3)) >= WIDE_GAP
    if not wide and len(m.group(1)) < 15:  # a few spaces, near the margin: just words
        return line
    mark = DUAL_WIDE if wide else DUAL_MARK
    return f"{m.group(1)}{m.group(2)}{mark}{m.group(4)}"


HEADING_WORD = re.compile(r"^(?:INT|EXT|I/E|INT\./EXT|EXT\./INT)\.?$")


def _drop_running_lines(pages: list[list[str]]) -> None:
    """Remove the headers and footers printed on every page ("KOTFM - Final
    Shooting Script - August 10, 2022  12.", "209 POST FINAL -- 3.3.24"): a
    line among the first or last two of a page that comes back, page number
    aside, on a good share of the pages."""
    if len(pages) < 6:
        return

    def edges(page: list[str]) -> list[int]:
        filled = [i for i, line in enumerate(page) if line.strip()]
        return filled[:2] + filled[-2:]

    def heading(line: str) -> bool:  # the same place can start many pages
        line = line.strip()
        if "CONTINUED" in line.upper():
            return False
        return bool(NUMBERED.match(line) or SCENE_PREFIX.match(re.sub(r"^\S*\d\S*\s+", "", line)))

    counts: Counter[str] = Counter()
    for page in pages:
        counts.update({_running_key(page[i]) for i in edges(page) if not heading(page[i])})
    # Headers carry a page number, a date or a revision; a line without one
    # (a character's name at the top of many pages) only counts if it is on
    # almost every page.
    running = {
        key for key, n in counts.items()
        if len(key) > 3 and not PAGE_NUMBER.match(key.replace("#", "1"))
        and n >= (max(3, len(pages) * 0.3) if "#" in key else len(pages) * 0.8)
    }
    for page in pages:
        for i in edges(page):
            if _running_key(page[i]) in running:
                page[i] = ""


def _page_shift(page: list[str], columns: _Columns) -> int:
    """How far this page's text sits from the script's columns. Scanned pages
    can each be a little to the left or right, some by a whole margin.

    The shift that lines up most of the page's lines with the script's
    columns wins; ties go to the smallest shift."""
    indents = [len(raw) - len(raw.lstrip()) for raw in page if raw.strip()]
    if len(indents) < 5:
        return 0
    stops = (columns.action, columns.dialogue, columns.cue)

    def fit(by: int) -> int:
        return sum(1 for i in indents if any(abs(i - by - stop) <= 1 for stop in stops))

    best = max(range(-25, 26), key=lambda by: (fit(by), -abs(by)))
    # Long lines are action, so the leftmost column where they start is the
    # margin, if the page agrees (on a page of dialogue the long lines can be
    # speeches). The best fit alone can be fooled: a page of dialogue lines
    # up well with the wrong columns too.
    wide = Counter(
        len(raw) - len(raw.lstrip()) for raw in page
        if len(_squeeze(raw)) >= 45 and not re.match(r"\s*\d+[A-Z]{0,2}\s{2,}", raw)
    )
    margins = [i for i, n in wide.items() if n >= 2]
    if margins:
        hint = min(margins) - columns.action
        # Near the script's margin, or confirmed by cues where that margin puts them.
        cues = sum(1 for i in indents if abs(i - hint - columns.cue) <= 1)
        if abs(hint) <= 3 or cues >= 2:
            return hint
    return best


def _unmark(raw: str) -> str:
    """A scan can leave a stray mark at the page edge ("I     stacks of linen"):
    blank it so the line keeps its real indentation."""
    m = MARGIN_MARK.match(raw)
    return " " * m.end() + raw[m.end():] if m else raw


def _trailing_cue(s: str, names: re.Pattern | None) -> tuple[str, str] | None:
    """Some PDFs put a character's name at the end of their first line of
    dialogue ("What do we know? GORDON"). Returns (cue, dialogue) if so."""
    if names is None:
        return None
    tail = s.split()[-1]
    if not (re.search(r"[A-Z]{2,}[^a-z]*$", tail) or tail.endswith(")") or tail.endswith("(")):
        return None  # quick no: the line doesn't end in capitals
    m = names.search(s)
    if not m or not s[: m.start()].strip(" -") or _caps(s[: m.start()]):
        return None
    extension = m.group(2) or ""
    cue = m.group(1) + (extension if extension.rstrip().endswith(")") else "")
    return _squeeze(cue), s[: m.start()].rstrip()


def _title_page(page: str) -> list[str]:
    lines = [_squeeze(line) for line in page.splitlines() if line.strip()]
    if not lines:
        return []
    byline = next((i for i, line in enumerate(lines) if line.lower() in BYLINES), len(lines))
    # The title is the first line in capitals before the byline (JOKER, not
    # its tagline "an origin"), skipping revision dates.
    candidates = [line for line in lines[:byline] if not REVISION.search(line)] or lines[:1]
    first = next((i for i, line in enumerate(candidates) if _caps(line)), 0)
    # A title in capitals can run onto the next line: STAR WARS / EPISODE III: ...
    parts = [candidates[first]]
    for line in candidates[first + 1:]:
        if not _caps(line) or len(parts) == 3:
            break
        parts.append(line)
    title = " - ".join(parts)
    fields = [f"Title: {title}"]
    if byline + 1 < len(lines):
        fields.append(f"Credit: {lines[byline]}")
        fields.append(f"Author: {lines[byline + 1]}")
    # Contact details are skipped on purpose: a breakdown doesn't need them.
    return fields


def pdf_text_to_fountain(text: str) -> str:
    """Convert layout-preserving text from a screenplay PDF to Fountain.

    Pages must be separated by form feeds (\\f).
    """
    pages = text.split("\f")
    header: list[str] = []
    first = [_squeeze(line) for line in pages[0].splitlines()] if pages else []
    # A title page has no scene headings, and a byline or only a few lines
    # (some have nothing but the title).
    words = [line for line in first if line]
    title_only = 0 < len(words) <= 12 and not any(
        line[:1].islower() or "CONT'D" in line or "(MORE)" in line for line in words  # a short page of script isn't one
    )
    if (any(line.lower() in BYLINES for line in first) or title_only) \
            and not any(SCENE_PREFIX.match(line) for line in first):
        header = _title_page(pages[0])
        pages = pages[1:]

    page_lines = [[_dual_cue(_misread_letters(_unmark(raw))) for raw in page.splitlines()] for page in pages]
    _drop_running_lines(page_lines)
    known_headings = _recover_headings(page_lines)
    columns = _columns([raw for page in page_lines for raw in page])
    shifted = [columns.shifted(_page_shift(page, columns)) for page in page_lines]
    lines = [(raw, cols) for page, cols in zip(page_lines, shifted) for raw in page]

    # Every name used as a cue, to find the ones a PDF moves onto a line of dialogue.
    known = {
        CUE_BASE.sub("", REVISION_MARKS.sub("", LEADING_JUNK.sub("", _squeeze(raw)))).strip()
        for raw, cols in lines
        if raw.strip() and cols.kind(len(raw) - len(raw.lstrip()), raw.strip()) == "cue"
    }
    # Names that end the first line of a speech more than once are cues the
    # PDF moved there, even in a script where no cue stands on its own line.
    trailing: Counter[str] = Counter()
    previous = ""
    for raw, cols in lines:
        s = raw.strip()
        if not s:
            previous = ""  # a blank line ends a speech
            continue
        kind = cols.kind(len(raw) - len(raw.lstrip()), s)
        if kind == "dialogue" and previous != "dialogue":
            m = TRAILING_NAME.search(_squeeze(s))
            if m and s[: m.start()].strip(" -") and not _caps(_squeeze(s)[: m.start()]):
                name = REVISION_MARKS.sub("", m.group(1)).strip()
                name = re.sub(r"^(?:[A-Z] )+", "", name)  # "...and I HENRY": the pronoun isn't part of the name
                trailing[name] += 1
        previous = kind
    known |= {n for n, count in trailing.items() if count >= 2 and n not in NOT_NAMES}
    known = sorted((n for n in known if len(n) >= 3 and not CONTINUED_HEADER.search(n)), key=len, reverse=True)
    names = re.compile(r"(?:(?<=[\s.?!,;:)\-\"'…’]))(" + "|".join(map(re.escape, known)) + r")(\s*\([^)]*\)?)?\s*$") if known else None
    out: list[str] = []
    last = ""  # kind of the last line written
    last_cue = ""
    more = False  # dialogue continues on the next page
    cues: list[int] = []  # where character cues are in `out`

    for raw, columns in lines:
        s = raw.strip()
        if not s:
            out.append("")
            continue
        if s.lower() in PLACEHOLDERS:
            continue
        indent = len(raw) - len(raw.lstrip())

        if DATED_HEADER.match(_squeeze(s)):
            continue
        numbered = NUMBERED.match(s) if indent < columns.kind_limit() else None
        if numbered and indent >= columns.action - 1:
            # At the action margin, "1   EXT. SPACE" is a numbered heading; any other
            # line that starts with a number ("2   men walk in") is just action.
            rest = _squeeze(numbered.group(2))
            number = numbered.group(1)
            rest = re.sub(rf"^\d{{1,4}} (?={re.escape(number)})", "", rest)
            twice = rest.startswith(number) and not rest[len(number):len(number) + 1].isdigit() \
                and _caps(rest[len(number):])  # "128   128THE NEWPORT FESTIVAL": the number on both sides
            if not (SCENE_PREFIX.match(rest) or SCENE_PREFIX.match(rest[len(number):]) or twice or OMITTED.match(rest)):
                numbered = None
        if numbered:
            number, rest = numbered.group(1), _squeeze(numbered.group(2))
            rest = re.sub(rf"^\d{{1,4}} (?={re.escape(number)})", "", rest)
            # The number on the right can come out glued in front of the text:
            # "128   128THE NEWPORT FOLK FESTIVAL". It still counts as numbered
            # on both sides.
            glued = rest.startswith(number) and not rest[len(number):len(number) + 1].isdigit()
            if glued:
                rest = rest[len(number):].lstrip()
            if not rest:
                continue  # just the scene number, twice: nothing to read
            if OMITTED.match(rest):
                out += ["", f"[[OMITTED {number}]]", ""]
                continue
            if CONTINUED.match(rest) or CONTINUED_HEADER.search(rest) or _continued_like(rest):
                continue
            # Scan specks in a heading ("INT. CAIURONI • S CAR ._ NIM ·"): cleaned.
            if HEADING_SPECKS.search(rest):
                rest = _clean_heading(rest, known_headings) or rest
            # Numbered on both sides, it is a heading even without INT./EXT.
            forced = "" if SCENE_PREFIX.match(rest) else "."
            if forced:
                rest = rest.rstrip(" :") or rest  # "BACKSTAGE :"
                # "94...HE BRINGS THE BOX": dots after a forced "." would hide the heading.
                rest = re.sub(r"^[.…\s]+", "", rest) or rest
            marks = rest.replace(" ", "")
            garbled = sum(c.isalnum() for c in marks) < len(marks) * 0.6  # a smudge, not words
            both_sides = glued or numbered.group(0).rstrip().endswith(number)
            if forced and not both_sides or not _caps(rest) or garbled:
                s, indent = rest, columns.action  # just a line that starts with a number
            else:
                out += ["", f"{forced}{rest} #{number}#", ""]
                last = "heading"
                continue

        if CONTINUED.match(_squeeze(s)) or (_caps(s) and CONTINUED_HEADER.search(s)):
            continue
        marks = s.replace(" ", "")
        if not any(c.isalnum() for c in marks) and set(marks) - SPEECH_MARKS:
            continue  # a stray bracket or smudge from the scan        if sum(c.isalnum() for c in marks) < len(marks) * 0.4 and (len(marks) > 12 or NOISE & set(marks)):
            continue  # scanning noise, not words ("1...2...3." is kept)
        if MORE.match(_squeeze(s)):
            more = True
            continue
        kind = columns.kind(indent, s)
        if last == "parenthetical" and out[-1].startswith("(") and not out[-1].endswith(")") and kind != "cue":
            kind = "parenthetical"  # the rest of a parenthetical that runs onto a second line
        s = REVISION_MARKS.sub("", _squeeze(s)) or s  # revision stars in the margin: "See ya. ******"
        if not s:
            continue
        if s[0] == "{":  # a scanned parenthesis
            s = "(" + s[1:]

        if kind == "right":
            if PAGE_NUMBER.match(s):
                continue
            out += ["", f"> {s}", ""]
            last = "transition"
            continue

        if kind == "cue" and s.endswith(":"):
            out += ["", f"> {s}", ""]  # a transition a scan moved to the cue column
            last = "transition"
            continue
        if kind == "cue":
            s = REVISION_MARKS.sub("", LEADING_JUNK.sub("", s))
            base = CUE_BASE.sub("", s)
            if more and base == last_cue:
                # "NAME (CONT'D)" repeated after a page break: keep one block.
                while out and not out[-1]:
                    out.pop()
                more = False
                continue
            more = False
            cues.append(len(out))
            out.append(s)
            last_cue, last = base, "cue"
        elif kind == "parenthetical":
            if last == "parenthetical" and out[-1].startswith("(") and not out[-1].endswith(")"):
                out[-1] += " " + s
                last = "parenthetical"
            elif s.startswith("("):
                out.append(s)
                last = "parenthetical"
            elif last in ("cue", "dialogue", "parenthetical"):
                # Indented further than dialogue but not a cue: still the speech.
                out.append(s)
                last = "dialogue"
            else:
                # Centred text in the action (titles, signs, on-screen text): one line each.
                out.append(s)
                last = "centred"
        elif kind == "dialogue":
            split = _trailing_cue(s, names)
            if split:
                cue, s = split
                out += ["", cue]
                cues.append(len(out) - 1)
                last_cue = CUE_BASE.sub("", cue)
            out.append(s)
            last = "dialogue"
        elif SCENE_PREFIX.match(s):
            # On its own paragraph: some PDFs put no blank line between a
            # heading and the action around it, and Fountain needs one.
            out += ["", s, ""]
            last = "heading"
        elif last == "action" and out[-1]:
            # Same paragraph, wrapped by the PDF layout.
            out[-1] += " " + s
        else:
            # Force all-caps action (KNOCK KNOCK, BLACKOUT...) so it isn't read as a
            # cue, and action that starts with a dot so it isn't read as a heading.
            out.append(f"!{s}" if s.isupper() or (s.startswith(".") and not s.startswith("...")) else s)
            last = "action"

    _join_split_cues(out, cues)
    # A "heading" that is mostly smudges is scanning noise: kept as action, not a scene.
    for i, line in enumerate(out):
        heading = line.startswith(".") and not line.startswith("..") or SCENE_PREFIX.match(line)
        body = SCENE_NUMBER_MARK.sub("", line).lstrip(".")
        marks = body.replace(" ", "")
        if heading and marks and sum(c.isalnum() for c in marks) < len(marks) * 0.6:
            out[i] = "!" + body
        elif line.startswith("..") and not line.startswith("...") and sum(c.isalnum() for c in marks) < len(marks) * 0.6:
            out[i] = "!" + line
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    if header:
        return "\n".join(header) + "\n\n" + body + "\n"
    return body + "\n"


# What a scan leaves at the end of a name: dashes, dots in the middle of a
# line, tildes, quotes, soft hyphens. A full stop is kept (MR., JR.).
NAME_TAIL_JUNK = re.compile(r"[\s\-–—·•~_,:;*`\"\u00ad]+$")
# Characters a real cue doesn't have: a name with any of them was misread.
# Accented capitals are letters (JOSÉ, ÁNGELA, MAÎTRE D').
SCAN_CHARACTERS = re.compile(r"[^A-Z0-9ÁÉÍÓÚÜÑÀÈÌÒÙÂÊÎÔÛÄËÏÖÇ .'’#&/()\-]")


def _letters_only(name: str) -> str:
    """The letters of a name without accents, to compare spellings."""
    plain = unicodedata.normalize("NFKD", name.upper())
    return re.sub(r"[^A-Z]", "", "".join(c for c in plain if not unicodedata.combining(c)))


def _join_split_cues(out: list[str], cues: list[int]) -> None:
    """Put right the names a PDF garbles, so each character is counted once.

    - Junk a scan leaves after a name goes ("ANAKIN---", "OBI-WAN·").
    - Letters spaced out by the extraction ("M ARTY") join the spelling the
      script uses most.
    - A name with characters no cue has ("GENBR.'\\.L GRIEVOUS") becomes the
      much more frequent name it is closest to, if it is clearly that one.
    - A "cue" that is a transition (CUT TO:) becomes a transition, and one
      that is mostly smudges stops being a character.
    Only misread names are changed: two real names that look alike (MAN 1,
    MAN 2) are left for the formatting notes to point out."""
    def split(line: str) -> tuple[str, str]:
        text = line.strip()
        base = CUE_BASE.sub("", text).strip()
        return base, text[len(base):]

    for i in cues:
        base, rest = split(out[i])
        clean = NAME_TAIL_JUNK.sub("", base) or base
        if clean.endswith(":") or base.endswith(":"):
            out[i] = "> " + base  # CUT TO:, misread as a cue
            continue
        if SCAN_CHARACTERS.search(clean) and sum(c.isalpha() for c in clean) < len(clean.replace(" ", "")) * 0.6:
            out[i] = "!" + out[i].strip()  # a smudge, kept as action so nothing is lost (P.A. is not one)
            continue
        out[i] = clean + rest
    cues[:] = [i for i in cues if not out[i].startswith(("> ", "!"))]

    counts: dict[str, dict[str, int]] = {}
    for i in cues:
        base, _ = split(out[i])
        spellings = counts.setdefault(base.replace(" ", ""), {})
        spellings[base] = spellings.get(base, 0) + 1
    for i in cues:
        base, rest = split(out[i])
        spellings = counts[base.replace(" ", "")]
        best = max(spellings, key=lambda name: (spellings[name], -name.count(" ")))
        if best != base and spellings[best] > spellings[base]:
            out[i] = best + rest

    totals: Counter[str] = Counter(split(out[i])[0] for i in cues)
    frequent = [name for name, n in totals.items() if n >= 3 and not SCAN_CHARACTERS.search(name)]
    for i in cues:
        base, rest = split(out[i])
        if not SCAN_CHARACTERS.search(base) or not frequent:
            continue
        letters = _letters_only(base)
        score, best = max((SequenceMatcher(None, letters, _letters_only(name)).ratio(), name) for name in frequent)
        if score >= 0.6:
            out[i] = best + rest


def pdf_to_fountain(path: str | Path | BinaryIO) -> str:
    """Read a screenplay PDF (a path or an open binary file) and return it as
    Fountain text. Needs `pypdf`."""
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise RuntimeError("PDF support needs pypdf: pip install 'slugline[pdf]'") from e
    from pypdf.errors import PyPdfError

    try:
        reader = PdfReader(path if hasattr(path, "read") else str(path))
        text = "\f".join(p.extract_text(extraction_mode="layout") for p in reader.pages)
    except PyPdfError as e:
        name = "the file" if hasattr(path, "read") else path
        raise RuntimeError(f"cannot read {name} as a PDF: {e}") from e
    if is_scanned(text):
        text = _ocr(path, text)
    return pdf_text_to_fountain(text)


def is_scanned(text: str) -> bool:
    """A PDF of pictures: next to no text on its pages."""
    pages = text.split("\f")
    return len(re.sub(r"\s", "", text)) < 40 * max(1, len(pages))


def _ocr(path: str | Path | BinaryIO, text: str) -> str:
    """Read a scanned PDF with the Mac's own text recognition."""
    from slugline import ocr

    if not ocr.available():
        raise RuntimeError(
            "This PDF is a scan: its pages are pictures, with no text to read. "
            "Slugline reads scans with the text recognition built into macOS; it is not available here."
        )
    if hasattr(path, "read"):  # Vision reads from a file
        import tempfile

        path.seek(0)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(path.read())
        try:
            return ocr.pdf_text(f.name)
        finally:
            Path(f.name).unlink(missing_ok=True)
    return ocr.pdf_text(path)
