"""Production elements: what each department has to provide for each scene.

A breakdown sheet lists, scene by scene, the props, wardrobe, vehicles,
effects and so on that the shoot needs. Elements can be suggested by Claude
(see `llm.extract_elements`) and are always editable by hand; hand edits are
never overwritten by a later extraction.

Sheets are saved per script in the data directory (SLUGLINE_DATA, by default
~/.local/share/slugline), keyed by the script's content, so the CLI and the
dashboard see the same breakdown.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from slugline.parser import normalize

if TYPE_CHECKING:
    from slugline.breakdown import Breakdown

# (key, label, colour). The order is the order of the boxes on a breakdown
# sheet; the colours follow the traditional colour coding where there is one.
CATEGORIES: list[tuple[str, str, str]] = [
    ("extras", "Extras", "#2e9e4f"),
    ("stunts", "Stunts", "#ef7d22"),
    ("props", "Props", "#7b4fd0"),
    ("wardrobe", "Wardrobe", "#1a9c9c"),
    ("makeup", "Makeup & hair", "#d4a106"),
    ("vehicles", "Vehicles", "#e06c9f"),
    ("animals", "Animals", "#b0478a"),
    ("sfx", "Special effects", "#2a78d6"),
    ("vfx", "Visual effects", "#0aa0c8"),
    ("sound", "Sound & music", "#8b5a2b"),
    ("set_dressing", "Set dressing", "#6f6d66"),
    ("equipment", "Special equipment", "#3f3f3c"),
]
CATEGORY_KEYS = [key for key, _, _ in CATEGORIES]
LABELS = {key: label for key, label, _ in CATEGORIES}
COLORS = {key: color for key, _, color in CATEGORIES}

MAX_NAME = 120
MAX_NOTES = 300
MAX_PER_SCENE = 300


def element_key(category: str, name: str) -> str:
    """Two elements are the same if they share a category and a name, ignoring case and spacing."""
    return f"{category}|{' '.join(name.lower().split())}"


@dataclass
class Element:
    category: str
    name: str
    notes: str = ""
    source: str = "manual"  # "ai" (suggested by Claude, untouched) or "manual"

    @property
    def key(self) -> str:
        return element_key(self.category, self.name)


@dataclass
class ElementSheet:
    scenes: dict[str, list[Element]] = field(default_factory=dict)
    # Keys of suggested elements someone removed, per scene, so a new
    # extraction doesn't bring them back.
    dismissed: dict[str, list[str]] = field(default_factory=dict)
    model: str | None = None  # the model of the last extraction, if any

    def for_scene(self, number: str) -> list[Element]:
        return self.scenes.get(number, [])

    def is_empty(self) -> bool:
        return not any(self.scenes.values())

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "scenes": {n: [asdict(e) for e in items] for n, items in self.scenes.items()},
            "dismissed": self.dismissed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ElementSheet:
        return cls(
            scenes={str(n): [Element(**e) for e in items] for n, items in data.get("scenes", {}).items()},
            dismissed={str(n): list(keys) for n, keys in data.get("dismissed", {}).items()},
            model=data.get("model"),
        )


def clean(category: Any, name: Any, notes: Any = "") -> tuple[str, str, str]:
    """Validate one element's fields. Raises ValueError with a readable message."""
    if category not in LABELS:
        raise ValueError(f"Unknown category {category!r}. Categories are: {', '.join(CATEGORY_KEYS)}.")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Every element needs a name.")
    if not isinstance(notes, str):
        raise ValueError("Notes must be text.")
    name, notes = " ".join(name.split()), " ".join(notes.split())
    if len(name) > MAX_NAME:
        raise ValueError(f"Element names are limited to {MAX_NAME} characters.")
    if len(notes) > MAX_NOTES:
        raise ValueError(f"Notes are limited to {MAX_NOTES} characters.")
    return category, name, notes


def _ordered(items: list[Element]) -> list[Element]:
    """Category order first; within a category, the order they were added."""
    rank = {key: i for i, key in enumerate(CATEGORY_KEYS)}
    return sorted(items, key=lambda e: rank[e.category])


def _dedupe(items: list[Element]) -> list[Element]:
    seen: set[str] = set()
    out = []
    for e in items:
        if e.key not in seen:
            seen.add(e.key)
            out.append(e)
    return out


