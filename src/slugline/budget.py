"""A first budget, worked out from the breakdown and the shooting schedule.

What a budget needs most is the quantities: how many shooting days, how many
days each actor works, how many days there are extras on set, how long the
unit spends at each location, which days need a picture car or an animal.
Those come straight from the schedule (or, before there is one, from the plan
`schedule.suggest` would make), so they are exact and move when the schedule
moves.

The prices are the user's. Each budget starts from a level (a short, a
low-budget feature, a mid-budget feature) whose rates are only a starting
point, and every rate and quantity can be changed. What can't be priced from
a script (an explosion, a visual effect) is marked to be quoted: the budget
counts the scenes and days that need it and carries a placeholder until the
user enters a quote.

Lines are grouped in the twelve chapters of the ICAA budget model used for
Spanish film funding. This is a first draft for a production manager to
check, not a budget to submit.
"""

from __future__ import annotations

import copy
import math
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from slugline import revisions
from slugline import schedule as scheduling
from slugline.breakdown import Breakdown, SceneRow
from slugline.elements import ElementSheet
from slugline.parser import parse

KIND = "budget"
CURRENCY = "EUR"

CHAPTERS = [
    ("01", "Script and music"),
    ("02", "Artistic staff"),
    ("03", "Crew"),
    ("04", "Sets and locations"),
    ("05", "Studios and sound"),
    ("06", "Equipment, shooting and transport"),
    ("07", "Travel, hotels and meals"),
    ("08", "Digital media"),
    ("09", "Post-production"),
    ("10", "Insurance"),
    ("11", "Overheads"),
    ("12", "Publicity and finance"),
]

# --- levels -----------------------------------------------------------------
# Rates in euros, per day unless the name says otherwise. They are a rough
# starting point for Spain, to be replaced by the production's own.

_LOW = {
    # cast, per working day
    "cast.lead": 1000, "cast.supporting": 450, "cast.small": 200, "extras.person": 60,
    "stunts.day": 1500,
    # sets and locations
    "location.day": 600, "props.item": 80, "wardrobe.character": 400, "wardrobe.item": 120,
    "makeup.day": 120, "makeup.item": 250, "set_dressing.item": 150,
    "vehicle.day": 250, "animal.day": 600,
    # to be quoted: placeholders per scene until there is a quote
    "sfx.scene": 3000, "vfx.scene": 5000,
    # equipment and transport
    "camera.day": 900, "lighting.day": 800, "grip.day": 400, "equipment.day": 900,
    "van.day": 120, "fuel.day": 40,
    # meals and media
    "catering.person": 22, "storage.day": 80,
    # lump sums
    "script.total": 40000, "music.total": 25000, "post.total": 120000, "publicity.total": 15000,
    "sound_studio.total": 15000,
}


def _scaled(base: dict, people: float, things: float, lumps: float) -> dict:
    groups = {
        "people": ("cast.", "extras.", "stunts."),
        "lumps": ("script.", "music.", "post.", "publicity.", "sound_studio."),
    }
    out = {}
    for key, value in base.items():
        factor = people if key.startswith(groups["people"]) else lumps if key.startswith(groups["lumps"]) else things
        out[key] = round(value * factor / 10) * 10 if value * factor >= 50 else round(value * factor)
    return out


# Crew: (key, department, role, low-budget rate per day, prep days per shooting day)
CREW = [
    ("director", "Direction", "Director", 600, 1.0),
    ("first_ad", "Direction", "First assistant director", 350, 0.5),
    ("script_supervisor", "Direction", "Script supervisor", 220, 0.2),
    ("production_manager", "Production", "Line producer", 450, 1.0),
    ("unit_manager", "Production", "Production manager", 320, 0.5),
    ("production_assistant", "Production", "Production assistant", 150, 0.2),
    ("dop", "Camera", "Director of photography", 550, 0.4),
    ("focus_puller", "Camera", "Focus puller", 280, 0.1),
    ("camera_assistant", "Camera", "Camera assistant", 180, 0.1),
    ("sound_mixer", "Sound", "Sound mixer", 300, 0.1),
    ("boom", "Sound", "Boom operator", 200, 0.0),
    ("art_director", "Art", "Production designer", 400, 0.8),
    ("set_dresser", "Art", "Set dresser", 220, 0.4),
    ("costume_designer", "Wardrobe", "Costume designer", 320, 0.6),
    ("makeup_artist", "Makeup and hair", "Makeup artist", 260, 0.2),
    ("hair", "Makeup and hair", "Hairdresser", 220, 0.1),
    ("gaffer", "Electric", "Gaffer", 260, 0.1),
    ("electrician", "Electric", "Electrician", 200, 0.0),
    ("key_grip", "Grip", "Key grip", 260, 0.1),
]
# The smaller crew of a short.
SHORT_CREW = {"director", "first_ad", "script_supervisor", "production_manager", "production_assistant", "dop",
              "focus_puller", "sound_mixer", "boom", "art_director", "costume_designer", "makeup_artist", "gaffer",
              "key_grip"}

