"""The user's scripts, kept between sessions.

Every script opened in the dashboard is saved in the data directory (see
`revisions.data_dir`), so closing the app loses nothing. A script's id is a
hash of its text: opening the same file twice gives the same project, and a
revised draft is a new project that inherits work from the old one.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from slugline import revisions
from slugline.parser import normalize, parse

KIND = "library"


@dataclass
class Entry:
    id: str
    filename: str
    title: str | None
    scenes: int
    added_at: str
    opened_at: str

    def to_dict(self) -> dict:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _folder() -> Path:
    return revisions.data_dir() / KIND


def _paths(script_id: str) -> tuple[Path, Path]:
    if not script_id.isalnum():  # ids are hex hashes; anything else is not ours
        raise KeyError(script_id)
    return _folder() / f"{script_id}.json", _folder() / f"{script_id}.fountain"


def save(text: str, filename: str) -> Entry:
    """Add a script to the library (or mark it as just opened). Returns its entry."""
    script_id = revisions.script_key(text)
    meta_path, text_path = _paths(script_id)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        previous = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    if not text_path.exists():
        text_path.write_text(normalize(text), encoding="utf-8")
    play = parse(text)
    now = _now()
    entry = Entry(
        id=script_id,
        filename=filename or previous.get("filename") or "script.fountain",
        title=play.title,
        scenes=len(play.scenes),
        added_at=previous.get("added_at") or now,
        opened_at=now,
    )
    meta_path.write_text(json.dumps(entry.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


def load(script_id: str) -> tuple[Entry, str] | None:
    """A saved script's entry and text, or None."""
    try:
        meta_path, text_path = _paths(script_id)
        entry = Entry(**json.loads(meta_path.read_text(encoding="utf-8")))
        return entry, text_path.read_text(encoding="utf-8")
    except (KeyError, OSError, ValueError, TypeError):
        return None


def entries() -> list[Entry]:
    """Every saved script, most recently opened first."""
    found = []
    for path in _folder().glob("*.json") if _folder().is_dir() else []:
        try:
            found.append(Entry(**json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError, TypeError):
            continue
    return sorted(found, key=lambda e: e.opened_at, reverse=True)


def remove(script_id: str) -> bool:
    """Take a script out of the library. Its breakdown and schedule stay on disk,
    so opening the same file again brings them back."""
    try:
        meta_path, text_path = _paths(script_id)
    except KeyError:
        return False
    existed = meta_path.exists()
    for path in (meta_path, text_path):
        path.unlink(missing_ok=True)
    return existed
