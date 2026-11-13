"""Make up screenplays, print them as PDFs many ways, read them back and score
the reading against what was written.

    python tools/synth.py                 # 60 scripts, every layout, a report
    python tools/synth.py --n 200 --seed 7
    python tools/synth.py --show 3        # print the worst few, what was written and what was read

The scripts are random but shaped like real ones: numbered or not, lettered
inserts, scenes cut (OMITTED), two people speaking at once, V.O. and CONT'D,
transitions, montages, times written every way scripts write them, English
and Spanish. Each is printed in several layouts (numbers on one side or
both, page headers with dates, CONTINUED, revision marks, pages off the
margin) and some are damaged like a scan. Everything happens in memory:
no file is written.

Unlike tools/corpus.py, the right answer is known, so the score is exact:
scenes found, headings, day or night, characters, cues and dialogue.
"""

from __future__ import annotations

import argparse
import io
import logging
import random
import re
import sys
import textwrap
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from slugline.parser import parse
from slugline.pdf_import import pdf_text_to_fountain

# --- making up a script ----------------------------------------------------------

FIRST = ["ANNA", "BOB", "CARLA", "DANIEL", "ELENA", "FRANK", "GRACE", "HUGO", "IRENE", "JACK", "LUCÍA", "MARCO",
         "NORA", "OSCAR", "PILAR", "RAY", "SOFÍA", "TOM", "VERA", "WALT", "ÁLVARO", "MAE", "JOE", "LIZ"]
TITLED = ["OFFICER RAMOS", "DR. KLEIN", "MRS. HALE", "AUNT RUTH", "THE STRANGER", "COP #2", "YOUNG ANNA",
          "SERGEANT BELL", "EL PADRE", "LA VECINA", "WAITER", "NEWSCASTER"]
PLACES_EN = ["KITCHEN", "DINER", "POLICE STATION", "HALLWAY", "ROOFTOP", "PARKING LOT", "MOTEL ROOM", "CAR",
             "BEACH", "OFFICE", "TRAIN STATION", "HOSPITAL - CORRIDOR", "BAR", "CHURCH", "FOREST", "APARTMENT - BEDROOM"]
PLACES_ES = ["COCINA", "BAR", "COMISARÍA", "PASILLO", "AZOTEA", "COCHE", "PLAYA", "OFICINA", "ESTACIÓN",
             "HOSPITAL - PASILLO", "IGLESIA", "PISO DE ANA - SALÓN"]
TIMES_EN = ["DAY", "NIGHT", "DAWN", "DUSK", "MORNING", "EVENING", "CONTINUOUS", "LATER"]
TIMES_ES = ["DÍA", "NOCHE", "AMANECER", "ATARDECER", "CONTINUACIÓN"]
WORDS = ("the a she he they rain window light door table phone glass street car slowly looks turns walks "
         "waits listens stops runs smiles cries nothing again never always quiet dark cold outside inside "
         "money letter gun coffee night morning tomorrow sorry please wait here there why now").split()
PALABRAS = ("la el ella él lluvia ventana luz puerta mesa teléfono vaso calle coche despacio mira gira camina "
            "espera escucha corre sonríe nada otra vez nunca siempre silencio oscuro frío fuera dentro dinero "
            "carta café noche mañana perdón por favor aquí ahí por qué ahora").split()
DAY_NIGHT = {"DAY": "DAY", "MORNING": "DAY", "NIGHT": "NIGHT", "EVENING": "NIGHT", "DAWN": "DAWN", "DUSK": "DUSK",
             "DÍA": "DAY", "NOCHE": "NIGHT", "AMANECER": "DAWN", "ATARDECER": "DUSK"}


@dataclass
class Scene:
    number: str | None
    heading: str
    light: str | None  # DAY, NIGHT, DAWN, DUSK or None (CONTINUOUS, LATER)
    omitted: bool = False
    # ("action", text) | ("cue", name, ext, paren, text, dual_with) | ("transition", text)
    body: list[tuple] = field(default_factory=list)


@dataclass
class Script:
    title: str
    scenes: list[Scene]
    spanish: bool