LEVELS = {
    "short": {
        "label": "Short film",
        "rates": {**_scaled(_LOW, 0.15, 0.35, 0.05), "script.total": 0, "publicity.total": 500},
        "crew_factor": 0.4, "extras": 5, "vans": 1, "post_split": (0.5, 0.2, 0.3),
    },
    "low": {
        "label": "Low-budget feature",
        "rates": dict(_LOW),
        "crew_factor": 1.0, "extras": 15, "vans": 3, "post_split": (0.45, 0.25, 0.30),
    },
    "medium": {
        "label": "Mid-budget feature",
        "rates": _scaled(_LOW, 2.0, 1.6, 2.5),
        "crew_factor": 1.6, "extras": 30, "vans": 6, "post_split": (0.40, 0.25, 0.35),
    },
    # A studio picture: stars, union crews, a second unit, hundreds of extras,
    # big visual effects, and a slower pace (fewer pages a day, so more days).
    "high": {
        "label": "High-budget feature",
        "rates": {
            **_scaled(_LOW, 10, 8, 30),
            "cast.lead": 60000, "cast.supporting": 12000, "cast.small": 2500, "extras.person": 220,
            "stunts.day": 25000, "location.day": 15000, "camera.day": 12000, "lighting.day": 15000,
            "grip.day": 8000, "sfx.scene": 60000, "vfx.scene": 150000, "vfx.total": 25000000,
            "script.total": 3000000, "music.total": 1500000, "post.total": 6000000, "publicity.total": 1000000,
            "sound_studio.total": 1200000, "second_unit.day": 60000, "catering.person": 45,
            "crew.extra_person": 450, "construction.total": 15000000,
        },
        "crew_factor": 3.2, "extras": 150, "vans": 25, "post_split": (0.40, 0.25, 0.35),
        "pages_per_day": 2.0, "second_unit": 0.4,
        # Departments at studio size: the people beyond the heads listed in CREW.
        "extra_crew": 120,
    },
}
DEFAULT_LEVEL = "low"
HOLD_LIMIT = 5  # longest gap between working days that is paid as hold
# Social security an employer pays on top of a wage, roughly, by country. It
# changes with the contract and the year: a starting point to check with the
# production's payroll. "none" is for crews who invoice, or rates that already
# include it.
COUNTRIES = {
    "es": ("Spain", 0.32),  # common contingencies, unemployment, FOGASA, training, accident cover
    "fr": ("France", 0.45),
    "it": ("Italy", 0.30),
    "de": ("Germany", 0.21),
    "pt": ("Portugal", 0.2375),
    "uk": ("United Kingdom", 0.15),
    "us": ("United States", 0.25),  # payroll taxes and union fringes, which vary a lot
    "mx": ("Mexico", 0.30),
    "ar": ("Argentina", 0.24),
    "co": ("Colombia", 0.30),
    "none": ("No social security", 0.0),
}
DEFAULT_COUNTRY = "es"

# Percentages, all editable in the budget:
PERCENTAGES = {
    # Social security on cast and crew wages: by default, the country's (see COUNTRIES).
    "social": COUNTRIES[DEFAULT_COUNTRY][1],
    "overtime": 0.05,  # of crew wages
    "insurance": 0.025,  # of the budget before insurance and overheads
    "overheads": 0.07,
    # A reserve on top of the chapters for what nobody saw coming. The ICAA
    # model keeps it out of the chapters, so it is shown apart.
    "contingency": 0.07,
}


# --- settings -----------------------------------------------------------------

@dataclass
class BudgetSettings:
    level: str = DEFAULT_LEVEL
    country: str = DEFAULT_COUNTRY  # sets the social security percentage
    rates: dict[str, float] = field(default_factory=dict)  # line key -> rate, replacing the computed one
    units: dict[str, float] = field(default_factory=dict)  # line key -> quantity, replacing the computed one
    quotes: dict[str, float] = field(default_factory=dict)  # line key -> quoted total, for lines to be quoted
    extra: list[dict] = field(default_factory=list)  # lines added by hand: chapter, concept, units, rate
    percentages: dict[str, float] = field(default_factory=dict)  # key of PERCENTAGES -> fraction, if changed
    # The total and days of this draft and of the draft before it, for the comparison.
    snapshot: dict | None = None
    previous: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> BudgetSettings:
        def numbers(value) -> dict[str, float]:
            out = {}
            for k, v in (value or {}).items():
                try:
                    number = float(v)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(number) and number >= 0:
                    out[str(k)] = number
            return out

        level = data.get("level")
        return cls(
            level=level if level in LEVELS else DEFAULT_LEVEL,
            country=data.get("country") if data.get("country") in COUNTRIES else DEFAULT_COUNTRY,
            rates=numbers(data.get("rates")),
            units=numbers(data.get("units")),
            quotes=numbers(data.get("quotes")),
            extra=[_clean_extra(x) for x in data.get("extra") or [] if isinstance(x, dict)][:200],
            percentages={k: v for k, v in numbers(data.get("percentages")).items() if k in PERCENTAGES and v <= 1},
            snapshot=data.get("snapshot") if isinstance(data.get("snapshot"), dict) else None,
            previous=data.get("previous") if isinstance(data.get("previous"), dict) else None,
        )


