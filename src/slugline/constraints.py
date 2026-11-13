"""What a schedule has to respect: the calendar, when actors and locations are
available, the hours of daylight and the crew's rest between days.

The constraints are saved with the schedule. `check` lists every conflict of
a schedule with them, day by day; `budget.reorder_days` uses `conflicts` to
move days to dates that work. Daylight is worked out here, with the usual
solar formulas, so it needs no internet.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# Cities to work daylight out from: (name, latitude, longitude, time zone).
CITIES = {
    "madrid": ("Madrid", 40.4168, -3.7038, "Europe/Madrid"),
    "barcelona": ("Barcelona", 41.3874, 2.1686, "Europe/Madrid"),
    "valencia": ("Valencia", 39.4699, -0.3763, "Europe/Madrid"),
    "sevilla": ("Sevilla", 37.3891, -5.9845, "Europe/Madrid"),
    "malaga": ("Málaga", 36.7213, -4.4214, "Europe/Madrid"),
    "bilbao": ("Bilbao", 43.2630, -2.9350, "Europe/Madrid"),
    "a_coruna": ("A Coruña", 43.3623, -8.4115, "Europe/Madrid"),
    "zaragoza": ("Zaragoza", 41.6488, -0.8891, "Europe/Madrid"),
    "las_palmas": ("Las Palmas de Gran Canaria", 28.1235, -15.4363, "Atlantic/Canary"),
    "lisboa": ("Lisboa", 38.7223, -9.1393, "Europe/Lisbon"),
    "paris": ("París", 48.8566, 2.3522, "Europe/Paris"),
    "london": ("Londres", 51.5074, -0.1278, "Europe/London"),
    "roma": ("Roma", 41.9028, 12.4964, "Europe/Rome"),
    "berlin": ("Berlín", 52.5200, 13.4050, "Europe/Berlin"),
    "mexico": ("Ciudad de México", 19.4326, -99.1332, "America/Mexico_City"),
    "bogota": ("Bogotá", 4.7110, -74.0721, "America/Bogota"),
    "buenos_aires": ("Buenos Aires", -34.6037, -58.3816, "America/Argentina/Buenos_Aires"),
    "santiago": ("Santiago de Chile", -33.4489, -70.6693, "America/Santiago"),
    "lima": ("Lima", -12.0464, -77.0428, "America/Lima"),
    "los_angeles": ("Los Ángeles", 34.0522, -118.2437, "America/Los_Angeles"),
    "new_york": ("Nueva York", 40.7128, -74.0060, "America/New_York"),
}
DEFAULT_DAY_HOURS = 11.0  # ten hours of shooting and one for lunch
DEFAULT_REST_HOURS = 12.0
DEFAULT_DAY_CALL = "07:00"  # assumed when a day has no call time
DEFAULT_NIGHT_CALL = "18:00"
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_PERIODS = 60


def _day(text: str) -> date | None:
    try:
        return date.fromisoformat(text) if text and ISO.match(text) else None
    except ValueError:
        return None


@dataclass
class Constraints:
    start: str = ""  # first shooting date, ISO
    weekdays: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])  # 0 Monday ... 6 Sunday
    city: str = ""  # a key of CITIES, for daylight
    day_hours: float = DEFAULT_DAY_HOURS  # from call to wrap
    rest_hours: float = DEFAULT_REST_HOURS  # between wrap and the next call
    # Dates someone or somewhere can't be used: name -> [[from, to], ...] (ISO, inclusive).
    cast_off: dict[str, list[list[str]]] = field(default_factory=dict)
    location_off: dict[str, list[list[str]]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> Constraints:
        data = data or {}

        def periods(value) -> dict[str, list[list[str]]]:
            out: dict[str, list[list[str]]] = {}
            for name, items in (value or {}).items():
                clean = []
                for item in items or []:
                    if isinstance(item, (list, tuple)) and len(item) == 2:
                        a, b = _day(str(item[0])), _day(str(item[1]))
                        if a and b:
                            clean.append([min(a, b).isoformat(), max(a, b).isoformat()])
                if clean:
                    out[str(name)] = clean[:MAX_PERIODS]
            return out

        def hours(value, default: float, low: float, high: float) -> float:
            try:
                number = float(value)
            except (TypeError, ValueError):
                return default
            return min(max(number, low), high)

        weekdays = sorted({int(d) for d in data.get("weekdays", [0, 1, 2, 3, 4]) if str(d).isdigit() and 0 <= int(d) <= 6})
        return cls(
            start=data.get("start") if _day(str(data.get("start", ""))) else "",
            weekdays=weekdays or [0, 1, 2, 3, 4],
            city=data.get("city") if data.get("city") in CITIES else "",
            day_hours=hours(data.get("day_hours"), DEFAULT_DAY_HOURS, 4, 18),
            rest_hours=hours(data.get("rest_hours"), DEFAULT_REST_HOURS, 0, 24),
            cast_off=periods(data.get("cast_off")),
            location_off=periods(data.get("location_off")),
        )

    def off(self, table: dict[str, list[list[str]]], name: str, when: date) -> bool:
        return any(date.fromisoformat(a) <= when <= date.fromisoformat(b) for a, b in table.get(name, []))


# --- calendar -----------------------------------------------------------------

def shooting_dates(constraints: Constraints, count: int) -> list[str]:
    """The next `count` shooting dates from the start, on the shooting weekdays."""
    start = _day(constraints.start)
    if not start or not constraints.weekdays:
        return []
    dates, current = [], start
    while len(dates) < count:
        if current.weekday() in constraints.weekdays:
            dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


# --- daylight -----------------------------------------------------------------

def sun_times(when: date, city: str) -> tuple[str, str] | None:
    """Sunrise and sunset, local time (HH:MM), with the NOAA solar formulas.
    None in a place and date where the sun doesn't rise or set."""
    if city not in CITIES:
        return None
    _, lat, lon, zone = CITIES[city]
    gamma = 2 * math.pi / 365 * (when.timetuple().tm_yday - 1)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma)
                       - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma))
    decl = (0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma) - 0.006758 * math.cos(2 * gamma)
            + 0.000907 * math.sin(2 * gamma) - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma))
    phi = math.radians(lat)
    cos_ha = math.cos(math.radians(90.833)) / (math.cos(phi) * math.cos(decl)) - math.tan(phi) * math.tan(decl)
    if not -1 <= cos_ha <= 1:
        return None
    ha = math.degrees(math.acos(cos_ha))
    midnight = datetime(when.year, when.month, when.day, tzinfo=ZoneInfo("UTC"))
    local = ZoneInfo(zone)

    def at(minutes: float) -> str:
        return (midnight + timedelta(minutes=minutes)).astimezone(local).strftime("%H:%M")

    return at(720 - 4 * (lon + ha) - eqtime), at(720 - 4 * (lon - ha) - eqtime)


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


