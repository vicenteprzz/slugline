"""Shooting schedule: which scenes are shot on which day, in what order.

`suggest` makes a first plan the way an assistant director would start one:
day work first and night work in one block at the end (so the crew's sleep
is turned around once), each location kept together, no move to a new
location halfway through a day, and each day filled up to a page count. The plan is then edited by hand in the
dashboard. Schedules are saved per script and carried over to revised drafts
(see `revisions`), like element breakdowns.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from slugline import revisions
from slugline.breakdown import Breakdown, SceneRow
from slugline.parser import parse

KIND = "schedule"
DEFAULT_PAGES_PER_DAY = 5.0
# Lighting order within a location: shoot what needs daylight first.
LIGHT_ORDER = {"DAWN": 0, "DAY": 1, "DUSK": 2, "NIGHT": 3}
MAX_DAYS = 400
MAX_NOTES = 500
MAX_ADDRESS = 300
MAX_ACTOR = 80
CALL_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _day_id() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class ShootDay:
    scenes: list[str] = field(default_factory=list)
    date: str = ""  # ISO date, optional
    notes: str = ""
    id: str = field(default_factory=_day_id)
    call_time: str = ""  # crew call, "07:30"
    address: str = ""  # where the unit meets: location address, base camp, parking


@dataclass
class Schedule:
    days: list[ShootDay] = field(default_factory=list)
    pages_per_day: float = DEFAULT_PAGES_PER_DAY
    revision: dict | None = None  # set when carried over from an earlier draft
    actors: dict[str, str] = field(default_factory=dict)  # character -> actor's name

    def scheduled(self) -> set[str]:
        return {n for d in self.days for n in d.scenes}

    def to_dict(self) -> dict:
        return {"days": [asdict(d) for d in self.days], "pages_per_day": self.pages_per_day,
                "revision": self.revision, "actors": self.actors}

    @classmethod
    def from_dict(cls, data: dict) -> Schedule:
        return cls(
            days=[ShootDay(**d) for d in data.get("days", [])],
            pages_per_day=float(data.get("pages_per_day", DEFAULT_PAGES_PER_DAY)),
            revision=data.get("revision"),
            actors={str(k): str(v) for k, v in data.get("actors", {}).items()},
        )


# --- planning -----------------------------------------------------------------

def _shift(scene: SceneRow) -> int:
    """0 for day work (dawn, day, dusk), 1 for night work."""
    return 1 if scene.day_night == "NIGHT" else 0


def _script_order(scene: SceneRow) -> tuple:
    digits = "".join(c for c in scene.number if c.isdigit())
    return (int(digits) if digits else 0, scene.number)


def suggest(b: Breakdown, pages_per_day: float = DEFAULT_PAGES_PER_DAY) -> Schedule:
    """A first shooting order, grouped by day/night work and location, packed into days."""
    if pages_per_day <= 0:
        raise ValueError("Pages per day must be more than zero.")
    capacity = round(pages_per_day * 8)

    groups: dict[tuple[int, str], list[SceneRow]] = {}
    for s in b.scenes:
        groups.setdefault((_shift(s), s.location or s.heading), []).append(s)
    # Day work before night work; within each, the biggest locations first.
    ordered_groups = sorted(groups.items(), key=lambda kv: (kv[0][0], -sum(s.eighths for s in kv[1]), kv[0][1]))

    days: list[ShootDay] = []
    load = 0
    current: tuple[int, str] | None = None
    for key, scenes in ordered_groups:
        scenes = sorted(scenes, key=lambda s: (LIGHT_ORDER.get(s.day_night or "", 1), _script_order(s)))
        for s in scenes:
            new_shift = current is not None and key[0] != current[0]
            moving = current is not None and key[1] != current[1]
            full = load + s.eighths > capacity
            # A company move costs half a day: start fresh unless the day is still mostly empty.
            if not days or new_shift or (load and full) or (moving and load >= capacity / 2):
                days.append(ShootDay())
                load = 0
            days[-1].scenes.append(s.number)
            load += s.eighths
            current = key
    # Within a day, follow the light: dawn, day, dusk, then night.
    rows = {s.number: s for s in b.scenes}
    for day in days:
        day.scenes.sort(key=lambda n: LIGHT_ORDER.get(rows[n].day_night or "", 1))
    return Schedule(days=days, pages_per_day=pages_per_day)


def set_days(
    b: Breakdown,
    days: list[dict],
    pages_per_day: float | None = None,
    previous: Schedule | None = None,
    actors: dict[str, str] | None = None,
) -> Schedule:
    """A schedule from what the user sent. Raises ValueError with a readable message."""
    if len(days) > MAX_DAYS:
        raise ValueError(f"A schedule can have at most {MAX_DAYS} days.")
    known = {s.number for s in b.scenes}
    seen: set[str] = set()
    result = []
    for i, day in enumerate(days, start=1):
        scenes = day.get("scenes", [])
        if not isinstance(scenes, list) or not all(isinstance(n, str) for n in scenes):
            raise ValueError(f"Day {i}: scenes must be a list of scene numbers.")
        for n in scenes:
            if n not in known:
                raise ValueError(f"Day {i}: there is no scene {n} in this script.")
            if n in seen:
                raise ValueError(f"Scene {n} is scheduled twice.")
            seen.add(n)
        date, notes = day.get("date", "") or "", day.get("notes", "") or ""
        call_time, address = day.get("call_time", "") or "", day.get("address", "") or ""
        if not all(isinstance(v, str) for v in (date, notes, call_time, address)):
            raise ValueError(f"Day {i}: the date, call time, address and notes must be text.")
        if len(notes) > MAX_NOTES or len(address) > MAX_ADDRESS:
            raise ValueError(f"Day {i}: the notes or the address are too long.")
        if call_time and not CALL_TIME.match(call_time):
            raise ValueError(f"Day {i}: the call time must look like 07:30.")
        result.append(ShootDay(scenes=list(scenes), date=date[:10], notes=notes, id=str(day.get("id") or _day_id())[:16],
                               call_time=call_time, address=address))
    if actors is None:
        actors = previous.actors if previous else {}
    cast = {c for s in b.scenes for c in s.characters}
    unknown = [name for name in actors if name not in cast]
    if unknown:
        raise ValueError(f"{unknown[0]} is not a character in this script.")
    if any(not isinstance(v, str) or len(v) > MAX_ACTOR for v in actors.values()):
        raise ValueError(f"Actors' names are limited to {MAX_ACTOR} characters.")
    return Schedule(
        days=result,
        pages_per_day=pages_per_day or (previous.pages_per_day if previous else DEFAULT_PAGES_PER_DAY),
        revision=previous.revision if previous else None,
        actors={k: v.strip() for k, v in actors.items() if v.strip()},
    )


@dataclass
class DayStats:
    eighths: int
    locations: list[str]
    cast: list[str]
    light: list[str]  # DAY / NIGHT / ... in shooting order
    over: bool  # more pages than the planned day


def day_stats(day: ShootDay, b: Breakdown, pages_per_day: float) -> DayStats:
    rows = {s.number: s for s in b.scenes}
    scenes = [rows[n] for n in day.scenes if n in rows]
    eighths = sum(s.eighths for s in scenes)
    unique = lambda values: list(dict.fromkeys(v for v in values if v))  # noqa: E731
    return DayStats(
        eighths=eighths,
        locations=unique(s.location for s in scenes),
        cast=unique(c for s in scenes for c in s.characters),
        light=unique(s.day_night for s in scenes),
        over=eighths > round(pages_per_day * 8),
    )


@dataclass
class CastDays:
    character: str
    actor: str
    codes: list[str]  # one per shooting day: SW, W, WF, SWF, H or ""
    work: int
    hold: int


def day_out_of_days(schedule: Schedule, b: Breakdown) -> list[CastDays]:
    """Which days each character works, in the codes production uses:
    SW start work, W work, WF work finish, SWF start-work-finish (one day),
    H hold (between work days, paid but not shooting).

    A character works on a day when they speak in one of its scenes or the
    action names them in it.
    """
    rows = {s.number: s for s in b.scenes}
    worked: dict[str, list[int]] = {}
    for i, day in enumerate(schedule.days):
        for n in day.scenes:
            s = rows.get(n)
            if s is None:
                continue
            for name in [*s.characters, *s.silent]:
                days = worked.setdefault(name, [])
                if not days or days[-1] != i:
                    days.append(i)
    result = []
    for name, days in worked.items():
        first, last = days[0], days[-1]
        codes = [""] * len(schedule.days)
        for i in range(first, last + 1):
            codes[i] = "H"
        for i in days:
            codes[i] = "SWF" if first == last else "SW" if i == first else "WF" if i == last else "W"
        result.append(CastDays(name, schedule.actors.get(name, ""), codes, len(days), codes.count("H")))
    # As on a production board: who starts first, then who works most.
    return sorted(result, key=lambda c: (c.codes.index(next(x for x in c.codes if x)), -c.work, c.character))


def to_payload(schedule: Schedule | None, b: Breakdown) -> dict | None:
    if schedule is None:
        return None
    scheduled = schedule.scheduled()
    return {
        "pages_per_day": schedule.pages_per_day,
        "days": [{**asdict(d), "stats": asdict(day_stats(d, b, schedule.pages_per_day))} for d in schedule.days],
        "unscheduled": [s.number for s in b.scenes if s.number not in scheduled],
        "revision": schedule.revision,
        "actors": schedule.actors,
        "day_out_of_days": [asdict(c) for c in day_out_of_days(schedule, b)],
    }


# --- storage ----------------------------------------------------------------

def schedule_path(text: str) -> Path:
    return revisions.doc_path(KIND, text)


def load_schedule(text: str) -> Schedule | None:
    data = revisions.load_doc(KIND, text)
    try:
        return Schedule.from_dict(data) if data else None
    except (KeyError, TypeError, ValueError):
        return None


def save_schedule(text: str, schedule: Schedule) -> Path:
    return revisions.save_doc(KIND, text, schedule.to_dict())


def carry_over(text: str) -> Schedule | None:
    """This draft's schedule made from the last schedule of an earlier draft:
    scenes keep their day under their new numbers, cut scenes leave it and
    new scenes wait to be scheduled."""
    play = parse(text)
    previous = revisions.find_previous(KIND, text, play, usable=lambda doc: bool(doc.get("days")))
    if previous is None:
        return None
    old = Schedule.from_dict(previous)
    matching = revisions.match_scenes(previous["meta"]["scenes"], [revisions.fingerprint(s) for s in play.scenes])
    new_number = {m.old: n for n, m in matching.scenes.items()}
    days = [
        ShootDay(scenes=[new_number[n] for n in d.scenes if n in new_number], date=d.date, notes=d.notes, id=d.id,
                 call_time=d.call_time, address=d.address)
        for d in old.days
    ]
    # Actors keep their characters, as long as the character is still in the script.
    cast = {c for s in play.scenes for d in s.dialogues for c in [d.character]}
    actors = {k: v for k, v in old.actors.items() if k in cast}
    return Schedule(days=days, pages_per_day=old.pages_per_day, actors=actors,
                    revision=revisions.matching_payload(matching, previous["meta"]))


def load_or_carry(text: str) -> Schedule | None:
    schedule = load_schedule(text)
    if schedule is None and (schedule := carry_over(text)) is not None:
        try:
            save_schedule(text, schedule)
        except OSError:
            pass
    return schedule