def percentages(settings: BudgetSettings) -> dict[str, float]:
    """The percentages in force: the defaults, the country's social security,
    and whatever the user changed."""
    return {**PERCENTAGES, "social": COUNTRIES[settings.country][1], **settings.percentages}


def _clean_extra(item: dict) -> dict:
    chapter = str(item.get("chapter", "04"))
    if chapter not in dict(CHAPTERS):
        chapter = "04"
    try:
        units, rate = float(item.get("units", 1)), float(item.get("rate", 0))
    except (TypeError, ValueError):
        units, rate = 1.0, 0.0
    return {"chapter": chapter, "concept": " ".join(str(item.get("concept", "")).split())[:120] or "Other",
            "units": max(0.0, units), "rate": max(0.0, rate)}


# --- lines --------------------------------------------------------------------

@dataclass
class Line:
    key: str
    chapter: str
    concept: str
    units: float
    unit: str  # "days", "people x days", "items", "lump"...
    rate: float
    to_quote: bool = False  # priced with a placeholder until there is a quote
    quoted: bool = False
    edited: bool = False  # the rate or quantity was changed by hand
    detail: str = ""  # where the quantity comes from
    scenes: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return round(self.units * self.rate, 2)


@dataclass
class _Plan:
    """Shooting days with their scenes: the real schedule, plus the days a
    suggested plan would add for scenes not scheduled yet."""
    days: list[list[SceneRow]]
    scheduled: int  # how many of the days come from the user's schedule
    pages_per_day: float


def _plan(b: Breakdown, plan: scheduling.Schedule | None,
          pace: float = scheduling.DEFAULT_PAGES_PER_DAY) -> _Plan:
    rows = {s.number: s for s in b.scenes}
    # The user's schedule sets the pace; without one, the level's usual pace.
    pages_per_day = plan.pages_per_day if plan else pace
    days = [[rows[n] for n in d.scenes if n in rows] for d in plan.days] if plan else []
    days = [d for d in days if d]
    scheduled = len(days)
    taken = {s.number for d in days for s in d}
    rest = [s for s in b.scenes if s.number not in taken]
    if rest:
        guess = scheduling.suggest(replace(b, scenes=rest), pages_per_day)
        days += [[rows[n] for n in d.scenes if n in rows] for d in guess.days]
    return _Plan(days=[d for d in days if d], scheduled=scheduled, pages_per_day=pages_per_day)


def _roles(b: Breakdown, worked: dict[str, set[int]]) -> dict[str, str]:
    """Lead, supporting or small part: by the days each character works, then
    by how much they speak."""
    words = {c.name: c.words for c in b.characters}
    ranked = sorted(worked, key=lambda n: (-len(worked[n]), -words.get(n, 0), n))
    return {name: "lead" if i < 2 else "supporting" if i < 8 else "small" for i, name in enumerate(ranked)}


def _paid_days(days: set[int]) -> tuple[int, int]:
    """Working days and paid holds. A gap of a few days between two working
    days is paid as hold; after a longer one the actor is released and called
    again (drop and pick up), so it isn't."""
    ordered = sorted(days)
    holds = sum(gap for a, b in zip(ordered, ordered[1:]) if 0 < (gap := b - a - 1) <= HOLD_LIMIT)
    return len(ordered), holds


def _days_with(plan: _Plan, scenes: set[str]) -> int:
    return sum(1 for day in plan.days if any(s.number in scenes for s in day))


def _element_scenes(sheet: ElementSheet | None, b: Breakdown) -> dict[tuple[str, str], list[str]]:
    """(category, name) -> scenes that need it, in script order."""
    found: dict[tuple[str, str], list[str]] = {}
    if sheet is None:
        return found
    for scene in b.scenes:
        for e in sheet.for_scene(scene.number):
            scenes = found.setdefault((e.category, e.name), [])
            if scene.number not in scenes:
                scenes.append(scene.number)
    return found


