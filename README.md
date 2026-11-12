# Slugline

**Screenplay breakdown and production planning for [Fountain](https://fountain.io), Final Draft and PDF scripts.**

Breaking a script down for production is slow, manual work: going scene by scene,
listing who is in it, where it happens, whether it's day or night, and how long it
runs. Slugline reads a screenplay and does that breakdown for you, as tables in the
terminal, as CSV and PDF reports, or as a web dashboard with an AI assistant that
can answer questions about the script.

## Get it

**Mac:** download `Slugline.dmg`, drag Slugline to Applications and open it.
Your scripts, breakdowns and schedules are saved on your computer; nothing
needs a terminal or an account. The interface is in Spanish and English.

The AI features (story notes, element suggestions, the script assistant) use
your own Anthropic API key, which you add in **Settings**. Everything else
works without it.

Without a licence Slugline runs as a **trial**: everything works, but the
library keeps two scripts and the PDFs are marked as a trial. Paste a licence
key in **Settings** to lift both.

## Selling licences

Licences are signed text keys checked on the buyer's computer: no server, no
accounts, and nobody can make one without the seller's private key.

```bash
slugline license keygen                                   # once: makes ~/.slugline-seller/private_key.pem
slugline license issue "Escuela de Cine" --kind school --days 365
slugline license issue "Ana Gil" --kind pro --days 0       # 0 days: never expires
slugline license check SLUG1-…
```

`keygen` writes the matching public key into `src/slugline/license_public_key.txt`,
which ships in the app. Back up the private key and never commit or share it
(`*.pem` is ignored by git): if it's lost, no new licence can be made for the
builds already out there, and if it leaks anyone can make licences. Kinds are
`pro`, `school`, `studio` and `pilot`. Set `SLUGLINE_PURCHASE_URL` when you
build the app to show a "Buy a licence" link in Settings.

## What it does

**Parsing**

- Parses Fountain screenplays into scenes, dialogue, action and transitions
- Imports Final Draft (`.fdx`) scripts, scene numbers and dual dialogue included
- Imports PDF screenplays by reading the industry layout (indentation tells
  action, dialogue, parentheticals, character cues and transitions apart),
  measured on each script and each page, so wide margins and scanned pages
  work too. It joins dialogue split across pages with `(MORE)` / `(CONT'D)`,
  reads scene numbers beside headings, and drops revision headers and
  `CONTINUED` lines
- In shooting scripts, shot descriptions (`MOVING POV`, `ANGLE ON`...) are kept
  out of the location, and a numbered shot with no INT./EXT. (`INSIDE`) stays
  in the location of the scene before, so the schedule groups them
- Handles the tricky parts of Fountain: forced scene headings (`.FLASHBACK`),
  forced characters (`@McCLANE`) and action (`!KNOCK KNOCK`), extensions like
  `(V.O.)` / `(CONT'D)`, dual dialogue (`^`), centered text, emphasis markers,
  title pages, notes `[[ ]]` and boneyard `/* */`

**Breakdown**

- Splits each scene heading into INT/EXT, location and time of day, and groups
  times into the four lighting conditions a schedule cares about (day, night,
  dawn, dusk). `LATER` and `CONTINUOUS` take the condition of the scene before
- Estimates scene length in eighths of a page, the unit used on production boards
- Character stats: scenes, dialogue cues and words, plus the scenes where the
  action names a character who has no lines there
- Location stats: how many scenes and pages each location needs
- Formatting checks: headings without INT/EXT or time of day, empty scenes,
  character or location names written two ways (`SHERIF` / `SHERIFF`), scene
  numbering gaps. In the app, one click merges the two spellings or sets day or
  night for a heading that doesn't say; the cast, locations and schedule count
  it that way without touching the script file

**Element breakdown**

- What each department has to provide for every scene: extras, stunts, props,
  wardrobe, makeup and hair, vehicles, animals, special and visual effects,
  sound, set dressing and special equipment
- Claude suggests the elements for the whole script in one pass; you check,
  edit, add or remove them on each scene's breakdown sheet. Suggesting again
  never overwrites what you edited, and doesn't bring back what you removed
- Works without AI too: when a script is opened, a production dictionary in
  English and Spanish (and the capitalised sound cues screenplays use) gives a
  first pass for every scene, marked as suggested; add or fix the rest by hand
- Each element is tracked across the shoot: which scenes need it and for how many pages

**Revised drafts**

- Open a new draft and your breakdown and schedule come with it. Scenes are
  matched between drafts even when they were renumbered, moved or rewritten
- Rewritten scenes are flagged to check, new scenes to break down, and cut
  scenes are listed with the elements that went with them

**Shooting schedule**

- Slugline suggests a first plan the way an assistant director starts one:
  day work first and the nights in one block, each location kept together, no
  company move halfway through a day, and each day filled up to the pages you
  expect to shoot
- Drag the strips between days (or use the menu on each strip), add dates and
  notes, and see each day's pages, locations and lighting at a glance
- Export it as a PDF stripboard or CSV

**Call sheets and day out of days**

- A call sheet for every shooting day: date, crew call, meeting point, notes,
  the day's scenes, the cast with each actor's status, who is on hold, what
  each department needs that day, and an advance look at the next day
- Day out of days: which days each character works (SW, W, WF, SWF) and the
  holds between them, which is what drives cast costs. Moving scenes to cut
  holds shows up at once
- Add the actors' names once; they appear on every call sheet

**Budget**

- A first budget worked out from the breakdown and the schedule, in the twelve
  chapters of the ICAA budget model used for Spanish film funding
- The quantities come from the script and the schedule, so they are exact and
  move with it: shooting days and preparation for each crew member, the days
  each actor works (a short gap between work days is paid as hold, a long one
  is a drop and pick-up), days with extras or stunts, days at each location,
  each picture vehicle and animal, meals for the crew and cast
- The rates are yours: four levels (short film, low-budget, mid-budget and
  high-budget feature) to start from, and every rate and quantity can be
  changed or a line added by hand. The high-budget level budgets a studio
  picture: a slower pace (2 pages a day), the crew at full size, a second
  unit, stage builds and visual effects across the film to be quoted
- What can't be priced from a script (an explosion, a visual effect) is
  marked *to be quoted*, with the scenes that need it, until you enter the quote
- Social security on cast and crew wages (about a third in Spain), overtime,
  insurance, overheads and a contingency reserve, each a percentage you can
  change; the contingency is kept apart from the ICAA chapters
- What each scene costs to shoot, so you know what cutting it would save, and
  what a rewrite costs: a new draft compares its total and days with the last one
- Export it as PDF or CSV for a spreadsheet. It is a first draft for a
  production manager to check, not a budget to submit as it is

**Exports**

- CSV tables (scenes, characters, locations, elements) that open cleanly in Excel or Sheets
- A printable PDF production report with a colour-coded stripboard and the element list
- Breakdown sheets: one printable page per scene with every department's box,
  the format department heads work from

**Dashboard** (`slugline serve`)

- Stripboard, who speaks in each scene, dialogue share, a character-by-scene
  presence map, day/night and interior/exterior balance, locations
- An editable breakdown sheet for every scene and an element list you can
  filter by department
- A shooting schedule board with drag and drop
- Every chart has a table view, and the page follows the system light or dark theme

**AI features** (optional, need an Anthropic API key)

- A summary, emotional tone, tension and mood score for every scene, plus a
  logline, synopsis and themes for the whole script
- A proofread that looks for formatting problems rules can't catch, such as a
  line of dialogue formatted as action
- A script assistant you can ask in plain language ("which scenes could shoot on
  the same day?"). It answers with tools that read the parsed script, so the
  counts and page lengths it gives are the same exact numbers as the breakdown,
  not the model's estimate

## Quick start (from the source code)

```bash
git clone https://github.com/vicenteprzz/slugline.git
cd slugline
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

slugline examples/johns_boys.fountain                 # breakdown tables
slugline my_script.pdf --fountain my_script.fountain  # PDF in, Fountain out
slugline lint examples/johns_boys.fountain            # formatting checks
slugline export examples/johns_boys.fountain --csv out/ --pdf out/report.pdf --sheets out/sheets.pdf
slugline schedule examples/johns_boys.fountain --pages 5 --pdf out/schedule.pdf --call-sheets out/calls.pdf
slugline my_script.fdx                                # Final Draft works everywhere a script does
pytest
```

The dashboard is a React app that is built once into the Python package:

```bash
cd web && npm install && npm run build && cd ..
slugline serve examples/johns_boys.fountain           # http://127.0.0.1:8000
```

You can also start `slugline serve` with no script and drop a file on the page.
Every script you open is kept in your library (in `~/.local/share/slugline`,
or `SLUGLINE_DATA`) with everything you did on it.

### The desktop app

```bash
pip install -e ".[desktop]"
slugline-app                        # the dashboard in its own window
```

To build the Mac app and its disk image (`dist/Slugline.app`, `dist/Slugline.dmg`):

```bash
pip install -e ".[package]"
packaging/macos/build.sh
```

The build is not signed. On your own Mac it opens normally; to give it to
other people without a security warning it needs an Apple Developer ID
signature and notarization.

### AI features

```bash
export ANTHROPIC_API_KEY=sk-ant-...

slugline analyze examples/johns_boys.fountain          # summaries, tone, proofread
slugline elements examples/johns_boys.fountain         # props, wardrobe, vehicles... per scene
slugline ask examples/johns_boys.fountain "Who is in the barn scenes?"
slugline chat examples/johns_boys.fountain             # a conversation
slugline export examples/johns_boys.fountain --pdf report.pdf --ai
```

Or add the key in the dashboard's **Settings** panel: it is saved only on
this computer, readable only by you, and never sent back to the page. With a
key, the dashboard shows **Analyze the script**, **Suggest elements with AI**
and an **Ask the script** panel. The model is `claude-opus-5-5`; set `SLUGLINE_MODEL`
to use another one. An analysis is cached in `~/.cache/slugline` by script
content and model, so asking twice for the same script makes no new request.
Element breakdowns and schedules, with your edits, are saved in
`~/.local/share/slugline` (or `SLUGLINE_DATA`), so the CLI and the dashboard
share them.
Using these features sends the script to the Anthropic API.

## Example: *John's Boys*

`examples/johns_boys.fountain` is my own western short (34 pages), converted
from its PDF with Slugline. Breakdown output (trimmed):

```
JOHN'S BOYS — 13 scenes, ~31.9 pages (estimated)

SCENES
  #   INT/EXT  LOCATION                     TIME                 LENGTH  CHARACTERS
  1   INT      BIG JOHN'S OFFICE            NIGHT                5       MAN 1, BIG JOHN, MAN 2, MR. B, MR. D, MR. X, MR. G
  2   EXT      MAIN STREET, OGALLALA        SUNSET               6/8     MR. B, MR. X (silent: MR. D, MR. G)
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

INT/EXT: INT 9, EXT 4
DAY/NIGHT: NIGHT 7, DUSK 4, DAWN 1, DAY 1
```

The page estimate (31.9) is within 10% of the real length (34 pages).

## How it works

```
.pdf ──► pdf_import.py ──┐
.fdx ──► fdx_import.py ──┤
                         ├──► parser.py ──► Screenplay ──┬──► breakdown.py ──► tables / JSON
.fountain ───────────────┘                               ├──► lint.py ──────► formatting checks
                                                         ├──► elements.py ──► element breakdown (AI + hand edits)
                                                         ├──► schedule.py ──► shooting schedule
                                                         ├──► revisions.py ─► carry work over to new drafts
                                                         ├──► export.py ────► CSV / PDF
                                                         ├──► llm.py ───────► summaries, tone, proofread
                                                         ├──► agent.py ─────► script assistant
                                                         └──► server.py ────► API for the dashboard (web/)
```

- `parser.py` is a line-based parser that follows the Fountain spec rules
  (an element is decided by its own line, the blank line before it and the line after it).
- `pdf_import.py` converts PDF text to Fountain using the indentation
  of each line. It works on extracted text, so it's tested without PDFs.
- `breakdown.py` aggregates the parsed scenes into scene, character and location reports.
- `llm.py` asks Claude for structured JSON (a schema per request), with the
  script sent as a cached block so that the later requests about it cost less.
- `elements.py` holds the element breakdown: suggestions from Claude and hand
  edits live in one sheet, and a new extraction merges into it instead of replacing it.
- `schedule.py` suggests and stores the shooting schedule.
- `revisions.py` fingerprints every scene (heading and words) when work is
  saved, and matches the scenes of a new draft against the latest saved draft
  of the same script.
- `agent.py` is a tool-use loop: Claude decides which of nine read-only tools
  to call (list scenes, read scenes, a character's dialogue, search...) and the
  answers come back from the parsed script.
- `server.py` is a small FastAPI app; the chat endpoint streams the answer as
  it is written. It only answers on this computer's own addresses, and only
  accepts changes that carry the app's header, so another website open in the
  browser can't use it (or the API key in it). `web/` is the React dashboard,
  with charts drawn in plain SVG and the interface in Spanish and English.
- `library.py` keeps every opened script; `settings.py` the API key, model
  and language; `desktop.py` runs it all in a native window.

The core (parser, breakdown, lint, CSV) uses only the Python standard library.
Everything else is an optional extra:

| Extra | Adds | Needs |
|---|---|---|
| `slugline[pdf]` | PDF import | `pypdf` |
| `slugline[export]` | PDF report | `reportlab` |
| `slugline[web]` | Dashboard | `fastapi`, `uvicorn` |
| `slugline[llm]` | AI features | `anthropic` |
| `slugline[all]` | All of the above | |

### Tests

`pytest` runs the whole suite without a network or an API key. The LLM tests use
the real Anthropic SDK with its HTTP layer replaced by canned responses
(`tests/fake_api.py`), so they check the requests Slugline sends and how it
handles answers, refusals and API errors.

To work on the dashboard, run `slugline serve` in one terminal and
`npm run dev` inside `web/` in another; the dev server proxies `/api` to port 8000.

## Known limitations

- Page length is an **estimate** based on line wrapping, not real pagination.
- A character who never speaks anywhere in the script is not detected. Silent
  appearances are found by name, so a character called WILL would also match
  the capitalised word "Will" at the start of a sentence.
- `INTERCUT` blocks stay inside the scene where they start.
- PDF import reads the layout, not the meaning: dual dialogue and badly scanned pages can come out mixed up. Check the formatting notes after importing.
- Drafts are recognised as the same script by their title page (or, without
  one, by their scene headings). Matching scenes is a judgement from the text:
  check the scenes it flags, and a scene moved to a new location with new
  action is treated as a new scene.
- Call sheets use one crew call for the whole cast; individual call times,
  pick-ups and crew lists are not there yet.
- The schedule suggestion knows pages, locations and day/night, but not cast
  availability, travel time or turnaround rules yet.
- Tone, tension and mood are a model's reading of the script. They are useful
  for seeing the shape of the story, not a measurement.

## Roadmap

1. **Parser and breakdown** — Fountain parser, scene/character/location extraction ✅
2. **Analytics dashboard** — FastAPI backend + React frontend with charts ✅
3. **LLM features** — scene summaries, tone tagging, formatting proofread, script assistant ✅
4. **PDF support and exports** — PDF import, CSV and PDF production reports ✅
5. **Element breakdown** — elements per department and scene, editable, breakdown sheets ✅
6. **Revised drafts and shooting schedule** — carry work across drafts, schedule board ✅
7. **Call sheets, day out of days, Final Draft import** ✅
8. **Desktop app** — Mac app, script library, API key in Settings, Spanish interface and PDFs ✅
9. **Next** — signed and notarized Mac build, Windows build; individual cast
   call times and crew lists; shared projects for a whole crew

## Built with an AI coding assistant

This project is developed with an AI coding assistant. I use it to plan, write
boilerplate and tests, and debug — and I review and test everything it produces,
especially the parsing rules, where screenplay formats are full of exceptions.

## License

Code: MIT. The *John's Boys* screenplay in `examples/` is © Vicente Pérez Pourtau,
all rights reserved; it's included only as test data.
