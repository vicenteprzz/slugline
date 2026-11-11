"""Convert a Final Draft (.fdx) screenplay to Fountain.

An .fdx file is XML: a list of <Paragraph Type="..."> elements (Scene Heading,
Action, Character, Parenthetical, Dialogue, Transition, Shot...), each holding
one or more <Text> runs. Dual dialogue sits inside a <DualDialogue> element.
Only the standard library is needed.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import BinaryIO

from slugline.parser import SCENE_PREFIX

# Characters that would change the meaning of an action line in Fountain.
FOUNTAIN_MARKERS = ("#", "=", ">", "@", "~", "!", ".", "[[", "/*", "^")
DIALOGUE_PARTS = {"Character", "Parenthetical", "Dialogue"}


def _text(paragraph: ET.Element) -> str:
    """The paragraph's text: its <Text> runs joined, line breaks kept, spaces tidied."""
    runs = "".join(t.text or "" for t in paragraph.iter("Text"))
    lines = [" ".join(line.split()) for line in runs.replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip()


def _action(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        # All-caps lines (KNOCK KNOCK) and lines starting with a Fountain marker
        # are forced as action, so they don't turn into cues or headings.
        forced = line.isupper() or line.startswith(FOUNTAIN_MARKERS) or bool(SCENE_PREFIX.match(line))
        lines.append(f"!{line}" if forced and line else line)
    return "\n".join(lines)


def _heading(text: str, number: str | None) -> str:
    heading = " ".join(text.split()).upper()
    if not SCENE_PREFIX.match(heading):
        heading = "." + heading  # forced heading: "FLASHBACK", "MONTAGE"...
    return heading + (f" #{number}#" if number else "")


def _cue(text: str, dual: bool) -> str:
    cue = " ".join(text.split())
    name = re.sub(r"\(.*?\)", "", cue).strip()
    forced = "@" if name != name.upper() or not any(c.isalpha() for c in name) else ""
    return f"{forced}{cue}{' ^' if dual else ''}"


def _blocks(paragraphs: list[ET.Element], dual_from: int | None = None) -> list[list[str]]:
    """Fountain blocks (lists of lines) for a run of paragraphs."""
    blocks: list[list[str]] = []
    cues = 0
    for p in paragraphs:
        if p.tag == "DualDialogue":
            blocks += _blocks(list(p.iter("Paragraph")), dual_from=1)
            continue
        if p.tag != "Paragraph":
            continue
        kind = p.get("Type", "Action")
        text = _text(p)
        if not text:
            continue
        if kind == "Scene Heading":
            blocks.append([_heading(text, p.get("Number"))])
        elif kind == "Character":
            dual = dual_from is not None and cues >= dual_from
            cues += 1
            blocks.append([_cue(text, dual)])
        elif kind in ("Parenthetical", "Dialogue") and blocks and blocks[-1] and _in_dialogue(blocks[-1]):
            line = text if kind == "Dialogue" else (text if text.startswith("(") else f"({text})")
            blocks[-1].append(line.replace("\n", " ") if kind == "Parenthetical" else line)
        elif kind == "Transition":
            transition = " ".join(text.split()).upper()
            plain = transition.endswith("TO:")
            blocks.append([transition if plain else f"> {transition}"])
        else:  # Action, Shot, General, a dialogue line without a cue...
            blocks.append([_action(text)])
    return blocks


def _in_dialogue(block: list[str]) -> bool:
    first = block[0].lstrip("@")
    return bool(first) and not first.startswith(("!", ".", ">")) and (block[0].startswith("@") or first == first.upper())


def _title_page(root: ET.Element) -> list[str]:
    page = root.find("TitlePage")
    if page is None:
        return []
    lines = [_text(p) for p in page.iter("Paragraph")]
    lines = [line for line in lines if line]
    if not lines:
        return []
    fields = [f"Title: {lines[0]}"]
    for i, line in enumerate(lines[1:], start=1):
        if line.lower() in ("written by", "by", "screenplay by") and i + 1 < len(lines):
            fields += [f"Credit: {line}", f"Author: {lines[i + 1]}"]
            break
    return fields


def fdx_to_fountain(source: str | bytes | Path | BinaryIO) -> str:
    """Read Final Draft XML (a path, an open binary file, or the XML itself) as Fountain text."""
    is_xml = isinstance(source, bytes) or (isinstance(source, str) and source.lstrip().startswith("<"))
    try:
        if is_xml:
            root = ET.fromstring(source)
        else:
            root = ET.parse(source if hasattr(source, "read") else str(source)).getroot()
    except ET.ParseError as e:
        raise RuntimeError(f"cannot read the file as Final Draft XML: {e}") from e
    except OSError as e:
        raise RuntimeError(f"cannot read {source}: {e.strerror}") from e
    if root.tag != "FinalDraft":
        raise RuntimeError("the file is XML but not a Final Draft script")
    content = root.find("Content")
    if content is None:
        raise RuntimeError("the Final Draft file has no script content")

    body = "\n\n".join("\n".join(block) for block in _blocks(list(content)))
    header = _title_page(root)
    return ("\n".join(header) + "\n\n" if header else "") + body + "\n"