def build_lines(b: Breakdown, plan: _Plan, sheet: ElementSheet | None, settings: BudgetSettings) -> list[Line]:
    level = LEVELS[settings.level]
    r = level["rates"]
    days = len(plan.days)
    lines: list[Line] = []

    def add(key: str, chapter: str, concept: str, units: float, unit: str, rate: float, **kw) -> None:
        lines.append(Line(key, chapter, concept, units, unit, rate, **kw))

    # 01 script and music
    add("script", "01", "Script and rights", 1 if r["script.total"] else 0, "lump", r["script.total"])
    add("music", "01", "Original music", 1, "lump", r["music.total"])

    # 02 cast: each character, for the days they work (holds are paid too)
    worked: dict[str, set[int]] = {}
    for i, day in enumerate(plan.days):
        for s in day:
            for name in [*s.characters, *s.silent]:
                worked.setdefault(name, set()).add(i)
    paid = {name: _paid_days(d) for name, d in worked.items()}
    roles = _roles(b, worked)
    order = {"lead": 0, "supporting": 1, "small": 2}
    for name in sorted(worked, key=lambda n: (order[roles[n]], -sum(paid[n]), n)):
        role = roles[name]
        scenes = [s.number for d in plan.days for s in d if name in s.characters or name in s.silent]
        work, hold = paid[name]
        add(f"cast:{name}", "02", name, work + hold, "days", r[f"cast.{role}"], scenes=scenes,
            detail=f"{role}|{work}|{hold}")

    # extras and stunts, on the days that need them
    elements = _element_scenes(sheet, b)
    extras_scenes = {n for (cat, _), scenes in elements.items() if cat == "extras" for n in scenes}
    if extras_scenes:
        extra_days = _days_with(plan, extras_scenes)
        add("extras", "02", "Extras", extra_days * level["extras"], "people x days", r["extras.person"],
            scenes=sorted(extras_scenes, key=_order(b)), detail=f"{level['extras']}|{extra_days}")
    stunt_scenes = {n for (cat, _), scenes in elements.items() if cat == "stunts" for n in scenes}
    if stunt_scenes:
        add("stunts", "02", "Stunt team", _days_with(plan, stunt_scenes), "days", r["stunts.day"],
            scenes=sorted(stunt_scenes, key=_order(b)))

    # 03 crew: shooting days plus their preparation
    factor = level["crew_factor"]
    for key, department, role, rate, prep in CREW:
        if settings.level == "short" and key not in SHORT_CREW:
            continue
        prep_days = math.ceil(days * prep * (0.5 if settings.level == "short" else 1))
        add(f"crew:{key}", "03", role, days + prep_days, "days", round(rate * factor / 10) * 10,
            detail=f"{department}|{days}|{prep_days}")
    if settings.level == "medium":
        add("crew:electrician_2", "03", "Electrician", days, "days", round(200 * factor / 10) * 10,
            detail=f"Electric|{days}|0")

    if level.get("extra_crew"):
        add("crew:extra", "03", "Rest of the crew at studio size", days * level["extra_crew"], "people x days",
            r["crew.extra_person"], detail=f"{level['extra_crew']}|{days}")
    if level.get("second_unit"):
        second = math.ceil(days * level["second_unit"])
        add("second_unit", "03", "Second unit: crew and equipment", second, "days", r["second_unit.day"],
            detail=f"{level['second_unit']}|{days}")

    # 04 sets and locations
    by_location: dict[str, set[int]] = {}
    for i, day in enumerate(plan.days):
        for s in day:
            by_location.setdefault(s.location or s.heading, set()).add(i)
    for location in sorted(by_location, key=lambda loc: (-len(by_location[loc]), loc)):
        scenes = [s.number for d in plan.days for s in d if (s.location or s.heading) == location]
        add(f"location:{location}", "04", location, len(by_location[location]), "days", r["location.day"],
            scenes=scenes)
    if "construction.total" in r:
        add("construction", "04", "Set construction on stage", 1, "lump", r["construction.total"], to_quote=True)
    cast_with_wardrobe = [n for n in worked if roles[n] != "small"]
    add("wardrobe:cast", "04", "Wardrobe for the main cast", len(cast_with_wardrobe), "characters",
        r["wardrobe.character"])
    add("makeup:kit", "04", "Makeup and hair materials", days, "days", r["makeup.day"])
    per_item = {"props": ("props.item", "Prop"), "wardrobe": ("wardrobe.item", "Wardrobe"),
                "makeup": ("makeup.item", "Makeup"), "set_dressing": ("set_dressing.item", "Set dressing")}
    for (category, name), scenes in elements.items():
        if category in per_item:
            rate_key, _ = per_item[category]
            add(f"element:{category}|{name}", "04", name, 1, "items", r[rate_key], scenes=scenes, detail=category)
        elif category in ("vehicles", "animals"):
            rate_key = "vehicle.day" if category == "vehicles" else "animal.day"
            add(f"element:{category}|{name}", "04", name, _days_with(plan, set(scenes)), "days", r[rate_key],
                scenes=scenes, detail=category)
        elif category in ("sfx", "vfx"):
            chapter = "04" if category == "sfx" else "09"
            add(f"element:{category}|{name}", chapter, name, len(scenes), "scenes", r[f"{category}.scene"],
                scenes=scenes, detail=category, to_quote=True)
        elif category == "equipment":
            add(f"element:{category}|{name}", "06", name, _days_with(plan, set(scenes)), "days", r["equipment.day"],
                scenes=scenes, detail=category)

    # 05 studios and sound
    add("sound_studio", "05", "Sound studio: dubbing, foley and mix", 1, "lump", r["sound_studio.total"])

    # 06 equipment, shooting and transport
    add("camera", "06", "Camera package", days, "days", r["camera.day"])
    add("lighting", "06", "Lighting", days, "days", r["lighting.day"])
    add("grip", "06", "Grip", days, "days", r["grip.day"])
    add("vans", "06", "Production vans", days * level["vans"], "vans x days", r["van.day"],
        detail=f"{level['vans']}|{days}")
    add("fuel", "06", "Fuel and parking", days * level["vans"], "vans x days", r["fuel.day"])

    # 07 travel, hotels and meals
    crew_count = sum(1 for line in lines if line.key.startswith("crew:") and line.key != "crew:extra")
    crew_count += level.get("extra_crew", 0)
    cast_days = sum(len(d) for d in worked.values())
    meals = days * crew_count + cast_days
    add("catering", "07", "Catering on set", meals, "meals", r["catering.person"],
        detail=f"{crew_count}|{days}|{cast_days}")
    add("travel", "07", "Travel, hotels and per diems (shooting away from home)", 0, "people x days", 90)

    # 08 digital media
    add("storage", "08", "Drives, backup and data management", days, "days", r["storage.day"])

    # 09 post-production
    edit, grade, other = level["post_split"]
    add("post:edit", "09", "Editing", 1, "lump", round(r["post.total"] * edit))
    add("post:grade", "09", "Grading and conform", 1, "lump", round(r["post.total"] * grade))
    add("post:deliveries", "09", "Titles, subtitles and deliveries", 1, "lump", round(r["post.total"] * other))

    if "vfx.total" in r:
        # Big pictures carry visual effects the script never names: a reserve to be quoted.
        add("vfx:general", "09", "Visual effects across the film", 1, "lump", r["vfx.total"], to_quote=True)

    # 12 publicity and finance
    add("publicity", "12", "Publicity and festivals", 1, "lump", r["publicity.total"])

    # the user's changes, and the lines they added
    for line in lines:
        if line.key in settings.units:
            line.units, line.edited = settings.units[line.key], True
        if line.key in settings.rates:
            line.rate, line.edited = settings.rates[line.key], True
        if line.to_quote and line.key in settings.quotes:
            line.units, line.rate, line.quoted = 1, settings.quotes[line.key], True
    for i, item in enumerate(settings.extra):
        add(f"extra:{i}", item["chapter"], item["concept"], item["units"], "units", item["rate"], edited=True)

    # Lines worked out as a percentage of others: overtime and social security on
    # the wages, then insurance and overheads on everything else.
    pct = percentages(settings)
    computed: list[Line] = []

    def percent(key: str, chapter: str, concept: str, share: str, of: float) -> None:
        add(key, chapter, concept, 1, "lump", round(of * pct[share]), detail=f"{pct[share]}|{share}")
        computed.append(lines[-1])

    crew_wages = sum(line.total for line in lines if line.chapter == "03")
    cast_wages = sum(line.total for line in lines if line.chapter == "02")
    percent("overtime", "03", "Overtime", "overtime", crew_wages)
    overtime = lines[-1].total
    percent("social:cast", "02", "Social security for the cast", "social", cast_wages)
    percent("social:crew", "03", "Social security for the crew", "social", crew_wages + overtime)
    base = sum(line.total for line in lines)
    percent("insurance", "10", "Production insurance", "insurance", base)
    percent("overheads", "11", "Overheads: office, accounting, legal", "overheads", base)
    for line in computed:
        if line.key in settings.rates:
            line.rate, line.edited = settings.rates[line.key], True
    return lines


