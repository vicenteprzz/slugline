# Slugline

**Screenplay breakdown and analysis for [Fountain](https://fountain.io) and PDF scripts.**

Breaking a script down for production is slow, manual work: going scene by scene,
listing who is in it, where it happens, whether it's day or night, and how long it
runs. Slugline reads a screenplay and does that breakdown for you.

> Status: early stage. The parser, PDF import and text breakdown work today.
> The dashboard and LLM features are on the roadmap below.

## What it does today

- Parses Fountain screenplays into scenes, dialogue, action and transitions
- **Imports PDF screenplays** by reading the industry layout (indentation tells
  action, dialogue, parentheticals, character cues and transitions apart), and
  joins dialogue split across pages with `(MORE)` / `(CONT'D)`
- Handles the tricky parts of Fountain: forced scene headings (`.FLASHBACK`),
  forced characters (`@McCLANE`) and action (`!KNOCK KNOCK`), extensions like
  `(V.O.)` / `(CONT'D)`, dual dialogue (`^`), title pages, notes `[[ ]]` and boneyard `/* */`
- Splits each scene heading into **INT/EXT**, **location** and **time of day**
- Estimates scene length in **eighths of a page**, the unit used on production boards
- Character stats: scenes each character appears in, dialogue blocks and word count
- Location stats: how many scenes and pages each location needs
- Output as readable tables or JSON

## Quick start

```bash
git clone https://github.com/vicenteprzz/slugline.git
cd slugline
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

slugline examples/johns_boys.fountain
slugline examples/johns_boys.fountain --json
slugline my_script.pdf --fountain my_script.fountain   # PDF in, Fountain out
pytest
```

## Example: *John's Boys*

`examples/johns_boys.fountain` is my own western short (34 pages), converted
from its PDF with Slugline. Breakdown output (trimmed):

```
JOHN'S BOYS — 13 scenes, ~31.9 pages (estimated)

SCENES
  #   INT/EXT  LOCATION                     TIME                 LENGTH  CHARACTERS
  1   INT      BIG JOHN'S OFFICE            NIGHT                5       MAN 1, BIG JOHN, MAN 2, MR. B, MR. D, MR. X, MR. G
  2   EXT      MAIN STREET, OGALLALA        SUNSET               6/8     MR. B, MR. X
  3   EXT      ALLEY, OGALLALA              CONTINUOUS           1 1/8   MR. G, MR. B
  ...

CHARACTERS
  NAME              SCENES  LINES  WORDS
  MR. B             10      59     959
  BIG JOHN          5       37     510
  MR. X             8       32     352
  ...

LOCATIONS
  LOCATION                     SCENES  LENGTH
  BARN                         6       18 4/8
  BIG JOHN'S OFFICE            2       5 5/8
  ...
```

The page estimate (31.9) is within 10% of the real length (34 pages).

## How it works

```
.pdf ──► pdf_import.py ──┐
                         ├──► parser.py ──► Screenplay ──► breakdown.py ──► tables / JSON
.fountain ───────────────┘
```

- `slugline/parser.py` — a line-based parser that follows the Fountain spec rules
  (an element is decided by its own line, the blank line before it and the line after it).
- `slugline/pdf_import.py` — converts PDF text to Fountain using the indentation
  of each line. It works on extracted text, so it's tested without PDFs.
- `slugline/breakdown.py` — aggregates the parsed scenes into character, location
  and scene reports.
- `slugline/cli.py` — command-line entry point.

The core uses only the Python standard library; PDF import needs `pypdf`
(`pip install -e ".[pdf]"`).

## Known limitations

- Page length is an **estimate** based on line wrapping, not real pagination.
- Only speaking characters are counted; characters who appear without dialogue
  are not detected yet.
- `INTERCUT` blocks stay inside the scene where they start.
- PDF import expects standard screenplay layout; dual dialogue in PDFs isn't supported yet.

## Roadmap

1. **Parser and breakdown** — Fountain parser, scene/character/location extraction ✅
2. **Analytics dashboard** — FastAPI backend + React frontend with charts
   (who speaks in each scene, dialogue share across the story, day/night balance)
3. **LLM features** — scene summaries, emotional tone tagging, formatting issue detection
4. **PDF support and exports** — PDF import ✅, export production reports (CSV/PDF)

## Built with an AI coding assistant

This project is developed with an AI coding assistant. I use it to plan, write
boilerplate and tests, and debug — and I review and test everything it produces,
especially the parsing rules, where screenplay formats are full of exceptions.

## License

Code: MIT. The *John's Boys* screenplay in `examples/` is © Vicente Pérez Pourtau,
all rights reserved; it's included only as test data.
