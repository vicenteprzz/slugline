"""Production breakdown: aggregate a parsed Screenplay into reports."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field

from slugline.parser import LINES_PER_PAGE, Scene, Screenplay, format_eighths


@dataclass
class CharacterStats:
    name: str
    scenes: list[str] = field(default_factory=list)
    dialogue_blocks: int = 0
    words: int = 0
    # Scenes where the character is named in the action but has no dialogue.
    silent_scenes: list[str] = field(default_factory=list)


@dataclass
class LocationStats:
    location: str
    scenes: list[str] = field(default_factory=list)
    eighths: int = 0


@dataclass
class SceneRow:
    number: str
    heading: str
    int_ext: str | None
    location: str
    time_of_day: str | None
    eighths: int
    characters: list[str]
    day_night: str | None = None
    # Characters named in the action who don't speak in this scene.
    silent: list[str] = field(default_factory=list)
    # Words of dialogue per speaking character.
    words: dict[str, int] = field(default_factory=dict)
    # Estimated page where the scene starts (1.0 = top of page one).
    start_page: float = 1.0
    # The day of the story it happens on (see `continuity`), and its label: D3, N3.
    story_day: int | None = None
    story_label: str = ""


@dataclass
class Breakdown:
    title: str | None
    scene_count: int
    page_count: float
    int_ext: dict[str, int]
    time_of_day: dict[str, int]
    # Scenes per lighting condition: DAY / NIGHT / DAWN / DUSK.
    day_night: dict[str, int]
    scenes: list[SceneRow]
    characters: list[CharacterStats]
    locations: list[LocationStats]

    def to_dict(self) -> dict:
        return asdict(self)


def _mention(name: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", re.IGNORECASE)


def silent_characters(play: Screenplay) -> dict[int, list[str]]:
    """For each scene index, the speaking characters of the script that the
    action names (as "MR. B" or "Mr. B") but who have no dialogue there."""
    cast = {d.character: None for s in play.scenes for d in s.dialogues}
    patterns = {name: _mention(name) for name in cast}
    result: dict[int, list[str]] = {}
    for scene in play.scenes:
        speaking = set(scene.characters)
        action = scene.action_text
        result[scene.index] = [
            name
            for name, pattern in patterns.items()
            if name not in speaking
            # A lowercase hit ("the sheriff") is a common noun, not the character.
            and any(m.group(0)[0].isupper() for m in pattern.finditer(action))
        ]
    return result


def _words(scene: Scene) -> dict[str, int]:
    words: dict[str, int] = {}
    for d in scene.dialogues:
        words[d.character] = words.get(d.character, 0) + d.word_count
    return words


def character_stats(play: Screenplay) -> list[CharacterStats]:
    """Per-character stats, sorted by words spoken (most first)."""
    stats: dict[str, CharacterStats] = {}
    silent = silent_characters(play)
    for scene in play.scenes:
        for d in scene.dialogues:
            s = stats.setdefault(d.character, CharacterStats(d.character))
            if scene.number not in s.scenes:
                s.scenes.append(scene.number)
            s.dialogue_blocks += 1
            s.words += d.word_count
    for scene in play.scenes:
        for name in silent[scene.index]:
            stats[name].silent_scenes.append(scene.number)
    return sorted(stats.values(), key=lambda s: (-s.words, s.name))


def location_stats(play: Screenplay) -> list[LocationStats]:
    """Per-location stats, sorted by total length (longest first)."""
    stats: dict[str, LocationStats] = {}
    for scene in play.scenes:
        s = stats.setdefault(scene.location, LocationStats(scene.location))
        s.scenes.append(scene.number)
        s.eighths += scene.eighths
    return sorted(stats.values(), key=lambda s: (-s.eighths, s.location))


def breakdown(play: Screenplay) -> Breakdown:
    silent = silent_characters(play)
    start_pages, lines = {}, 0
    for s in play.scenes:
        start_pages[s.index] = round(1 + lines / LINES_PER_PAGE, 2)
        lines += s.printed_lines
    return Breakdown(
        title=play.title,
        scene_count=len(play.scenes),
        page_count=round(play.page_count, 1),
        int_ext=dict(Counter(s.int_ext or "?" for s in play.scenes)),
        time_of_day=dict(Counter(s.time_of_day or "?" for s in play.scenes)),
        day_night=dict(Counter(s.day_night or "?" for s in play.scenes)),
        scenes=[
            SceneRow(
                number=s.number,
                heading=s.heading,
                int_ext=s.int_ext,
                location=s.location,
                time_of_day=s.time_of_day,
                eighths=s.eighths,
                characters=s.characters,
                day_night=s.day_night,
                silent=silent[s.index],
                words=_words(s),
                start_page=start_pages[s.index],
            )
            for s in play.scenes
        ],
        characters=character_stats(play),
        locations=location_stats(play),
    )


def _table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    out = [fmt.format(*headers)]
    out += [fmt.format(*r) for r in rows]
    return "\n".join("  " + line.rstrip() for line in out)


def render_text(b: Breakdown) -> str:
    title = (b.title or "UNTITLED").upper()
    parts = [f"{title} — {b.scene_count} scenes, ~{b.page_count} pages (estimated)"]

    parts.append("\nSCENES")
    parts.append(_table(
        ["#", "INT/EXT", "LOCATION", "TIME", "LENGTH", "CHARACTERS"],
        [[r.number, r.int_ext or "-", r.location, r.time_of_day or "-",
          format_eighths(r.eighths),
          ", ".join(r.characters) + (f" (silent: {', '.join(r.silent)})" if r.silent else "")]
         for r in b.scenes],
    ))

    parts.append("\nCHARACTERS")
    parts.append(_table(
        ["NAME", "SCENES", "LINES", "WORDS"],
        [[c.name, str(len(c.scenes)), str(c.dialogue_blocks), str(c.words)] for c in b.characters],
    ))

    parts.append("\nLOCATIONS")
    parts.append(_table(
        ["LOCATION", "SCENES", "LENGTH"],
        [[loc.location, str(len(loc.scenes)), format_eighths(loc.eighths)] for loc in b.locations],
    ))

    summary = lambda d: ", ".join(f"{k} {v}" for k, v in d.items())  # noqa: E731
    parts.append(f"\nINT/EXT: {summary(b.int_ext)}")
    parts.append(f"DAY/NIGHT: {summary(b.day_night)}")
    return "\n".join(parts)