def _order(b: Breakdown):
    index = {s.number: i for i, s in enumerate(b.scenes)}
    return lambda n: index.get(n, 0)


# --- cost per scene -------------------------------------------------------------

def scene_costs(lines: list[Line], plan: _Plan) -> dict[str, float]:
    """What each scene costs to shoot: its share of each day it is shot on
    (crew, equipment, location, cast), plus what only it needs. Preparation,
    post-production and lump sums are left out: cutting a scene doesn't save
    them."""
    cost: dict[str, float] = {s.number: 0.0 for day in plan.days for s in day}
    if not plan.days:
        return cost
    day_of = {s.number: i for i, day in enumerate(plan.days) for s in day}
    weight = {s.number: max(s.eighths, 1) for day in plan.days for s in day}

    def spread(amount: float, scenes: list[str]) -> None:
        """Share an amount among scenes, by length."""
        scenes = [n for n in scenes if n in cost]
        total = sum(weight[n] for n in scenes)
        for n in scenes:
            cost[n] += amount * weight[n] / total if total else 0

    def per_day(amount_per_day: float, scenes: list[str] | None = None) -> None:
        """A cost that is paid on each day these scenes (or all scenes) are shot."""
        for i, day in enumerate(plan.days):
            names = [s.number for s in day if scenes is None or s.number in scenes]
            if names:
                spread(amount_per_day, names)

    days = len(plan.days)
    for line in lines:
        if line.total == 0:
            continue
        if line.key.startswith("crew:") and line.unit == "days":
            per_day(line.rate)  # each shooting day of each crew member; not their preparation
        elif line.key == "crew:extra":
            per_day(line.total / days)
        elif line.key in ("camera", "lighting", "grip", "vans", "fuel", "storage", "makeup:kit", "catering",
                          "overtime", "social:cast", "social:crew"):
            per_day(line.total / days)
        elif line.scenes and (line.unit in ("days", "people x days") or line.key.startswith("cast:")):
            # Paid on the days these scenes are shot (a cast member's holds too),
            # shared among the scenes that need it on each day.
            scene_days = {day_of[n] for n in line.scenes if n in day_of}
            for i in scene_days:
                spread(line.total / len(scene_days), [n for n in line.scenes if day_of.get(n) == i])
        elif line.scenes:
            spread(line.total, line.scenes)  # an item or an effect: shared among its scenes
    return {n: round(v, 2) for n, v in cost.items()}


