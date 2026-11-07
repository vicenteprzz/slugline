# Slugline

**Screenplay breakdown and analysis for [Fountain](https://fountain.io) scripts.**

Breaking a script down for production is slow, manual work: going scene by scene,
listing who is in it, where it happens, whether it's day or night, and how long it
runs. Slugline reads a screenplay and does that breakdown for you.

> Status: early stage. The Fountain parser and the text breakdown work today.
> The dashboard, LLM features and PDF import are on the roadmap below.

## What it does today

- Parses Fountain screenplays into scenes, dialogue, action and transitions
- Handles the tricky parts of the format: forced scene headings (`.FLASHBACK`),
  forced characters (`@McCLANE`), extensions like `(V.O.)` / `(CONT'D)`,
  dual dialogue (`^`), parentheticals, title pages, notes `[[ ]]` and boneyard `/* */`
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

slugline examples/dust_and_iron.fountain
slugline examples/dust_and_iron.fountain --json
pytest
```

Example output (trimmed):

```
DUST AND IRON — 6 scenes, ~1.3 pages (estimated)

SCENES
  #   INT/EXT  LOCATION                    TIME        LENGTH  CHARACTERS
  1   EXT      DESERT ROAD                 DAWN        2/8     ELI, RUTH
  2   EXT      SILVER CREEK - MAIN STREET  DAY         3/8     ELI, RUTH
  3   INT      SALOON                      CONTINUOUS  2/8     SHERIFF, RUTH
  ...

CHARACTERS
  NAME         SCENES  LINES  WORDS
  RUTH         3       4      16
  ELI          2       3      14
  ...
```

## Known limitations

- Page length is an **estimate** based on line wrapping, not real pagination.
- Only speaking characters are counted; characters who appear without dialogue
  are not detected yet.
- Forced headings without INT/EXT (e.g. `.FLASHBACK - THE RANCH FIRE`) are split
  on the last dash like any other heading.

## How it works

```
.fountain file ──► parser.py ──► Screenplay (scenes, elements) ──► breakdown.py ──► tables / JSON
```

- `slugline/parser.py` — a line-based parser that follows the Fountain spec rules
  (an element is decided by its own line, the blank line before it and the line after it).
- `slugline/breakdown.py` — aggregates the parsed scenes into character, location
  and scene reports.
- `slugline/cli.py` — command-line entry point.

No dependencies outside the Python standard library for the core.

## Roadmap

1. **Parser and breakdown** — Fountain parser, scene/character/location extraction ✅ *(in progress: more edge cases)*
2. **Analytics dashboard** — FastAPI backend + React frontend with charts
   (who speaks in each scene, dialogue share across the story, day/night balance)
3. **LLM features** — scene summaries, emotional tone tagging, formatting issue detection
4. **PDF support and exports** — import PDF screenplays, export production reports (CSV/PDF)

## Built with an AI coding assistant

This project is developed with an AI coding assistant. I use it to plan, write
boilerplate and tests, and debug — and I review and test everything it produces,
especially the parsing rules, where the Fountain format is full of exceptions.

## License

MIT
