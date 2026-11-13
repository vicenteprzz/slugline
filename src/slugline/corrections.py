"""Fixes the user makes in the app without touching the script.

Scripts come with slips: the same character or place spelled two ways
(REDHEAD / READHEAD), or a heading with no time of day. Rewriting the file is
the writer's job; the people breaking it down just need the numbers right.
These corrections are saved next to the script and applied every time it is
read, so the cast list, the locations and the schedule count it as meant.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from slugline import revisions
from slugline.parser import Screenplay, day_night

KIND = "corrections"
DAY_NIGHT = ("DAY", "NIGHT", "DAWN", "DUSK")
KINDS = ("characters", "locations")
MAX_STORY_DAY = 999


@dataclass
class Corrections:
    # Name as written -> name to use, for characters and for locations.
    characters: dict[str, str] = field(default_factory=dict)
    locations: dict[str, str] = field(default_factory=dict)
    # Scene number -> DAY / NIGHT / DAWN / DUSK, for headings that don't say.
    day_night: dict[str, str] = field(default_factory=dict)
    # Scene number -> day of the story, where the suggestion was wrong.
    story_days: dict[str, int] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not (self.characters or self.locations or self.day_night or self.story_days)

    def to_dict(self) -> dict:
        return {"characters": dict(self.characters), "locations": dict(self.locations),
                "day_night": dict(self.day_night), "story_days": dict(self.story_days)}

    @classmethod
    def from_dict(cls, data: dict) -> Corrections:
        def names(value) -> dict[str, str]:
            return {str(k): str(v) for k, v in (value or {}).items() if str(k) != str(v)}

        return cls(
            characters=names(data.get("characters")),
            locations=names(data.get("locations")),
            day_night={str(k): v for k, v in (data.get("day_night") or {}).items() if v in DAY_NIGHT},
            story_days={str(k): int(v) for k, v in (data.get("story_days") or {}).items()
                        if isinstance(v, int) and 1 <= v <= MAX_STORY_DAY},
        )

    def merge(self, kind: str, names: list[str], into: str) -> None:
        """Count every name in `names` as `into` from now on."""
        if kind not in KINDS:
            raise ValueError(f"Unknown kind {kind!r}: use one of {', '.join(KINDS)}.")
        into = " ".join(into.split()).upper()
        if not into:
            raise ValueError("Say which name to keep.")
        aliases = getattr(self, kind)
        for name in names:
            name = " ".join(name.split()).upper()
            if name and name != into:
                aliases[name] = into
        aliases.pop(into, None)  # the name kept is never itself an alias
        # A name merged before into one of these follows it to the new one.
        for name in list(aliases):
            target, seen = aliases[name], {name}
            while target in aliases and target not in seen:
                seen.add(target)
                target = aliases[target]
            aliases[name] = target

    def unmerge(self, kind: str, name: str) -> None:
        if kind not in KINDS:
            raise ValueError(f"Unknown kind {kind!r}: use one of {', '.join(KINDS)}.")
        getattr(self, kind).pop(name.upper(), None)

    def set_story_day(self, scene: str, day: int | None) -> None:
        if day is None:
            self.story_days.pop(scene, None)
        elif isinstance(day, int) and 1 <= day <= MAX_STORY_DAY:
            self.story_days[scene] = day
        else:
            raise ValueError(f"The day of the story must be between 1 and {MAX_STORY_DAY}.")

    def set_day_night(self, scene: str, value: str | None) -> None:
        if value in (None, ""):
            self.day_night.pop(scene, None)
        elif value in DAY_NIGHT:
            self.day_night[scene] = value
        else:
            raise ValueError(f"Day or night must be one of {', '.join(DAY_NIGHT)}.")


def apply(play: Screenplay, fixes: Corrections | None) -> Screenplay:
    """Apply the corrections to a parsed script, in place, and return it."""
    if fixes is None or fixes.is_empty():
        return play
    previous = None
    for scene in play.scenes:
        scene.location = fixes.locations.get(scene.location, scene.location)
        for d in scene.dialogues:
            d.character = fixes.characters.get(d.character, d.character)
        # A heading that says DAY or NIGHT keeps it; one set by hand uses that;
        # the rest (LATER, CONTINUOUS, nothing) follow the scene before, which
        # may itself have been set by hand.
        scene.day_night = fixes.day_night.get(scene.number) or day_night(scene.time_of_day) or previous
        previous = scene.day_night
    for d in (e for e in play.preamble if hasattr(e, "character")):
        d.character = fixes.characters.get(d.character, d.character)
    return play


def load(text: str) -> Corrections:
    data = revisions.load_doc(KIND, text)
    try:
        return Corrections.from_dict(data) if data else Corrections()
    except (AttributeError, TypeError, ValueError):
        return Corrections()


def save(text: str, fixes: Corrections) -> None:
    revisions.save_doc(KIND, text, fixes.to_dict())