# --- reordering the schedule to save money -------------------------------------------

@dataclass
class Reorder:
    order: list[int]  # the schedule's days, by their position now, in the new order
    cost_before: float
    cost_after: float
    holds_before: int
    holds_after: int
    conflicts_before: int = 0  # cast or locations on dates they can't be used
    conflicts_after: int = 0

    @property
    def saving(self) -> float:
        return round(self.cost_before - self.cost_after, 2)


def reorder_days(b: Breakdown, plan: scheduling.Schedule, settings: BudgetSettings) -> Reorder:
    """The order of the shooting days that pays the cast for the fewest holds.

    Only the order of whole days changes, so every day keeps its scenes, and
    day work and night work stay in the blocks they are in (turning the crew
    around between day and night is what a schedule avoids). A move of one day
    to another place in its block is kept when it lowers the cost, until no
    move does."""
    rows = {s.number: s for s in b.scenes}
    days = [[rows[n] for n in d.scenes if n in rows] for d in plan.days]
    level = LEVELS[settings.level]["rates"]
    words = {c.name: c.words for c in b.characters}
    people: dict[str, list[int]] = {}
    for i, day in enumerate(days):
        for s in day:
            for name in {*s.characters, *s.silent}:
                people.setdefault(name, []).append(i)
    worked = {name: set(d) for name, d in people.items()}
    roles = _roles(b, worked)
    rate = {name: settings.rates.get(f"cast:{name}", level[f"cast.{roles[name]}"]) for name in people}
    social = 1 + percentages(settings)["social"]

    # Conflicts of each day on each date of the calendar: a day moves to another
    # date when it moves, as the dates stay where they are.
    from slugline import constraints as limits

    rules = limits.Constraints.from_dict(plan.constraints)
    dates = [limits._day(d.date) for d in plan.days]
    clash = [[len(limits.conflicts_on(plan.days[d], when, rows, rules)) if when else 0 for when in dates]
             for d in range(len(days))]

    def cost(order: list[int]) -> tuple[float, int, int]:
        position = {day: i for i, day in enumerate(order)}
        total, holds = 0.0, 0
        for name, on in people.items():
            work, hold = _paid_days({position[d] for d in on})
            total += rate[name] * (work + hold)
            holds += hold
        conflicts = sum(clash[d][slot] for slot, d in enumerate(order))
        return total * social, holds, conflicts

    def score(value: tuple[float, int, int]) -> float:
        return value[2] * 1e9 + value[0]  # no saving is worth a conflict

    # Blocks of consecutive days with the same shift; days move only inside their block.
    shift = [1 if any(s.day_night == "NIGHT" for s in day) and all(s.day_night == "NIGHT" for s in day) else 0
             for day in days]
    blocks, start = [], 0
    for i in range(1, len(days) + 1):
        if i == len(days) or shift[i] != shift[start]:
            blocks.append((start, i))
            start = i

    order = list(range(len(days)))
    first = best_value = cost(order)
    deadline = time.monotonic() + 5  # a long schedule gets the best found in a few seconds
    for _ in range(30):  # passes; each one tries every move
        improved = False
        for lo, hi in blocks:
            for i in range(lo, hi):
                if time.monotonic() > deadline:
                    break
                for j in range(lo, hi):
                    if i == j:
                        continue
                    candidate = order[:]
                    candidate.insert(j, candidate.pop(i))
                    value = cost(candidate)
                    if score(value) < score(best_value) - 0.5:
                        order, best_value, improved = candidate, value, True
        if not improved:
            break
    return Reorder(order, round(first[0], 2), round(best_value[0], 2), first[1], best_value[1], first[2], best_value[2])


