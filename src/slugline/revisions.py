"""Scripts get rewritten all through prep. This module lets work done on one
draft (the element breakdown, the shooting schedule) carry over to the next.

Each saved document stores a fingerprint of every scene: its heading and the
words in it. When a draft is opened that has no saved work of its own, the
most recent document of the same script is found and its scenes are matched
to the new draft's, even if scenes were renumbered, moved or rewritten.

Documents live in the data directory (SLUGLINE_DATA, by default
~/.local/share/slugline), one folder per kind, keyed by the script's content.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from slugline.parser import Scene, Screenplay, normalize, parse, parse_heading

WORD = re.compile(r"\w{3,}")
# Words too common to say anything about what a scene is (English and Spanish).
STOPWORDS = {
    "the", "and", "his", "her", "him", "she", "they", "them", "their", "for", "with", "from", "into", "that",
    "this", "but", "not", "you", "are", "was", "has", "have", "its", "our", "out", "all", "who",
    "que", "los", "las", "del", "una", "uno", "por", "con", "para", "como", "pero", "sus", "más", "mas",
    "esta", "este", "eso", "esa", "hay", "muy", "sin", "sobre", "entre", "cuando", "donde",
}
# Below this, two scenes are considered different scenes.
MIN_SCORE = 0.45
# A scene that moved to a different location is the same scene only if most of its text stayed.
MOVED_LOCATION_CONTENT = 0.6


# --- fingerprints and matching ----------------------------------------------

def fingerprint(scene: Scene) -> dict:
    body = scene.to_text().partition("\n")[2]
    return {
        "number": scene.number,
        "heading": scene.heading,
        "words": sorted({w.lower() for w in WORD.findall(body)} - STOPWORDS),
    }


@dataclass
class SceneMatch:
    old: str  # the scene's number in the previous draft
    status: str  # "unchanged" or "changed"


@dataclass
class Matching:
    scenes: dict[str, SceneMatch]  # by scene number in the new draft
    new: list[str]  # scenes of the new draft with no counterpart
    omitted: list[dict]  # scenes of the old draft that are gone: {"number", "heading"}


def match_scenes(old: list[dict], new: list[dict]) -> Matching:
    """Pair the scenes of two drafts.

    Two scenes are scored by how alike their headings are, how many words they
    share, and how close they sit in the script (which tells apart two scenes
    with the same heading). Pairs are taken best first, each scene once, so a
    scene that moved is still found.
    """
    def location(heading: str) -> str:
        return parse_heading(heading)[1] or heading

    pairs = []
    for i, o in enumerate(old):
        old_words = set(o["words"])
        for j, n in enumerate(new):
            heading = SequenceMatcher(None, o["heading"], n["heading"]).ratio()
            new_words = set(n["words"])
            union = old_words | new_words
            content = len(old_words & new_words) / len(union) if union else 1.0
            same_place = SequenceMatcher(None, location(o["heading"]), location(n["heading"])).ratio() >= 0.8
            if not same_place and content < MOVED_LOCATION_CONTENT:
                continue  # a different place with different action is a different scene
            position = 1 - abs(i / max(len(old), 1) - j / max(len(new), 1))
            score = 0.3 * heading + 0.6 * content + 0.1 * position
            if score >= MIN_SCORE:
                pairs.append((score, i, j))
    pairs.sort(key=lambda p: (-p[0], p[1], p[2]))

    used_old: set[int] = set()
    used_new: set[int] = set()
    scenes: dict[str, SceneMatch] = {}
    for _score, i, j in pairs:
        if i in used_old or j in used_new:
            continue
        used_old.add(i)
        used_new.add(j)
        # Any rewrite counts: one changed word can be a changed prop.
        same = old[i]["heading"] == new[j]["heading"] and old[i]["words"] == new[j]["words"]
        scenes[new[j]["number"]] = SceneMatch(old[i]["number"], "unchanged" if same else "changed")
    return Matching(
        scenes={n["number"]: scenes[n["number"]] for n in new if n["number"] in scenes},
        new=[n["number"] for n in new if n["number"] not in scenes],
        omitted=[{"number": o["number"], "heading": o["heading"]} for i, o in enumerate(old) if i not in used_old],
    )


def matching_payload(matching: Matching, previous: dict) -> dict:
    """What a carried-over document remembers about where it came from."""
    return {
        "from": {"title": previous.get("title"), "saved_at": previous.get("saved_at")},
        "scenes": {n: asdict(m) for n, m in matching.scenes.items()},
        "new": matching.new,
        "omitted": matching.omitted,
    }


# --- storage ----------------------------------------------------------------

def data_dir() -> Path:
    return Path(os.environ.get("SLUGLINE_DATA") or Path.home() / ".local" / "share" / "slugline")


def script_key(text: str) -> str:
    return hashlib.sha256(normalize(text).encode()).hexdigest()[:32]


def doc_path(kind: str, text: str) -> Path:
    return data_dir() / kind / f"{script_key(text)}.json"


def load_doc(kind: str, text: str) -> dict | None:
    try:
        data = json.loads(doc_path(kind, text).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None  # missing or unreadable: treated as nothing saved yet
    return data if isinstance(data, dict) else None


def save_doc(kind: str, text: str, data: dict, play: Screenplay | None = None) -> Path:
    """Save a document with the fingerprints a later draft needs to find it."""
    play = play or parse(text)
    doc = {
        **data,
        "meta": {
            "title": play.title,
            "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "scenes": [fingerprint(s) for s in play.scenes],
        },
    }
    path = doc_path(kind, text)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)  # never leave a half-written file behind
    return path


def _same_script(meta: dict, play: Screenplay) -> bool:
    """Whether a saved document looks like an earlier draft of this script."""
    if play.title and meta.get("title"):
        return play.title.strip().lower() == meta["title"].strip().lower()
    # No title page: half the headings in common is enough.
    old = {s["heading"] for s in meta.get("scenes", [])}
    new = [s.heading for s in play.scenes]
    return bool(new) and sum(h in old for h in new) / len(new) >= 0.5


def find_previous(kind: str, text: str, play: Screenplay, usable: Callable[[dict], bool]) -> dict | None:
    """The most recently saved document of an earlier draft of this script."""
    folder = data_dir() / kind
    own = doc_path(kind, text)
    best = None
    for path in folder.glob("*.json") if folder.is_dir() else []:
        if path == own:
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        meta = doc.get("meta") if isinstance(doc, dict) else None
        if not isinstance(meta, dict) or not meta.get("scenes") or not usable(doc):
            continue
        if _same_script(meta, play) and (best is None or meta.get("saved_at", "") > best["meta"].get("saved_at", "")):
            best = doc
    return best
