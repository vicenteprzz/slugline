"""Fountain screenplay parser.

Fountain (https://fountain.io/syntax) is plain text: the type of each element
is decided by the line itself, whether a blank line comes before it, and what
comes after it. This parser implements the subset needed for a production
breakdown: title page, scene headings, action, character + dialogue,
parentheticals and transitions. Notes, boneyard, sections and synopses are
stripped because they never reach the printed page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

# A scene heading starts with one of these, followed by a dot or a space.
SCENE_PREFIX = re.compile(r"^(?:INT\.?/EXT|INT/EXT|I/E|INT|EXT|EST)[.\s]", re.IGNORECASE)
HEADING_PARTS = re.compile(r"^(INT\.?/EXT|INT/EXT|I/E|INT|EXT|EST)\.?\s*", re.IGNORECASE)
SCENE_NUMBER = re.compile(r"\s*#([\w.\-]+)#\s*$")
# Location and time are separated by a dash surrounded by spaces: "HOUSE - NIGHT".
TIME_SEPARATOR = re.compile(r"\s+[-–—]\s+")
EXTENSION = re.compile(r"\(([^)]*)\)")
TITLE_KEY = re.compile(r"^([A-Za-z][A-Za-z ]*):\s*(.*)$")
NOTE = re.compile(r"\[\[.*?\]\]", re.DOTALL)
BONEYARD = re.compile(r"/\*.*?\*/", re.DOTALL)

# Rough layout of a printed page in standard screenplay format.
LINES_PER_PAGE = 55
ACTION_WIDTH = 60
DIALOGUE_WIDTH = 35
PARENTHETICAL_WIDTH = 25


@dataclass
class Action:
    text: str


@dataclass
class Transition:
    text: str


@dataclass
class Dialogue:
    character: str
    extensions: list[str] = field(default_factory=list)
    parentheticals: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    dual: bool = False

    @property
    def text(self) -> str:
        return " ".join(self.lines)

    @property
    def word_count(self) -> int:
        return len(self.text.split())


Element = Union[Action, Dialogue, Transition]


@dataclass
class Scene:
    index: int
    heading: str
    int_ext: str | None = None
    location: str = ""
    time_of_day: str | None = None
    scene_number: str | None = None
    elements: list[Element] = field(default_factory=list)

    @property
    def number(self) -> str:
        """The script's own scene number if it has one, else the position."""
        return self.scene_number or str(self.index)

    @property
    def dialogues(self) -> list[Dialogue]:
        return [e for e in self.elements if isinstance(e, Dialogue)]

    @property
    def characters(self) -> list[str]:
        """Speaking characters, in order of first appearance."""
        seen: dict[str, None] = {}
        for d in self.dialogues:
            seen.setdefault(d.character, None)
        return list(seen)

    @property
    def printed_lines(self) -> int:
        """Estimated number of lines this scene takes on the printed page."""
        total = 2  # heading + the blank line after it
        for e in self.elements:
            if isinstance(e, Action):
                total += sum(_wrapped(p, ACTION_WIDTH) for p in e.text.split("\n")) + 1
            elif isinstance(e, Transition):
                total += 2
            else:
                total += 1  # character cue
                total += sum(_wrapped(p, PARENTHETICAL_WIDTH) for p in e.parentheticals)
                total += sum(_wrapped(line, DIALOGUE_WIDTH) for line in e.lines) + 1
        return total

    @property
    def eighths(self) -> int:
        """Estimated length in eighths of a page (minimum 1, as on a stripboard)."""
        return max(1, round(self.printed_lines / LINES_PER_PAGE * 8))


@dataclass
class Screenplay:
    title_page: dict[str, str] = field(default_factory=dict)
    scenes: list[Scene] = field(default_factory=list)
    # Elements that come before the first scene heading (cold opens, titles...).
    preamble: list[Element] = field(default_factory=list)

    @property
    def title(self) -> str | None:
        return self.title_page.get("title")

    @property
    def page_count(self) -> float:
        return sum(s.printed_lines for s in self.scenes) / LINES_PER_PAGE