def apply_order(plan: scheduling.Schedule, order: list[int]) -> scheduling.Schedule:
    """The schedule with its days in a new order. Dates stay where they were
    on the calendar: the days that move take the dates of the places they go."""
    moved = [copy.deepcopy(plan.days[i]) for i in order]
    for day, slot in zip(moved, plan.days):
        day.date = slot.date
    return replace(plan, days=moved)


# --- the budget -----------------------------------------------------------------

def compute(b: Breakdown, plan: scheduling.Schedule | None, sheet: ElementSheet | None,
            settings: BudgetSettings) -> dict:
    """The budget as the dashboard and the exports use it."""
    shoot = _plan(b, plan, LEVELS[settings.level].get("pages_per_day", scheduling.DEFAULT_PAGES_PER_DAY))
    lines = build_lines(b, shoot, sheet, settings)
    subtotal = round(sum(line.total for line in lines), 2)
    pct = percentages(settings)
    contingency = round(subtotal * pct["contingency"])
    total = subtotal + contingency
    chapters = []
    for code, label in CHAPTERS:
        items = [line for line in lines if line.chapter == code]
        chapters.append({
            "code": code, "label": label, "total": round(sum(line.total for line in items), 2),
            "lines": [{**asdict(line), "total": line.total} for line in items],
        })
    to_quote = [line for line in lines if line.to_quote and not line.quoted]
    costs = scene_costs(lines, shoot)
    rows = {s.number: s for s in b.scenes}
    ranking = sorted(costs.items(), key=lambda kv: -kv[1])
    return {
        "currency": CURRENCY,
        "level": settings.level,
        "levels": [{"key": k, "label": v["label"]} for k, v in LEVELS.items()],
        "country": settings.country,
        "countries": [{"key": k, "label": label, "social": social} for k, (label, social) in COUNTRIES.items()],
        "subtotal": subtotal,
        "contingency": {"pct": pct["contingency"], "amount": contingency},
        "total": total,
        "percentages": pct,
        "days": len(shoot.days),
        "scheduled_days": shoot.scheduled,
        "estimated_days": len(shoot.days) - shoot.scheduled,
        "chapters": chapters,
        "to_quote": {"count": len(to_quote), "amount": round(sum(line.total for line in to_quote), 2)},
        "scenes": [
            {"number": n, "heading": rows[n].heading, "eighths": rows[n].eighths, "cost": c}
            for n, c in ranking if n in rows
        ],
        "per_day": round(total / len(shoot.days), 2) if shoot.days else None,
        "previous": settings.previous,
        "settings": {k: v for k, v in settings.to_dict().items() if k not in ("snapshot", "previous")},
    }