def _sentence(rng: random.Random, spanish: bool, low: int, high: int) -> str:
    words = [rng.choice(PALABRAS if spanish else WORDS) for _ in range(rng.randint(low, high))]
    return (" ".join(words).capitalize() + rng.choice([".", ".", "?", "!", "..."]))


def make_script(rng: random.Random) -> Script:
    spanish = rng.random() < 0.25
    cast = rng.sample(FIRST, 6) + rng.sample(TITLED, 3)
    leads = cast[:4]
    numbering = rng.choice(["none", "plain", "plain", "inserts", "prologue"])
    style = rng.choice(["dash", "dash", "double", "glued", "bare", "year"])
    places = PLACES_ES if spanish else PLACES_EN
    times = TIMES_ES if spanish else TIMES_EN
    scenes: list[Scene] = []
    n = 0
    if numbering == "prologue":
        for p in range(1, rng.randint(4, 8)):
            scenes.append(Scene(f"P{p}", f"CUT TO {_sentence(rng, False, 3, 6).upper().rstrip('.?!')}", None,
                                body=[("action", _sentence(rng, spanish, 6, 14))]))
    for _ in range(rng.randint(18, 45)):
        n += 1
        number = None if numbering == "none" else str(n)
        if number and rng.random() < 0.06:  # cut from this draft
            scenes.append(Scene(number, "OMITTED", None, omitted=True))
            continue
        prefix = rng.choice(["INT.", "INT.", "EXT.", "INT./EXT."])
        place = rng.choice(places)
        time = rng.choice(times)
        light = DAY_NIGHT.get(time)
        if style == "dash" or light is None:
            heading = f"{prefix} {place} - {time}"
        elif style == "double":
            heading = f"{prefix} {place} -- {time}"
        elif style == "glued":
            heading = f"{prefix} {place}-{time}"
        elif style == "bare":
            heading = f"{prefix} {place} {time}"
        else:
            heading = f"{prefix} {place} - {time} ({rng.randint(1950, 2020)})"
        scene = Scene(number, heading, light)
        scene.body.append(("action", _sentence(rng, spanish, 8, 40)))
        for _ in range(rng.randint(1, 7)):
            roll = rng.random()
            who = rng.choice(leads if rng.random() < 0.7 else cast)
            if roll < 0.6:
                ext = rng.choice(["", "", "", "", "V.O.", "O.S.", "CONT'D"])
                paren = rng.choice(["", "", "", "(quietly)", "(beat)", "(en voz baja)" if spanish else "(laughing)"])
                scene.body.append(("cue", who, ext, paren, _sentence(rng, spanish, 3, 30), None))
            elif roll < 0.68:
                other = rng.choice([c for c in leads if c != who])
                scene.body.append(("cue", who, "", "", _sentence(rng, spanish, 2, 8), other))
            elif roll < 0.8:
                scene.body.append(("action", _sentence(rng, spanish, 6, 50)))
            elif roll < 0.85:
                scene.body.append(("action", " ".join(f"-- {_sentence(rng, spanish, 3, 7)}" for _ in range(3))))
            else:
                scene.body.append(("action", _sentence(rng, spanish, 5, 12)))
        if rng.random() < 0.3:
            scene.body.append(("transition", rng.choice(["CUT TO:", "DISSOLVE TO:", "FADE OUT."] if not spanish else ["CORTE A:", "FUNDIDO A:"])))
        scenes.append(scene)
        if number and numbering == "inserts" and rng.random() < 0.12:
            letter = Scene(f"A{n}", f"{rng.choice(['INT.', 'EXT.'])} {rng.choice(places)} - {rng.choice(times)}", None)
            letter.light = DAY_NIGHT.get(letter.heading.rsplit(" - ", 1)[-1])
            letter.body.append(("action", _sentence(rng, spanish, 6, 20)))
            scenes.append(letter)
    title = rng.choice(["LAST TRAIN", "THE QUIET HOUSE", "NORTH", "LA ESPERA", "SALT", "BLUE HOUR"])
    return Script(title, scenes, spanish)


