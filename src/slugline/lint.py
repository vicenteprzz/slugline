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
    # For two spellings of one name: both, most used first, so the app can merge them.
    names: list[str] | None = None
    # The message before its values were filled in, and the values, so the app
    # and the PDFs can print it in another language. None for Claude's notes.
    template: str | None = None
    params: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# Every message the checks write. The app and the PDF exports translate them.
NO_INT_EXT = 'Heading "{heading}" has no INT./EXT.'
NO_TIME = 'Heading "{heading}" has no time of day.'
EMPTY_SCENE = 'Scene "{heading}" is empty.'
EMPTY_DIALOGUE = "{character} has a cue with no dialogue."
LONG_ACTION = "1 action paragraph longer than {lines} lines; shorter blocks read faster."
LONG_ACTIONS = "{n} action paragraphs longer than {lines} lines; shorter blocks read faster."
SIMILAR = {
    ("characters", "spacing"): "Characters {a} and {b} differ only in punctuation or spacing ({na} and {nb} cues).",
    ("characters", "spelling"): "Characters {a} and {b} look like the same name spelled two ways ({na} and {nb} cues).",
    ("locations", "spacing"): 'Locations "{a}" and "{b}" differ only in punctuation or spacing.',
    ("locations", "spelling"): 'Locations "{a}" and "{b}" look like the same name spelled two ways.',
}
PARTIAL_NUMBERING = "Only {n} of {total} scenes have a scene number."
DUPLICATE_NUMBER = "Scene number {number} is used {n} times."
NO_TITLE = "The script has no title page."
MISSING_SCENES = "No scene {missing} between {a} and {b}: it may be hard to read in the file. Check those pages; you can add the scene in a Fountain copy."
OMITTED_SCENES = "Scenes cut from this draft (marked OMITTED): {missing}."
# Signs that a file was not read well, shown at the top of the dashboard.
READ_NO_DIALOGUE = "No speaking characters were found in {scenes} scenes: the file may not have been read correctly."
READ_FEW_SCENES = "Only {scenes} scenes in about {pages} pages: some scene headings may not have been recognised."
READ_NO_LIGHT = "{n} of {total} scenes have no day or night: the times in the headings may not have been read."
READ_CODES = ("read-no-dialogue", "read-few-scenes", "read-no-light")


MESSAGES_ES = {
    NO_INT_EXT: 'El encabezado "{heading}" no dice si es INT. o EXT.',
    NO_TIME: 'El encabezado "{heading}" no dice el momento del día.',
    EMPTY_SCENE: 'La secuencia "{heading}" está vacía.',
    EMPTY_DIALOGUE: "{character} tiene una intervención sin diálogo.",
    LONG_ACTION: "1 párrafo de acción de más de {lines} líneas; los bloques cortos se leen mejor.",
    LONG_ACTIONS: "{n} párrafos de acción de más de {lines} líneas; los bloques cortos se leen mejor.",
    SIMILAR["characters", "spacing"]: "Los personajes {a} y {b} solo se diferencian en la puntuación o los espacios ({na} y {nb} intervenciones).",
    SIMILAR["characters", "spelling"]: "Los personajes {a} y {b} parecen el mismo nombre escrito de dos formas ({na} y {nb} intervenciones).",
    SIMILAR["locations", "spacing"]: 'Los decorados "{a}" y "{b}" solo se diferencian en la puntuación o los espacios.',
    SIMILAR["locations", "spelling"]: 'Los decorados "{a}" y "{b}" parecen el mismo nombre escrito de dos formas.',
    PARTIAL_NUMBERING: "Solo {n} de {total} secuencias tienen número.",
    DUPLICATE_NUMBER: "El número de secuencia {number} se usa {n} veces.",
    NO_TITLE: "El guion no tiene portada.",
    READ_NO_DIALOGUE: "No se ha encontrado ningún personaje con diálogo en {scenes} secuencias: puede que el archivo no se haya leído bien.",
    READ_FEW_SCENES: "Solo {scenes} secuencias en unas {pages} páginas: puede que no se hayan reconocido algunos encabezados.",
    READ_NO_LIGHT: "{n} de {total} secuencias no tienen día ni noche: puede que no se haya leído el momento del día de los encabezados.",
}


def _issue(severity: str, code: str, template: str, scene: str | None = None,
           names: list[str] | None = None, **params) -> Issue:
    return Issue(severity, code, template.format(**params), scene, names=names, template=template, params=params)


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
                pairs.append((a, b, "spacing"))
            elif _one_token_typo(a, b):
                pairs.append((a, b, "spelling"))
    return pairs