def merge_extraction(sheet: ElementSheet | None, found: dict[str, list[Element]], model: str) -> ElementSheet:
    """Combine a new extraction with an existing sheet.

    Elements added or edited by hand are kept; the previous suggestions are
    replaced by the new ones, except those someone removed before.
    """
    sheet = sheet or ElementSheet()
    scenes: dict[str, list[Element]] = {}
    for number in dict.fromkeys([*sheet.scenes, *found]):
        manual = [e for e in sheet.for_scene(number) if e.source == "manual"]
        blocked = {e.key for e in manual} | set(sheet.dismissed.get(number, []))
        suggested = [
            Element(e.category, e.name, e.notes, "ai")
            for e in found.get(number, [])
            if e.key not in blocked
        ]
        scenes[number] = _ordered(_dedupe(manual + suggested))
    return ElementSheet(scenes=scenes, dismissed=sheet.dismissed, model=model)


def update_scene(sheet: ElementSheet | None, number: str, items: list[dict]) -> ElementSheet:
    """Replace one scene's elements with what the user sent.

    A suggestion that comes back unchanged stays a suggestion; anything new or
    edited becomes a manual element; a suggestion that is missing is
    remembered as dismissed.
    """
    sheet = sheet or ElementSheet()
    if len(items) > MAX_PER_SCENE:
        raise ValueError(f"A scene can hold at most {MAX_PER_SCENE} elements.")
    previous = {e.key: e for e in sheet.for_scene(number)}
    updated: list[Element] = []
    for item in items:
        category, name, notes = clean(item.get("category"), item.get("name"), item.get("notes", ""))
        before = previous.get(element_key(category, name))
        unchanged = before is not None and before.source == "ai" and before.name == name and before.notes == notes
        updated.append(Element(category, name, notes, "ai" if unchanged else "manual"))
    updated = _dedupe(updated)

    kept = {e.key for e in updated}
    dismissed = [k for k in sheet.dismissed.get(number, []) if k not in kept]
    dismissed += [k for k, e in previous.items() if e.source == "ai" and k not in kept and k not in dismissed]

    sheet.scenes[number] = _ordered(updated)
    if dismissed:
        sheet.dismissed[number] = dismissed
    else:
        sheet.dismissed.pop(number, None)
    return sheet


@dataclass
class ElementTotal:
    category: str
    name: str
    scenes: list[str]
    eighths: int


def totals(sheet: ElementSheet, b: Breakdown) -> list[ElementTotal]:
    """Each element once, with the scenes that need it and their total length."""
    lengths = {s.number: s.eighths for s in b.scenes}
    grouped: dict[str, ElementTotal] = {}
    for scene in b.scenes:  # script order, so scene lists come out sorted
        for e in sheet.for_scene(scene.number):
            total = grouped.setdefault(e.key, ElementTotal(e.category, e.name, [], 0))
            if scene.number not in total.scenes:
                total.scenes.append(scene.number)
                total.eighths += lengths[scene.number]
    rank = {key: i for i, key in enumerate(CATEGORY_KEYS)}
    return sorted(grouped.values(), key=lambda t: (rank[t.category], -len(t.scenes), t.name.lower()))


def to_payload(sheet: ElementSheet | None, b: Breakdown) -> dict | None:
    """The sheet as the dashboard and the JSON output use it."""
    if sheet is None:
        return None
    return {
        "model": sheet.model,
        "scenes": {n: [asdict(e) for e in items] for n, items in sheet.scenes.items() if items},
        "totals": [asdict(t) for t in totals(sheet, b)],
    }


# --- storage ----------------------------------------------------------------

def data_dir() -> Path:
    return Path(os.environ.get("SLUGLINE_DATA") or Path.home() / ".local" / "share" / "slugline")


def sheet_path(text: str) -> Path:
    key = hashlib.sha256(normalize(text).encode()).hexdigest()[:32]
    return data_dir() / "elements" / f"{key}.json"


def load_sheet(text: str) -> ElementSheet | None:
    try:
        return ElementSheet.from_dict(json.loads(sheet_path(text).read_text(encoding="utf-8")))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError):
        return None  # an unreadable file is treated as no breakdown yet


def save_sheet(text: str, sheet: ElementSheet) -> Path:
    path = sheet_path(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(sheet.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)  # never leave a half-written breakdown behind
    return path
