"""Convert a PDF screenplay to Fountain.

Screenplay PDFs keep the industry layout, so the left indentation of each line
tells us what it is (in characters, as extracted by pypdf's layout mode):

    0-5    action and scene headings
    6-15   dialogue
    16-21  parentheticals
    22-39  character cues
    40+    transitions and page numbers

The conversion works on the extracted text, so it can be tested without a PDF.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import BinaryIO

from slugline.parser import SCENE_PREFIX

PAGE_NUMBER = re.compile(r"^\d+\.?$")
CUE_BASE = re.compile(r"\s*\(.*$")
# Title page placeholders that templates leave behind; they are not real data.
PLACEHOLDERS = {"address", "phone", "e-mail", "email", "contact"}
BYLINES = {"written by", "by", "screenplay by"}


def _kind(indent: int) -> str:
    if indent <= 5:
        return "action"
    if indent <= 15:
        return "dialogue"
    if indent <= 21:
        return "parenthetical"
    if indent <= 39:
        return "cue"
    return "right"


def _title_page(page: str) -> list[str]:
    lines = [line.strip() for line in page.splitlines() if line.strip()]
    if not lines:
        return []
    fields = [f"Title: {lines[0]}"]
    for i, line in enumerate(lines[1:], start=1):
        if line.lower() in BYLINES and i + 1 < len(lines):
            fields.append(f"Credit: {line}")
            fields.append(f"Author: {lines[i + 1]}")
            break
    # Contact details are skipped on purpose: a breakdown doesn't need them.
    return fields


def pdf_text_to_fountain(text: str) -> str:
    """Convert layout-preserving text from a screenplay PDF to Fountain.

    Pages must be separated by form feeds (\\f).
    """
    pages = text.split("\f")
    header: list[str] = []
    first = [line.strip() for line in pages[0].splitlines()] if pages else []
    # A title page has a byline and no scene headings.
    if any(line.lower() in BYLINES for line in first) and not any(SCENE_PREFIX.match(line) for line in first):
        header = _title_page(pages[0])
        pages = pages[1:]

    out: list[str] = []
    last = ""  # kind of the last line written
    last_cue = ""
    more = False  # dialogue continues on the next page
    cues: list[int] = []  # where character cues are in `out`

    for raw in "\n".join(pages).splitlines():
        s = raw.strip()
        if not s:
            out.append("")
            continue
        if s.lower() in PLACEHOLDERS:
            continue
        indent = len(raw) - len(raw.lstrip())
        kind = _kind(indent)

        if kind == "right":
            if PAGE_NUMBER.match(s):
                continue
            out += ["", f"> {s}", ""]
            last = "transition"
            continue

        if s == "(MORE)":
            more = True
            continue

        if kind == "cue":
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
            if last == "parenthetical" and out[-1] and not out[-1].endswith(")"):
                out[-1] += " " + s
            else:
                out.append(s)
            last = "parenthetical"
        elif kind == "dialogue":
            out.append(s)
            last = "dialogue"
        elif SCENE_PREFIX.match(s):
            out.append(s)
            last = "heading"
        elif last == "action" and out[-1]:
            # Same paragraph, wrapped by the PDF layout.
            out[-1] += " " + s
        else:
            # Force all-caps action (KNOCK KNOCK, BLACKOUT...) so it isn't read as a cue.
            out.append(f"!{s}" if s.isupper() else s)
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