def lint(play: Screenplay) -> list[Issue]:
    issues: list[Issue] = []

    for s in play.scenes:
        if s.int_ext is None and not s.continues:
            issues.append(_issue("warning", "no-int-ext", NO_INT_EXT, s.number, heading=s.heading))
        if s.time_of_day is None and not s.continues:
            issues.append(_issue("warning", "no-time", NO_TIME, s.number, heading=s.heading))
        if not s.elements:
            issues.append(_issue("warning", "empty-scene", EMPTY_SCENE, s.number, heading=s.heading))
        for d in s.dialogues:
            if not d.lines:
                issues.append(_issue("warning", "empty-dialogue", EMPTY_DIALOGUE, s.number, character=d.character))
        long_blocks = sum(
            1 for e in s.elements
            if isinstance(e, Action)
            and sum(_wrapped(p, ACTION_WIDTH) for p in e.text.split("\n")) > LONG_ACTION_LINES
        )
        if long_blocks:
            issues.append(_issue("info", "long-action", LONG_ACTIONS if long_blocks > 1 else LONG_ACTION,
                                 s.number, n=long_blocks, lines=LONG_ACTION_LINES))

    blocks = Counter(d.character for s in play.scenes for d in s.dialogues)
    for a, b, why in _similar_pairs(sorted(blocks)):
        issues.append(_issue("warning", "similar-characters", SIMILAR["characters", why],
                             names=sorted([a, b], key=lambda n: -blocks[n]), a=a, b=b, na=blocks[a], nb=blocks[b]))
    locations = Counter(s.location for s in play.scenes if s.location)
    for a, b, why in _similar_pairs(sorted(locations)):
        issues.append(_issue("warning", "similar-locations", SIMILAR["locations", why],
                             names=sorted([a, b], key=lambda n: -locations[n]), a=a, b=b))

    numbered = [s for s in play.scenes if s.scene_number]
    if numbered and len(numbered) < len(play.scenes):
        issues.append(_issue("warning", "partial-numbering", PARTIAL_NUMBERING,
                             n=len(numbered), total=len(play.scenes)))
    for number, count in Counter(s.scene_number for s in numbered).items():
        if count > 1:
            issues.append(_issue("warning", "duplicate-number", DUPLICATE_NUMBER, number, number=number, n=count))

    issues += _numbering_gaps(play)

    if play.scenes and not play.title:
        issues.append(_issue("info", "no-title", NO_TITLE))
    return _reading_checks(play) + issues


GAP_LIMIT = 15  # a longer jump is a new block of numbers (an episode), not lost scenes


def _numbering_gaps(play: Screenplay) -> list[Issue]:
    """Numbers missing from the script's own numbering: the ones it marks as
    cut, and the ones that may not have been read. Lettered scenes (106A)
    count for their number; letters that only mark inserts are not a series."""
    part = re.compile(r"^([A-Z]{0,2})(\d{1,4})[A-Z]{0,2}$")
    series: dict[str, set[int]] = {}
    for s in play.scenes:
        m = part.match(s.scene_number or "")
        if m:
            series.setdefault(m.group(1), set()).add(int(m.group(2)))
    cut: dict[str, set[int]] = {}
    for number in play.omitted:
        m = part.match(number)
        if m:
            cut.setdefault(m.group(1), set()).add(int(m.group(2)))
    issues: list[Issue] = []
    omitted: list[str] = []
    for prefix, found in series.items():
        if prefix and (len(found) < 5 or len(found) < 0.6 * (max(found) - min(found) + 1)):
            continue
        ordered = sorted(found)
        for a, b in zip(ordered, ordered[1:]):
            if not 1 < b - a <= GAP_LIMIT:
                continue
            gone = [n for n in range(a + 1, b) if n not in cut.get(prefix, set())]
            omitted += [f"{prefix}{n}" for n in range(a + 1, b) if n in cut.get(prefix, set())]
            if gone:
                issues.append(_issue("warning", "missing-scenes", MISSING_SCENES, f"{prefix}{b}",
                                     missing=", ".join(f"{prefix}{n}" for n in gone), a=f"{prefix}{a}", b=f"{prefix}{b}"))
    if omitted:
        issues.append(_issue("info", "omitted-scenes", OMITTED_SCENES, missing=", ".join(omitted)))
    return issues


def _reading_checks(play: Screenplay) -> list[Issue]:
    """Signs that the file was not read well: a script with no dialogue at
    all, far too few scenes for its length, or most scenes without day or
    night. Better to say so than to let someone plan with a bad reading."""
    scenes = len(play.scenes)
    found: list[Issue] = []
    if scenes >= 5 and not any(s.dialogues for s in play.scenes):
        found.append(_issue("warning", "read-no-dialogue", READ_NO_DIALOGUE, scenes=scenes))
    pages = play.page_count
    if pages >= 20 and scenes and pages / scenes > 4:
        found.append(_issue("warning", "read-few-scenes", READ_FEW_SCENES, scenes=scenes, pages=round(pages)))
    dark = sum(1 for s in play.scenes if not s.day_night)
    if scenes >= 10 and dark * 2 > scenes:
        found.append(_issue("warning", "read-no-light", READ_NO_LIGHT, n=dark, total=scenes))
    return found
