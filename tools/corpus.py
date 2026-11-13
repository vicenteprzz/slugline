"""Read a folder of scripts and say how well each one was read.

    python tools/corpus.py ~/Desktop/GUION                 # the report, worst first
    python tools/corpus.py ~/Desktop/GUION --save          # keep this as the baseline
    python tools/corpus.py ~/Desktop/GUION --compare       # what changed since the baseline
    python tools/corpus.py ~/Desktop/GUION --only batman   # one script, every example

Nothing in the folder is changed or copied into the repository: the scripts
stay where they are, a PDF's text is cached in ~/.cache/slugline-corpus so the
next run is quick, and the baseline is kept there too.

Every check is something a well-read script doesn't have: a scene number the
numbering skips, a heading left in the action, a heading with scan specks, a
"character" that is a scrap of dialogue, scenes without day or night. None
needs to know the right answer, so any script can be added to the folder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path

from slugline.lint import lint
from slugline.parser import SCENE_PREFIX, Action, parse
from slugline.pdf_import import pdf_text_to_fountain

CACHE = Path.home() / ".cache" / "slugline-corpus"
BASELINE = CACHE / "baseline.json"
SUFFIXES = {".pdf", ".fdx", ".fountain", ".spmd", ".txt"}

# How much each kind of problem weighs in the score.
WEIGHTS = {
    "unread": 100,  # the file read as next to nothing (a scan with no text, a broken PDF)
    "missing": 3,  # a scene number the numbering skips and the file doesn't show
    "heading_in_action": 3,  # "INT. KITCHEN - DAY" read as action
    "odd_name": 2,  # a character that is a scrap of dialogue or a smudge
    "bad_heading": 2,  # specks or lowercase in a heading
    "time_missed": 3,  # "STUDY NIGHT": the time is there but wasn't read
    "empty": 1,  # a scene with nothing in it
    "no_time": 0,  # no day or night in the heading: the script's choice, shown only
}
TIME_WORDS = re.compile(r"\b(DAY|NIGHT|MORNING|EVENING|DAWN|DUSK|AFTERNOON|SUNSET|SUNRISE|DÍA|NOCHE|AMANECER|ATARDECER|TARDE|MAÑANA)\b\W*$")
NAME_OK = re.compile(r"^[\"“A-ZÁÉÍÓÚÜÑÀÈÌÒÙÇ0-9][A-ZÁÉÍÓÚÜÑÀÈÌÒÙÇ0-9 .'’#&/()\"“”\-]*$")
HEADING_OK = re.compile(r"^[A-ZÁÉÍÓÚÜÑÀÈÌÒÙÇ0-9 .,'’/&()#:;!?\"“”\-–—]+$")


def layout_text(path: Path) -> str:
    """The PDF's text as pypdf lays it out, cached by the file's content."""
    digest = hashlib.sha1(path.read_bytes()).hexdigest()[:16]
    cached = CACHE / "text" / f"{digest}.txt"
    if cached.exists():
        return cached.read_text()
    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)

    text = "\f".join(p.extract_text(extraction_mode="layout") for p in PdfReader(str(path)).pages)
    from slugline import ocr
    from slugline.pdf_import import is_scanned

    if is_scanned(text):
        if not ocr.available():
            return text  # not cached: read again once OCR is installed
        text = ocr.pdf_text(path, lambda done, total: print(f"  OCR {path.name}: {done}/{total}", end="\r", file=sys.stderr))
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(text)
    return text


def fountain(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return pdf_text_to_fountain(layout_text(path))
    if suffix == ".fdx":
        from slugline.fdx_import import fdx_to_fountain

        return fdx_to_fountain(path)
    return path.read_text(encoding="utf-8-sig")


def check(path: Path) -> dict:
    """What was read from one script, and every problem found in it."""
    play = parse(fountain(path))
    cues = Counter(d.character for s in play.scenes for d in s.dialogues)
    found: dict[str, list[str]] = {k: [] for k in WEIGHTS}

    for issue in lint(play):
        if issue.code.startswith("read-"):
            found["unread"].append(issue.message)
        if issue.code == "missing-scenes":
            found["missing"] += [n.strip() for n in issue.params["missing"].split(",")]
    for s in play.scenes:
        heading = s.heading.strip()
        if not HEADING_OK.match(heading) or len(heading) > 90:
            found["bad_heading"].append(f"{s.number}: {heading[:80]}")
        if s.time_of_day is None and not s.continues and SCENE_PREFIX.match(heading):
            kind = "time_missed" if TIME_WORDS.search(heading.upper()) else "no_time"
            found[kind].append(f"{s.number}: {heading[:60]}")
        if not s.elements:
            found["empty"].append(f"{s.number}: {heading[:60]}")
        for e in s.elements:
            if isinstance(e, Action):
                first = e.text.strip().split("\n")[0]
                if SCENE_PREFIX.match(first) and first.upper() == first and len(first) < 90:
                    found["heading_in_action"].append(f"in {s.number}: {first[:70]}")
    for name, n in cues.items():
        words = name.split()
        if (not NAME_OK.match(name) or "--" in name or "..." in name or len(words) > 5
                or sum(len(w) == 1 for w in words) >= 2):
            found["odd_name"].append(f"{name} ({n})")

    if not play.scenes:
        found["unread"].append("no scenes at all")
    score = sum(WEIGHTS[k] * len(v) for k, v in found.items())
    return {
        "scenes": len(play.scenes),
        "characters": sorted(cues),
        "cues": sum(cues.values()),
        "omitted": len(play.omitted),
        "found": found,
        "score": score,
    }


def scripts(folder: Path, only: str | None) -> list[Path]:
    files = sorted(p for p in folder.rglob("*") if p.suffix.lower() in SUFFIXES and p.is_file())
    return [p for p in files if not only or only.lower() in p.name.lower()]


def report(results: dict[str, dict], examples: int) -> None:
    width = max(len(n) for n in results) if results else 10
    heads = "".join(f"{k[:8]:>9}" for k in WEIGHTS)
    print(f"{'script':<{width}}  score scenes  cues{heads}")
    for name, r in sorted(results.items(), key=lambda kv: -kv[1]["score"]):
        counts = "".join(f"{len(r['found'][k]):>9}" for k in WEIGHTS)
        print(f"{name:<{width}}  {r['score']:>5} {r['scenes']:>6} {r['cues']:>5}{counts}")
    for name, r in sorted(results.items(), key=lambda kv: -kv[1]["score"]):
        if not r["score"]:
            continue
        print(f"\n== {name}")
        for kind, items in r["found"].items():
            if items:
                shown = "; ".join(items[:examples]) + (f" … (+{len(items) - examples})" if len(items) > examples else "")
                print(f"  {kind}: {shown}")


def compare(results: dict[str, dict], baseline: dict[str, dict]) -> bool:
    """What got worse since the baseline. True when nothing did."""
    worse = False
    for name, r in sorted(results.items()):
        before = baseline.get(name)
        if not before:
            print(f"+ {name}: new, score {r['score']}")
            continue
        notes = []
        if r["scenes"] != before["scenes"]:
            notes.append(f"scenes {before['scenes']} -> {r['scenes']}")
        lost = sorted(set(before["characters"]) - set(r["characters"]))
        gained = sorted(set(r["characters"]) - set(before["characters"]))
        if lost:
            notes.append(f"characters gone: {', '.join(lost[:8])}")
        if gained:
            notes.append(f"characters new: {', '.join(gained[:8])}")
        if r["cues"] != before["cues"]:
            notes.append(f"cues {before['cues']} -> {r['cues']}")
        for kind in WEIGHTS:
            a, b = len(before["found"].get(kind, [])), len(r["found"][kind])
            if a != b:
                notes.append(f"{kind} {a} -> {b}")
        # Worse: a higher score, or scenes or characters lost that the score can't see.
        bad = r["score"] > before["score"] or r["scenes"] < before["scenes"] and not r["score"] < before["score"] or bool(lost)
        worse |= bad
        if notes:
            mark = "!" if bad else "~"
            print(f"{mark} {name}: score {before['score']} -> {r['score']}; " + "; ".join(notes))
    print("\nNothing got worse." if not worse else "\nSomething got worse: look at the lines marked !")
    return not worse


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--save", action="store_true", help="keep this run as the baseline")
    ap.add_argument("--compare", action="store_true", help="compare with the baseline")
    ap.add_argument("--only", help="only the scripts whose file name contains this")
    ap.add_argument("--examples", type=int, default=4)
    args = ap.parse_args()

    results = {}
    for path in scripts(args.folder.expanduser(), args.only):
        try:
            results[path.stem] = check(path)
        except Exception as e:  # a script that can't be read at all is the worst result
            print(f"! {path.name}: {type(e).__name__}: {e}", file=sys.stderr)
    if args.compare:
        baseline = json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
        ok = compare(results, baseline)
    else:
        report(results, 99 if args.only else args.examples)
        ok = True
    if args.save:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(results, ensure_ascii=False, indent=1))
        print(f"\nBaseline saved: {len(results)} scripts.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