# --- conflicts ----------------------------------------------------------------

@dataclass
class Problem:
    kind: str  # cast, location, dawn, rest
    day: int  # 1-based position in the schedule
    date: str
    name: str = ""  # the actor's character or the location
    detail: dict = field(default_factory=dict)


def _call(day, rows: dict) -> str:
    scenes = [rows[n] for n in day.scenes if n in rows]
    if day.call_time:
        return day.call_time
    night = scenes and all(s.day_night == "NIGHT" for s in scenes)
    return DEFAULT_NIGHT_CALL if night else DEFAULT_DAY_CALL


def conflicts_on(day, when: date, rows: dict, constraints: Constraints) -> list[tuple[str, str]]:
    """Cast and locations of a day that can't be used on a date."""
    scenes = [rows[n] for n in day.scenes if n in rows]
    found = []
    for name in dict.fromkeys(c for s in scenes for c in [*s.characters, *s.silent]):
        if constraints.off(constraints.cast_off, name, when):
            found.append(("cast", name))
    for place in dict.fromkeys(s.location for s in scenes if s.location):
        if constraints.off(constraints.location_off, place, when):
            found.append(("location", place))
    return found


def check(schedule, b, constraints: Constraints) -> list[Problem]:
    """Every conflict of the schedule with its constraints."""
    rows = {s.number: s for s in b.scenes}
    problems: list[Problem] = []
    previous = None  # (date, wrap datetime)
    for i, day in enumerate(schedule.days, start=1):
        when = _day(day.date)
        if not when:
            previous = None
            continue
        for kind, name in conflicts_on(day, when, rows, constraints):
            problems.append(Problem(kind, i, day.date, name))
        call = _call(day, rows)
        start = datetime.combine(when, datetime.strptime(call, "%H:%M").time())
        # An exterior at dawn needs the unit there before the sun is up.
        sun = sun_times(when, constraints.city)
        if sun:
            dawn = [rows[n].number for n in day.scenes if n in rows and rows[n].day_night == "DAWN"
                    and (rows[n].int_ext or "") != "INT"]
            if dawn and _minutes(call) > _minutes(sun[0]) - 60:
                problems.append(Problem("dawn", i, day.date, detail={"call": call, "sunrise": sun[0], "scenes": dawn}))
        if previous and when - previous[0] == timedelta(days=1):
            rest = (start - previous[1]).total_seconds() / 3600
            if rest < constraints.rest_hours:
                problems.append(Problem("rest", i, day.date, detail={
                    "rest": round(rest, 1), "minimum": constraints.rest_hours, "call": call,
                    "assumed": not day.call_time or not schedule.days[i - 2].call_time,
                }))
        previous = (when, start + timedelta(hours=constraints.day_hours))
    return problems


def daylight(schedule, constraints: Constraints) -> list[dict | None]:
    """Sunrise, sunset and hours of light of each day with a date."""
    out = []
    for day in schedule.days:
        when = _day(day.date)
        sun = sun_times(when, constraints.city) if when else None
        if not sun:
            out.append(None)
            continue
        hours = (_minutes(sun[1]) - _minutes(sun[0])) / 60
        out.append({"sunrise": sun[0], "sunset": sun[1], "hours": round(hours, 1)})
    return out


def to_payload(schedule, b, constraints: Constraints) -> dict:
    return {
        "constraints": constraints.to_dict(),
        "cities": [{"key": k, "name": v[0]} for k, v in CITIES.items()],
        "problems": [asdict(p) for p in check(schedule, b, constraints)],
        "daylight": daylight(schedule, constraints),
    }
