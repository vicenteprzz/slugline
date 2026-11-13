"""Story days and continuity.

A first assistant director marks the day of the story each scene happens on
(day 1, the night of day 1, day 2...). From that come the costume changes of
each character and the continuity to keep between scenes of the same day: a
wound in one scene is still there in the next scene of that day.

`story_days` proposes the days from the script: a heading or opening line
that says NEXT MORNING or TWO DAYS LATER starts a new day, and so does going
from a night scene to a morning one; CONTINUOUS, LATER and SAME stay on the
same day. Days set by hand (see `corrections`) are kept, and the scenes after
them follow on from there.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from slugline.parser import Action, Screenplay

# A new day of the story, in English or Spanish.
NEW_DAY = re.compile(
    r"\b((THE\s+)?NEXT\s+(DAY|MORNING|NIGHT|EVENING|AFTERNOON|WEEK)|FOLLOWING\s+(DAY|MORNING)"
    r"|(\w+|\d+)\s+(DAYS?|WEEKS?|MONTHS?|YEARS?)\s+LATER"
    r"|D[IÍ]A\s+SIGUIENTE|MAÑANA\s+SIGUIENTE|NOCHE\s+SIGUIENTE"
    r"|(\w+|\d+)\s+(D[IÍ]AS|SEMANAS|MESES|AÑOS)\s+(DESPU[EÉ]S|M[AÁ]S\s+TARDE))\b"
)
# The same moment or a little later: no new day, whatever the light.
SAME_DAY = re.compile(
    r"\b(CONTIN[UI]+OUS|SAME|LATER|MOMENTS?|SIMULTANEOUS|SOON|AFTER|CONTINUACI[OÓ]N|MISMO|M[AÁ]S\s+TARDE|POCO\s+DESPU[EÉ]S)\b"
)
MORNING = {"DAY", "DAWN"}
# Categories whose elements carry over between scenes of the same day.
CARRIES_OVER = ("makeup", "wardrobe")
# Names too general to follow from scene to scene.
GENERIC = {"makeup", "maquillaje", "makeup and hair", "maquillaje y peluquería", "hair", "peluquería"}


def _opening(scene) -> str:
    """The first words of the action, where scripts put SUPER: THE NEXT MORNING."""
    for e in scene.elements:
        if isinstance(e, Action):
            return e.text[:160].upper()
    return ""


def story_days(play: Screenplay, fixed: dict[str, int] | None = None) -> dict[str, int]:
    """The day of the story of each scene, by scene number."""
    fixed = fixed or {}
    days: dict[str, int] = {}
    day, light = 1, None
    for i, s in enumerate(play.scenes):
        if s.number in fixed:
            day = fixed[s.number]
        elif i > 0:
            time = (s.time_of_day or "").upper()
            if NEW_DAY.search(time) or NEW_DAY.search(_opening(s)):
                day += 1
            elif SAME_DAY.search(time):
                pass
            elif light == "NIGHT" and (s.day_night in MORNING or "MORNING" in time or "MAÑANA" in time):
                day += 1
        days[s.number] = max(1, day)
        light = s.day_night or light
    return days


def label(day: int | None, day_night: str | None) -> str:
    """D3 for day 3, N3 for the night of day 3, as production boards write it."""
    if not day:
        return ""
    return f"{'N' if day_night == 'NIGHT' else 'D'}{day}"


@dataclass
class Change:
    day: int
    number: int  # the character's costume change, counted through the story
    scenes: list[str] = field(default_factory=list)


@dataclass
class CostumePlot:
    character: str
    changes: list[Change]


@dataclass
class Warning:
    element: str
    category: str
    day: int
    has: str  # the scene that has the element
    missing: str  # a scene of the same day, with the same people, that doesn't
    characters: list[str] = field(default_factory=list)


def costume_plot(rows, days: dict[str, int]) -> list[CostumePlot]:
    """Each character's days of the story, one costume change per day, and the
    scenes of each: what the wardrobe department builds its plot from."""
    seen: dict[str, dict[int, list[str]]] = {}
    for row in rows:
        day = days.get(row.number)
        if not day:
            continue
        for name in dict.fromkeys([*row.characters, *row.silent]):
            seen.setdefault(name, {}).setdefault(day, []).append(row.number)
    plots = []
    for name, by_day in seen.items():
        changes = [Change(day, i, scenes) for i, (day, scenes) in enumerate(sorted(by_day.items()), start=1)]
        plots.append(CostumePlot(name, changes))
    # Most changes first: the characters the department works hardest for.
    return sorted(plots, key=lambda p: (-len(p.changes), p.character))


def warnings(rows, sheet, days: dict[str, int], limit: int = 200) -> list[Warning]:
    """Scenes that may have lost something on the way: a makeup element (a
    wound, blood) or a costume added by hand is in one scene, and a later
    scene of the same story day with the same people doesn't have it."""
    if sheet is None:
        return []
    people = {r.number: set(r.characters) | set(r.silent) for r in rows}
    order = {r.number: i for i, r in enumerate(rows)}
    by_day: dict[int, list[str]] = {}
    for r in rows:
        if days.get(r.number):
            by_day.setdefault(days[r.number], []).append(r.number)
    found: dict[tuple[str, str], Warning] = {}
    for r in rows:
        day = days.get(r.number)
        if not day:
            continue
        for e in sheet.for_scene(r.number):
            if e.category not in CARRIES_OVER or (e.category == "wardrobe" and e.source != "manual") \
                    or e.name.lower() in GENERIC:
                continue
            for other in by_day[day]:
                # Only later in the day: before the wound happens it isn't there.
                if order[other] <= order[r.number]:
                    continue
                shared = people[r.number] & people[other]
                if not shared or any(x.key == e.key for x in sheet.for_scene(other)):
                    continue
                key = (e.key, other)
                if key not in found:
                    found[key] = Warning(e.name, e.category, day, r.number, other, sorted(shared))
    result = sorted(found.values(), key=lambda w: (order.get(w.missing, 0), w.element))
    return result[:limit]


def to_payload(rows, sheet, days: dict[str, int]) -> dict:
    return {
        "costume_plot": [asdict(p) for p in costume_plot(rows, days)],
        "warnings": [asdict(w) for w in warnings(rows, sheet, days)],
        "days": max(days.values(), default=0),
    }