# --- printing it ---------------------------------------------------------------

@dataclass
class Layout:
    name: str
    numbers: str = "both"  # none, left, both
    header: str = ""  # a line printed on top of every page; {n} is the page
    continued: bool = False  # CONTINUED: / (CONTINUED) and (MORE) / (CONT'D) across pages
    stars: bool = False  # revision asterisks in the right margin
    drift: int = 0  # points a page can sit off the margin, either way


LAYOUTS = [
    Layout("clean", numbers="none"),
    Layout("numbered", numbers="both"),
    Layout("left-numbers", numbers="left"),
    Layout("shooting", numbers="both", header="{title} - Shooting Script - 10/12/2024      {n}.", continued=True, stars=True),
    Layout("revised", numbers="both", header="Rev. 12/17/20 (Blue)", continued=True),
    Layout("drifting", numbers="both", drift=24),
]

PAGE_W, PAGE_H, LINE = 612, 792, 12
ACTION_X, DIALOGUE_X, PAREN_X, CUE_X, RIGHT_X = 108, 180, 223, 266, 540
TOP, LINES_PER_PAGE = 72 + 12, 54


def _lines(script: Script, layout: Layout) -> list[list[tuple[float, str, str]]]:
    """Pages of (x, text, kind) lines, laid out like a typed screenplay."""
    out: list[tuple[float, str, str]] = []

    def blank():
        out.append((0, "", "blank"))

    for scene in script.scenes:
        blank()
        number = scene.number if layout.numbers != "none" and scene.number else ""
        out.append((ACTION_X, scene.heading, f"heading|{number}"))
        for item in scene.body:
            blank()
            if item[0] == "action":
                for line in textwrap.wrap(item[1], 60):
                    out.append((ACTION_X, line, "action"))
            elif item[0] == "transition":
                out.append((RIGHT_X - len(item[1]) * 7.2, item[1], "action"))
            elif item[5]:  # two at once: side by side
                _, who, _, _, text, other = item
                out.append((0, f"{who}|{other}", "dual-cue"))
                left = textwrap.wrap(text, 24)
                right = textwrap.wrap(text[::-1].capitalize(), 24)
                for k in range(max(len(left), len(right))):
                    out.append((0, f"{left[k] if k < len(left) else ''}|{right[k] if k < len(right) else ''}", "dual"))
            else:
                _, who, ext, paren, text, _ = item
                out.append((CUE_X, f"{who} ({ext})" if ext else who, "cue"))
                if paren:
                    out.append((PAREN_X, paren, "paren"))
                for line in textwrap.wrap(text, 35):
                    out.append((DIALOGUE_X, line, "dialogue"))
    pages = [out[i:i + LINES_PER_PAGE] for i in range(0, len(out), LINES_PER_PAGE)]
    if layout.continued:
        for k in range(len(pages) - 1):
            last = next((l for l in reversed(pages[k]) if l[2] != "blank"), None)
            if last and last[2] == "dialogue":
                pages[k].append((CUE_X + 14, "(MORE)", "more"))
            pages[k].append((RIGHT_X - 80, "(CONTINUED)", "more"))
            pages[k + 1].insert(0, (ACTION_X, "CONTINUED:", "more"))
    return pages


