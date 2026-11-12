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
from collections import Counter
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
NUMBERED = re.compile(r"^(\d{1,4}[A-Z]{0,2})\s{2,}(\S.*?)(?:\s{2,}\1)?$")
# Page-break noise: (CONTINUED), CONTINUED: (2), (CONT'D), and the same scanned
# with braces or cut short at the page edge.
CONTINUED = re.compile(r"^[({]?\s*CONT(INUED|'D)?\s*[:)}]?\s*([({]\s*\d+\s*[)}])?$", re.IGNORECASE)
MORE = re.compile(r"^[({]\s*MORE\s*[)}]$", re.IGNORECASE)
LETTERS = re.compile(r"[A-Za-z]")
REVISION = re.compile(r"^rev\b|\d{1,2}/\d{1,2}/\d{2,4}|draft", re.IGNORECASE)
# A page header with CONTINUED in it, such as "02/09/20 CONTINUED: 58.", spaced out or not.
CONTINUED_HEADER = re.compile(r"C\s?O\s?N\s?T\s?I\s?N\s?U\s?E\s?D\s?:")
# Revision stars at the end of a line and stray marks a scan leaves before a name.
REVISION_MARKS = re.compile(r"(\s+\*)+\s*$")
LEADING_JUNK = re.compile(r"^[^A-Za-z0-9(\"']+")
# Revision page headers: "02/09/20 (White February Shooting Script) 3." or
# "3 02/09/20 CONTINUED: (2)".
DATED_HEADER = re.compile(
    r"^(\d+[A-Z]?\s+)?\d{1,2}/\d{1,2}/\d{2,4}\s*(\(|C\s?O\s?N|$)"  # 02/09/20 (White ...) 3.
    r"|^(\w+\s+)?Rev\.\s*\("  # Green Rev. (mm/dd/yy) 157.
)
MARGIN_MARK = re.compile(r"^\s*[Il|!.,'`]\s{5,}(?=\S)")
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
    # The left margin is the leftmost column most lines use (scene numbers
    # sit further left, but there are few of them).
    floor = max(1, len(rows) // 50)
    action = min((i for i, n in indents.items() if n >= floor), default=min(indents))
    speech = Counter(i for i, s in rows if i > action + 3 and not _caps(s) and s[0] not in "({")
    dialogue = speech.most_common(1)[0][0] if speech else action + 12
    names = Counter(i for i, s in rows if i > dialogue + 3 and _caps(s) and len(s) < 40 and not s.endswith(":"))
    cue = names.most_common(1)[0][0] if names else dialogue + 13
    return _Columns(action, dialogue, cue)


def _page_shift(page: list[str], columns: _Columns) -> int:
    """How far this page's text sits from the script's columns. Scanned pages
    can each be a little to the left or right; the shift that lines up most
    lines with the script's columns is the page's."""
    indents = [len(raw) - len(raw.lstrip()) for raw in page if raw.strip()]
    if len(indents) < 5:
        return 0
    stops = (columns.action, columns.dialogue, columns.cue)

    def fit(by: int) -> int:
        return sum(1 for i in indents if any(abs(i - by - stop) <= 1 for stop in stops))

    return max(range(-30, 31), key=lambda by: (fit(by), -abs(by)))


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
    if not (_caps(tail) or tail.endswith(")") or tail.endswith("(")):
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
    title = next((line for line in candidates if _caps(line)), candidates[0])
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
    # A title page has a byline and no scene headings.
    if any(line.lower() in BYLINES for line in first) and not any(SCENE_PREFIX.match(line) for line in first):
        header = _title_page(pages[0])
        pages = pages[1:]

    page_lines = [[_unmark(raw) for raw in page.splitlines()] for page in pages]
    columns = _columns([raw for page in page_lines for raw in page])
    shifted = [columns.shifted(_page_shift(page, columns)) for page in page_lines]
    lines = [(raw, cols) for page, cols in zip(page_lines, shifted) for raw in page]

    # Every name used as a cue, to find the ones a PDF moves onto a line of dialogue.
    known = {
        CUE_BASE.sub("", REVISION_MARKS.sub("", LEADING_JUNK.sub("", _squeeze(raw)))).strip()
        for raw, cols in lines
        if raw.strip() and cols.kind(len(raw) - len(raw.lstrip()), raw.strip()) == "cue"
    }
    known = sorted((n for n in known if len(n) >= 3 and not CONTINUED_HEADER.search(n)), key=len, reverse=True)
    names = re.compile(r"(?:(?<=\s)|(?<=--))(" + "|".join(map(re.escape, known)) + r")(\s*\([^)]*\)?)?\s*$") if known else None
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
        numbered = NUMBERED.match(s) if indent < columns.action else None
        if numbered:
            number, rest = numbered.group(1), _squeeze(numbered.group(2))
            if rest.startswith(number) and SCENE_PREFIX.match(rest[len(number):]):
                rest = rest[len(number):]  # "168A 168AINT. DEN": the number printed twice
            if CONTINUED.match(rest) or CONTINUED_HEADER.search(rest):
                continue
            # Numbered on both sides, it is a heading even without INT./EXT.
            forced = "" if SCENE_PREFIX.match(rest) else "."
            if forced and not numbered.group(0).rstrip().endswith(number) or not _caps(rest):
                s, indent = rest, columns.action  # just a line that starts with a number
            else:
                out += ["", f"{forced}{rest} #{number}#", ""]
                last = "heading"
                continue

        if CONTINUED.match(_squeeze(s)) or (_caps(s) and CONTINUED_HEADER.search(s)):
            continue
        marks = s.replace(" ", "")
        if sum(c.isalnum() for c in marks) < len(marks) * 0.4 and (len(marks) > 12 or NOISE & set(marks)):
            continue  # scanning noise, not words ("1...2...3." is kept)
        if MORE.match(_squeeze(s)):
            more = True
            continue
        kind = columns.kind(indent, s)
        if last == "parenthetical" and out[-1].startswith("(") and not out[-1].endswith(")") and kind != "cue":
            kind = "parenthetical"  # the rest of a parenthetical that runs onto a second line
        s = _squeeze(s)
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
            out.append(s)
            last = "heading"
        elif last == "action" and out[-1]:
            # Same paragraph, wrapped by the PDF layout.
            out[-1] += " " + s
        else:
            # Force all-caps action (KNOCK KNOCK, BLACKOUT...) so it isn't read as a
            # cue, and action that starts with a dot so it isn't read as a heading.
            out.append(f"!{s}" if s.isupper() or (s.startswith(".") and not s.startswith("..")) else s)
            last = "action"

    _join_split_cues(out, cues)
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    if header:
        return "\n".join(header) + "\n\n" + body + "\n"
    return body + "\n"


def _join_split_cues(out: list[str], cues: list[int]) -> None:
    """Some PDFs space out the letters of a name ("M ARTY" for "MARTY") when
    the text is extracted. A cue that, without spaces, is a name used more
    often elsewhere is written that way."""
    counts: dict[str, dict[str, int]] = {}
    for i in cues:
        base = CUE_BASE.sub("", out[i]).strip()
        spellings = counts.setdefault(base.replace(" ", ""), {})
        spellings[base] = spellings.get(base, 0) + 1
    for i in cues:
        base = CUE_BASE.sub("", out[i]).strip()
        spellings = counts[base.replace(" ", "")]
        best = max(spellings, key=lambda name: (spellings[name], -name.count(" ")))
        if best != base and spellings[best] > spellings[base]:
            out[i] = best + out[i].strip()[len(base):]


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