def _wrapped(text: str, width: int) -> int:
    """How many printed lines a paragraph needs at the given width."""
    if not text:
        return 1
    return max(1, -(-len(text) // width))


def format_eighths(eighths: int) -> str:
    """Format a length in eighths the way production boards do: 1 3/8, 4/8..."""
    pages, rest = divmod(eighths, 8)
    if pages and rest:
        return f"{pages} {rest}/8"
    if pages:
        return str(pages)
    return f"{rest}/8"


def parse_heading(text: str) -> tuple[str | None, str, str | None]:
    """Split a scene heading into (int_ext, location, time_of_day).

    >>> parse_heading("INT. SALOON - NIGHT")
    ('INT', 'SALOON', 'NIGHT')
    >>> parse_heading("EXT. RANCH - CORRAL - DAY")
    ('EXT', 'RANCH - CORRAL', 'DAY')
    """
    int_ext = None
    rest = text.strip()
    m = HEADING_PARTS.match(rest)
    if m:
        prefix = m.group(1).upper().replace(".", "")
        int_ext = "INT/EXT" if prefix in ("INT/EXT", "I/E") else prefix
        rest = rest[m.end():]
    parts = TIME_SEPARATOR.split(rest)
    if len(parts) > 1:
        return int_ext, " - ".join(parts[:-1]).strip(), parts[-1].strip().upper()
    return int_ext, rest.strip(), None


def _strip_invisible(text: str) -> str:
    """Remove notes and boneyard, which never appear in the printed script."""
    text = BONEYARD.sub("", text)
    return NOTE.sub("", text)


def _parse_title_page(lines: list[str]) -> tuple[dict[str, str], int]:
    """Parse the optional title page. Returns (fields, index of first body line)."""
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines) or not TITLE_KEY.match(lines[i]):
        return {}, 0

    fields: dict[str, str] = {}
    key = None
    while i < len(lines) and lines[i].strip():
        line = lines[i]
        m = TITLE_KEY.match(line)
        if m and not line[0].isspace():
            key = m.group(1).strip().lower()
            fields[key] = m.group(2).strip()
        elif key is not None:
            # Indented continuation line of a multi-line value.
            fields[key] = (fields[key] + "\n" + line.strip()).strip()
        i += 1
    return fields, i


def _is_scene_heading(line: str) -> bool:
    if line.startswith(".") and not line.startswith(".."):
        return True
    return bool(SCENE_PREFIX.match(line))


def _is_transition(line: str, next_line: str) -> bool:
    if line.startswith(">"):
        return not line.endswith("<")  # >CENTERED< is action, not a transition
    return line.isupper() and line.endswith("TO:") and not next_line


def _character_name(line: str) -> tuple[str, list[str], bool] | None:
    """If the line is a character cue, return (name, extensions, dual)."""
    if line.startswith("!"):  # forced action, even if it's all caps
        return None
    forced = line.startswith("@")
    cue = line[1:] if forced else line
    dual = cue.rstrip().endswith("^")
    if dual:
        cue = cue.rstrip()[:-1]
    extensions = [e.strip() for e in EXTENSION.findall(cue)]
    name = EXTENSION.sub("", cue).strip()
    if not name:
        return None
    if not forced and (name != name.upper() or not any(c.isalpha() for c in name)):
        return None
    return name, extensions, dual


def parse(text: str) -> Screenplay:
    """Parse Fountain text into a Screenplay."""
    lines = _strip_invisible(text.replace("\r\n", "\n")).split("\n")
    title_page, i = _parse_title_page(lines)
    play = Screenplay(title_page=title_page)
    current: list[Element] = play.preamble
    prev_blank = True
    n = len(lines)

    while i < n:
        line = lines[i].strip()
        if not line:
            prev_blank = True
            i += 1
            continue
        next_line = lines[i + 1].strip() if i + 1 < n else ""

        # Sections (#), synopses (=) and page breaks (===) are not printed.
        if prev_blank and line.startswith(("#", "=")):
            i += 1
            continue

        if prev_blank and _is_scene_heading(line):
            heading = line[1:] if line.startswith(".") else line
            scene_number = None
            m = SCENE_NUMBER.search(heading)
            if m:
                scene_number = m.group(1)
                heading = heading[: m.start()]
            int_ext, location, time = parse_heading(heading)
            scene = Scene(
                index=len(play.scenes) + 1,
                heading=heading.strip().upper(),
                int_ext=int_ext,
                location=location.upper(),
                time_of_day=time,
                scene_number=scene_number,
            )
            play.scenes.append(scene)
            current = scene.elements
            i += 1
            continue

        if prev_blank and _is_transition(line, next_line):
            current.append(Transition(line.lstrip(">").strip()))
            i += 1
            continue

        cue = _character_name(line) if prev_blank and next_line else None
        if cue is not None:
            name, extensions, dual = cue
            block = Dialogue(character=name, extensions=extensions, dual=dual)
            i += 1
            while i < n and lines[i].strip():
                part = lines[i].strip()
                if part.startswith("(") and part.endswith(")"):
                    block.parentheticals.append(part)
                else:
                    block.lines.append(part)
                i += 1
            current.append(block)
            continue

        # Anything else is action: take the whole paragraph up to the next blank line.
        paragraph = []
        while i < n and lines[i].strip():
            part = lines[i].strip()
            paragraph.append(part[1:] if part.startswith("!") else part)
            i += 1
        current.append(Action("\n".join(paragraph)))
        prev_blank = False

    return play


def parse_file(path: str | Path) -> Screenplay:
    return parse(Path(path).read_text(encoding="utf-8"))
