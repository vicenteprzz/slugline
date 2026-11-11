"""Formatting checks that need no LLM: the mistakes a script supervisor or a
first AD would circle before breaking the script down."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher

from slugline.parser import ACTION_WIDTH, Action, Screenplay, _wrapped

LONG_ACTION_LINES = 6


@dataclass
class Issue:
    severity: str  # "warning" | "info"
    code: str
    message: str
    scene: str | None = None  # scene number, when the issue belongs to one
    source: str = "rule"  # "rule" (this module) or "ai" (slugline.llm)

    def to_dict(self) -> dict:
        return asdict(self)


def _squash(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", name.upper())


def _one_token_typo(a: str, b: str) -> bool:
    """True if two names differ in a single word that looks like a misspelling
    (SHERIF / SHERIFF), not in a number or initial (MAN 1 / MAN 2, MR. B / MR. D)."""
    ta, tb = a.split(), b.split()
    if len(ta) != len(tb):
        return False
    diff = [(x, y) for x, y in zip(ta, tb) if x != y]
    if len(diff) != 1:
        return False
    x, y = diff[0]
    if min(len(x), len(y)) < 4 or not (x.isalpha() and y.isalpha()):
        return False
    return SequenceMatcher(None, x, y).ratio() >= 0.8


def _similar_pairs(names: list[str]) -> list[tuple[str, str, str]]:
    """Pairs of names that are probably the same thing written two ways."""
    pairs = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if _squash(a) == _squash(b):
                pairs.append((a, b, "differ only in punctuation or spacing"))
            elif _one_token_typo(a, b):
                pairs.append((a, b, "look like the same name spelled two ways"))
    return pairs


def lint(play: Screenplay) -> list[Issue]:
    issues: list[Issue] = []

    for s in play.scenes:
        if s.int_ext is None:
            issues.append(Issue("warning", "no-int-ext", f"Heading \"{s.heading}\" has no INT./EXT.", s.number))
        if s.time_of_day is None:
            issues.append(Issue("warning", "no-time", f"Heading \"{s.heading}\" has no time of day.", s.number))
        if not s.elements:
            issues.append(Issue("warning", "empty-scene", f"Scene \"{s.heading}\" is empty.", s.number))
        for d in s.dialogues:
            if not d.lines:
                issues.append(Issue("warning", "empty-dialogue", f"{d.character} has a cue with no dialogue.", s.number))
        long_blocks = sum(
            1 for e in s.elements
            if isinstance(e, Action)
            and sum(_wrapped(p, ACTION_WIDTH) for p in e.text.split("\n")) > LONG_ACTION_LINES
        )
        if long_blocks:
            issues.append(Issue(
                "info", "long-action",
                f"{long_blocks} action paragraph{'s' if long_blocks > 1 else ''} longer than "
                f"{LONG_ACTION_LINES} lines; shorter blocks read faster.", s.number,
            ))

    blocks = Counter(d.character for s in play.scenes for d in s.dialogues)
    for a, b, why in _similar_pairs(sorted(blocks)):
        issues.append(Issue(
            "warning", "similar-characters",
            f"Characters {a} ({blocks[a]} cues) and {b} ({blocks[b]} cues) {why}.",
        ))
    locations = Counter(s.location for s in play.scenes if s.location)
    for a, b, why in _similar_pairs(sorted(locations)):
        issues.append(Issue("warning", "similar-locations", f"Locations \"{a}\" and \"{b}\" {why}."))

    numbered = [s for s in play.scenes if s.scene_number]
    if numbered and len(numbered) < len(play.scenes):
        issues.append(Issue(
            "warning", "partial-numbering",
            f"Only {len(numbered)} of {len(play.scenes)} scenes have a scene number.",
        ))
    for number, count in Counter(s.scene_number for s in numbered).items():
        if count > 1:
            issues.append(Issue("warning", "duplicate-number", f"Scene number {number} is used {count} times.", number))

    if play.scenes and not play.title:
        issues.append(Issue("info", "no-title", "The script has no title page."))
    return issues
