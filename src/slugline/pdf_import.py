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

from slugline.parser import SCENE_PREFIX

PAGE_NUMBER = re.compile(r"^\d+\.?$")
CUE_BASE = re.compile(r"\s*\(.*$")
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

    page_lines = [[_unmark(raw) for raw in page.splitlines()] for page in pages]
    _drop_running_lines(page_lines)
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
            if not (SCENE_PREFIX.match(rest) or SCENE_PREFIX.match(rest[len(number):]) or twice):
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
            if CONTINUED.match(rest) or CONTINUED_HEADER.search(rest):
                continue
            # Numbered on both sides, it is a heading even without INT./EXT.
            forced = "" if SCENE_PREFIX.match(rest) else "."
            if forced:
                rest = rest.rstrip(" :") or rest  # "BACKSTAGE :"
            marks = rest.replace(" ", "")
            garbled = sum(c.isalpha() for c in marks) < len(marks) * 0.6  # a smudge, not words
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
        if heading and marks and sum(c.isalpha() for c in marks) < len(marks) * 0.6:
            out[i] = "!" + body
        elif line.startswith("..") and not line.startswith("...") and sum(c.isalpha() for c in marks) < len(marks) * 0.6:
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
    return pdf_text_to_fountain(text)