def render(script: Script, layout: Layout, rng: random.Random) -> bytes:
    from reportlab.pdfgen.canvas import Canvas

    buffer = io.BytesIO()
    pdf = Canvas(buffer, pagesize=(PAGE_W, PAGE_H))
    # Title page.
    pdf.setFont("Courier", 12)
    pdf.drawCentredString(PAGE_W / 2, 500, script.title)
    pdf.drawCentredString(PAGE_W / 2, 470, "written by")
    pdf.drawCentredString(PAGE_W / 2, 446, "Pat Writer")
    pdf.showPage()
    for n, page in enumerate(_lines(script, layout), start=1):
        dx = rng.randint(-layout.drift, layout.drift) if layout.drift else 0
        pdf.setFont("Courier", 12)
        y = PAGE_H - 48
        if layout.header:
            pdf.drawString(ACTION_X + dx, y, layout.header.format(title=script.title, n=n))
        elif n > 1:
            pdf.drawRightString(RIGHT_X + dx, y, f"{n}.")
        y = PAGE_H - TOP
        for x, text, kind in page:
            if kind.startswith("heading"):
                number = kind.split("|")[1]
                if number:
                    pdf.drawString(72 + dx, y, number)
                    if layout.numbers == "both":
                        pdf.drawRightString(RIGHT_X + 30 + dx, y, number)
                pdf.drawString(x + dx, y, text)
            elif kind == "dual-cue":
                a, b = text.split("|")
                pdf.drawString(198 + dx, y, a)
                pdf.drawString(396 + dx, y, b)
            elif kind == "dual":
                a, b = text.split("|")
                pdf.drawString(144 + dx, y, a)
                pdf.drawString(342 + dx, y, b)
            elif text:
                pdf.drawString(x + dx, y, text)
            if layout.stars and kind in ("action", "dialogue") and rng.random() < 0.04:
                pdf.drawString(RIGHT_X + 50 + dx, y, "*")
            y -= LINE
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


# --- damage like a scan -----------------------------------------------------------

LOOKALIKE = {"I": "l", "l": "I", "O": "0", "0": "O", "S": "5", "1": "l", "E": "F", "m": "rn", "a": "o", "e": "c"}


def damage(text: str, rng: random.Random, rate: float) -> str:
    """Letters swapped for lookalikes, specks in the margin, numbers split apart."""
    out = []
    for line in text.split("\n"):
        if line.strip() and rng.random() < rate:
            chars = list(line)
            for _ in range(rng.randint(1, 2)):
                k = rng.randrange(len(chars))
                chars[k] = LOOKALIKE.get(chars[k], chars[k])
            line = "".join(chars)
        if line.strip() and rng.random() < rate / 2:
            line = rng.choice(["·", "•", "~", "'", ",."]) + line[2:] if line.startswith("  ") else line
        if rng.random() < rate / 3:
            line = re.sub(r"^(\s*)(\d)(\d)", r"\1\2 \3", line)  # "14 7"
        out.append(line)
    return "\n".join(out)


# --- reading it back and scoring --------------------------------------------------

def read_back(pdf: bytes, rng: random.Random, rate: float) -> str:
    from pypdf import PdfReader

    text = "\f".join(p.extract_text(extraction_mode="layout") for p in PdfReader(io.BytesIO(pdf)).pages)
    if rate:
        text = "\f".join(damage(page, rng, rate) for page in text.split("\f"))
    return pdf_text_to_fountain(text)


def _key(heading: str) -> str:
    return re.sub(r"\s+", " ", heading.upper().replace("–", "-")).strip(" .")