# --- words -------------------------------------------------------------------------
# Spanish for the chapters, concepts and units, in Spanish production terms. The
# dashboard has the same text in web/src/es.ts (a test checks they match).
BUDGET_ES = {
    "Script and music": "Guion y música", "Artistic staff": "Personal artístico", "Crew": "Equipo técnico",
    "Sets and locations": "Escenografía", "Studios and sound": "Estudios de rodaje y sonorización",
    "Equipment, shooting and transport": "Maquinaria, rodaje y transportes",
    "Travel, hotels and meals": "Viajes, hoteles y comidas", "Digital media": "Soporte digital",
    "Post-production": "Postproducción", "Insurance": "Seguros", "Overheads": "Gastos generales",
    "Publicity and finance": "Gastos de explotación, comercial y financieros",
    "Script and rights": "Guion y derechos", "Original music": "Música original", "Extras": "Figuración",
    "Stunt team": "Especialistas", "Director": "Director/a", "First assistant director": "Ayudante de dirección",
    "Script supervisor": "Script", "Line producer": "Director/a de producción",
    "Production manager": "Jefe/a de producción", "Production assistant": "Auxiliar de producción",
    "Director of photography": "Director/a de fotografía", "Focus puller": "Foquista",
    "Camera assistant": "Auxiliar de cámara", "Sound mixer": "Jefe/a de sonido", "Boom operator": "Microfonista",
    "Production designer": "Director/a de arte", "Set dresser": "Ambientador/a",
    "Costume designer": "Figurinista", "Makeup artist": "Maquillador/a", "Hairdresser": "Peluquero/a",
    "Gaffer": "Jefe/a de eléctricos", "Electrician": "Eléctrico/a", "Key grip": "Jefe/a de maquinistas",
    "Wardrobe for the main cast": "Vestuario del reparto principal",
    "Makeup and hair materials": "Material de maquillaje y peluquería",
    "Sound studio: dubbing, foley and mix": "Estudio de sonido: doblaje, efectos sala y mezcla",
    "Camera package": "Equipo de cámara", "Lighting": "Iluminación", "Grip": "Maquinaria",
    "Production vans": "Furgonetas de producción", "Fuel and parking": "Combustible y aparcamientos",
    "Catering on set": "Catering en rodaje",
    "Travel, hotels and per diems (shooting away from home)": "Viajes, hoteles y dietas (rodaje fuera)",
    "Drives, backup and data management": "Discos, copias de seguridad y gestión de datos",
    "Editing": "Montaje", "Grading and conform": "Etalonaje y conformado",
    "Titles, subtitles and deliveries": "Créditos, subtítulos y entregas",
    "Publicity and festivals": "Publicidad y festivales", "Production insurance": "Seguro de producción",
    "Overheads: office, accounting, legal": "Gastos generales: oficina, gestoría, asesoría jurídica",
    "Other": "Otros", "Overtime": "Horas extra",
    "Social security for the cast": "Seguridad Social del personal artístico",
    "Social security for the crew": "Seguridad Social del equipo técnico",
    "days": "días", "people x days": "personas x días", "items": "unidades", "lump": "global",
    "characters": "personajes", "scenes": "secuencias", "vans x days": "furgonetas x días", "meals": "comidas",
    "units": "unidades",
    "Short film": "Cortometraje", "High-budget feature": "Largometraje de alto presupuesto",
    "Spain": "España", "France": "Francia", "Italy": "Italia", "Germany": "Alemania", "Portugal": "Portugal",
    "United Kingdom": "Reino Unido", "United States": "Estados Unidos", "Mexico": "México",
    "Argentina": "Argentina", "Colombia": "Colombia",
    "No social security": "Sin cargas sociales (facturan o va incluida)",
    "Second unit: crew and equipment": "Segunda unidad: equipo y material",
    "Visual effects across the film": "Efectos visuales del conjunto de la película",
    "Rest of the crew at studio size": "Resto del equipo a escala de gran producción",
    "Set construction on stage": "Construcción de decorados en plató", "Low-budget feature": "Largometraje de bajo presupuesto",
    "Mid-budget feature": "Largometraje de presupuesto medio",
}


def words(lang: str):
    """Translate a budget word or concept, or leave it as it is (names, places)."""
    return (lambda text: BUDGET_ES.get(text, text)) if lang == "es" else (lambda text: text)


# --- storage ----------------------------------------------------------------------

def budget_path(text: str) -> Path:
    return revisions.doc_path(KIND, text)


def load_settings(text: str) -> BudgetSettings | None:
    data = revisions.load_doc(KIND, text)
    try:
        return BudgetSettings.from_dict(data) if data else None
    except (AttributeError, TypeError, ValueError):
        return None


def save_settings(text: str, settings: BudgetSettings) -> Path:
    return revisions.save_doc(KIND, text, settings.to_dict())


def carry_over(text: str) -> BudgetSettings | None:
    """A new draft keeps the budget's level, rates and quotes from the draft
    before it, and remembers that draft's total and days to compare."""
    play = parse(text)
    previous = revisions.find_previous(KIND, text, play, usable=lambda doc: bool(doc.get("snapshot")))
    if previous is None:
        return None
    old = BudgetSettings.from_dict(previous)
    # Quantities, quotes and lines by hand that belong to scenes may not fit the
    # new draft; levels and rates still do.
    return BudgetSettings(level=old.level, country=old.country, rates=old.rates, quotes=old.quotes, extra=old.extra,
                          percentages=old.percentages, previous={**(old.snapshot or {}), "saved_at": previous["meta"].get("saved_at")})


def load_or_carry(text: str) -> BudgetSettings:
    settings = load_settings(text)
    if settings is None:
        settings = carry_over(text) or BudgetSettings()
    return settings


def remember(text: str, settings: BudgetSettings, result: dict) -> None:
    """Keep this draft's total and days, so a later draft can say what changed."""
    snapshot = {"total": result["total"], "days": result["days"]}
    if settings.snapshot != snapshot:
        settings.snapshot = snapshot
        try:
            save_settings(text, settings)
        except OSError:
            pass