def score(script: Script, fountain: str, both_numbers: bool = True) -> dict:
    """What was read right and wrong, compared with what was written."""
    play = parse(fountain)
    # Without INT./EXT. a line is a heading only with its number on both sides ("P3  CUT TO ...  P3").
    truth = [s for s in script.scenes if not s.omitted and (re.match(r"(INT|EXT)", s.heading) or both_numbers)]
    numbered = any(s.number for s in truth) and play.scenes and any(s.scene_number for s in play.scenes)
    problems: list[str] = []
    if numbered:
        read = {s.number: s for s in play.scenes}
        pairs = [(t, read.get(t.number)) for t in truth]
        extra = [s.number for s in play.scenes if s.number not in {t.number for t in truth}]
    else:
        heads_t = [_key(t.heading) for t in truth]
        heads_r = [_key(s.heading) for s in play.scenes]
        match = SequenceMatcher(None, heads_t, heads_r, autojunk=False)
        found = {}
        for block in match.get_matching_blocks():
            for k in range(block.size):
                found[block.a + k] = play.scenes[block.b + k]
        pairs = [(t, found.get(k)) for k, t in enumerate(truth)]
        extra = [f"{s.number}: {s.heading}" for k, s in enumerate(play.scenes) if s not in found.values()]
    missing = [t for t, r in pairs if r is None]
    wrong_heading = [(t, r) for t, r in pairs if r and _key(r.heading) != _key(t.heading)]
    wrong_light = [(t, r) for t, r in pairs if r and t.light and r.day_night != t.light]
    for t in missing:
        problems.append(f"scene lost: {t.number or ''} {t.heading}")
    for t, r in wrong_heading:
        problems.append(f"heading: {t.heading!r} read as {r.heading!r}")
    for t, r in wrong_light:
        problems.append(f"day/night: {t.heading!r} read as {r.day_night}")
    for e in extra:
        problems.append(f"scene made up: {e}")

    said = Counter()
    for s in truth:
        for item in s.body:
            if item[0] == "cue":
                said[item[1]] += 1
                if item[5]:
                    said[item[5]] += 1
    heard = Counter(d.character for s in play.scenes for d in s.dialogues)
    for name in sorted(set(heard) - set(said)):
        problems.append(f"character made up: {name} ({heard[name]})")
    for name in sorted(set(said) - set(heard)):
        problems.append(f"character lost: {name} ({said[name]})")
    cues_right = sum((said & heard).values())
    omitted_t = {s.number for s in script.scenes if s.omitted}
    if numbered and omitted_t != set(play.omitted):
        problems.append(f"omitted: wrote {sorted(omitted_t)}, read {sorted(play.omitted)}")
    return {
        "scenes": len(truth), "found": len(truth) - len(missing), "extra": len(extra),
        "headings_right": len(pairs) - len(missing) - len(wrong_heading),
        "light_right": sum(1 for t, r in pairs if r and t.light and r.day_night == t.light),
        "light_total": sum(1 for t in truth if t.light),
        "cues": sum(said.values()), "cues_right": cues_right,
        "characters_wrong": len(set(heard) ^ set(said)),
        "problems": problems,
    }


def main() -> int:
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--damage", type=float, default=0.04, help="share of lines a scan damages, for the damaged runs")
    ap.add_argument("--show", type=int, default=0, help="print the problems of the worst N runs")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    totals: dict[str, Counter] = {}
    runs = []
    for k in range(args.n):
        script = make_script(rng)
        for layout in LAYOUTS:
            for scanned in (False, True):
                if scanned and layout.name not in ("numbered", "shooting"):
                    continue
                name = layout.name + (" + scan" if scanned else "")
                fountain = read_back(render(script, layout, rng), rng, args.damage if scanned else 0)
                result = score(script, fountain, both_numbers=layout.numbers != "none")
                totals.setdefault(name, Counter()).update({k: v for k, v in result.items() if k != "problems"})
                runs.append((len(result["problems"]), k, name, result["problems"], fountain))

    print(f"{args.n} scripts, seed {args.seed}\n")
    print(f"{'layout':<20}{'scenes':>9}{'headings':>10}{'day/night':>11}{'cues':>8}{'made up':>9}{'names':>7}")
    for name, t in totals.items():
        pct = lambda a, b: f"{100 * t[a] / max(1, t[b]):.1f}%"  # noqa: E731
        print(f"{name:<20}{pct('found', 'scenes'):>9}{pct('headings_right', 'scenes'):>10}"
              f"{pct('light_right', 'light_total'):>11}{pct('cues_right', 'cues'):>8}{t['extra']:>9}{t['characters_wrong']:>7}")
    kinds = Counter(re.sub(r"[:(].*", "", p) for _, _, _, problems, _ in runs for p in problems)
    print("\nMost common problems:", ", ".join(f"{k} ×{v}" for k, v in kinds.most_common()) or "none")
    for count, k, name, problems, fountain in sorted(runs, key=lambda r: r[0], reverse=True)[:args.show]:
        print(f"\n== script {k}, {name}: {count} problems")
        for p in problems[:15]:
            print("  ", p)
            made_up = re.match(r"character made up: (.*) \(", p)
            if made_up:  # where it was read, to see why
                at = fountain.find("\n" + made_up.group(1))
                print("      " + fountain[max(0, at - 160):at + 120].replace("\n", "\n      "))
    return 0


if __name__ == "__main__":
    sys.exit(main())
