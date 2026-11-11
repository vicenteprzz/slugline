"""Exports: CSV tables for spreadsheets and a printable PDF production report."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import TYPE_CHECKING

from slugline.breakdown import Breakdown
from slugline.lint import Issue
from slugline.parser import format_eighths

if TYPE_CHECKING:
    from slugline.llm import Analysis

# Traditional stripboard colours, keyed by (INT/EXT, DAY/NIGHT).
STRIP_COLORS = {
    ("INT", "DAY"): "#ffffff",
    ("EXT", "DAY"): "#fff3b0",
    ("INT", "NIGHT"): "#cfe2f7",
    ("EXT", "NIGHT"): "#cfe8cf",
    ("INT", "DAWN"): "#fbd9e3",
    ("EXT", "DAWN"): "#fbd9e3",
    ("INT", "DUSK"): "#fde0c8",
    ("EXT", "DUSK"): "#fde0c8",
}


def strip_color(int_ext: str | None, day_night: str | None) -> str:
    side = "EXT" if int_ext in ("EXT", "INT/EXT", "EST") else "INT"
    return STRIP_COLORS.get((side, day_night or ""), "#eeeeee")


def _csv(header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def scenes_csv(b: Breakdown, analysis: Analysis | None = None) -> str:
    notes = analysis.by_scene() if analysis else {}
    header = ["scene", "int_ext", "location", "time_of_day", "day_night", "eighths", "length",
              "start_page", "characters", "silent_characters"]
    if analysis:
        header += ["summary", "tone", "valence", "tension"]
    rows = []
    for s in b.scenes:
        row = [s.number, s.int_ext or "", s.location, s.time_of_day or "", s.day_night or "", s.eighths,
               format_eighths(s.eighths), s.start_page, "; ".join(s.characters), "; ".join(s.silent)]
        if analysis:
            n = notes.get(s.number)
            row += [n.summary, n.tone, n.valence, n.tension] if n else ["", "", "", ""]
        rows.append(row)
    return _csv(header, rows)


def characters_csv(b: Breakdown) -> str:
    return _csv(
        ["character", "scenes", "scene_list", "dialogue_blocks", "words", "silent_scenes"],
        [[c.name, len(c.scenes), "; ".join(c.scenes), c.dialogue_blocks, c.words, "; ".join(c.silent_scenes)]
         for c in b.characters],
    )


def locations_csv(b: Breakdown) -> str:
    return _csv(
        ["location", "scenes", "scene_list", "eighths", "length"],
        [[loc.location, len(loc.scenes), "; ".join(loc.scenes), loc.eighths, format_eighths(loc.eighths)]
         for loc in b.locations],
    )


CSV_EXPORTS = {"scenes": scenes_csv, "characters": characters_csv, "locations": locations_csv}


def write_csv(b: Breakdown, directory: str | Path, analysis: Analysis | None = None) -> list[Path]:
    """Write scenes.csv, characters.csv and locations.csv into a directory."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "scenes.csv": scenes_csv(b, analysis),
        "characters.csv": characters_csv(b),
        "locations.csv": locations_csv(b),
    }
    paths = []
    for name, text in files.items():
        path = directory / name
        # utf-8-sig so Excel opens accented names correctly.
        path.write_text(text, encoding="utf-8-sig")
        paths.append(path)
    return paths


def report_pdf(b: Breakdown, issues: list[Issue] | None = None, analysis: Analysis | None = None) -> bytes:
    """A printable production report: stripboard, cast, locations and notes. Needs `reportlab`."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as e:
        raise RuntimeError("PDF export needs reportlab: pip install 'slugline[export]'") from e
    from xml.sax.saxutils import escape

    styles = getSampleStyleSheet()
    cell = ParagraphStyle("cell", parent=styles["BodyText"], fontSize=8, leading=10)
    small = ParagraphStyle("small", parent=cell, textColor=colors.HexColor("#52514e"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    p = lambda text, style=cell: Paragraph(escape(str(text)), style)  # noqa: E731

    grid = colors.HexColor("#c3c2b7")
    base = [
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, grid),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]

    title = b.title or "Untitled"
    story = [
        Paragraph(escape(title), styles["Title"]),
        p(f"Production breakdown · {b.scene_count} scenes · about {b.page_count} pages · "
          f"{len(b.characters)} speaking characters · {len(b.locations)} locations", small),
    ]
    if analysis and analysis.logline:
        story += [Spacer(1, 6), p(analysis.logline)]

    notes = analysis.by_scene() if analysis else {}
    story.append(Paragraph("Stripboard", h2))
    rows = [["#", "I/E", "Location", "Time", "D/N", "Length", "Cast" + (" / summary" if notes else "")]]
    style = list(base)
    for i, s in enumerate(b.scenes, start=1):
        cast = ", ".join(s.characters) + (f" (silent: {', '.join(s.silent)})" if s.silent else "")
        last = [p(cast)]
        if s.number in notes:
            last.append(p(f"{notes[s.number].summary} [{notes[s.number].tone}]", small))
        rows.append([s.number, s.int_ext or "-", p(s.location), p(s.time_of_day or "-"),
                     s.day_night or "-", format_eighths(s.eighths), last])
        style.append(("BACKGROUND", (0, i), (4, i), colors.HexColor(strip_color(s.int_ext, s.day_night))))
    story.append(Table(rows, colWidths=[10 * mm, 14 * mm, 62 * mm, 34 * mm, 15 * mm, 15 * mm, 117 * mm],
                       repeatRows=1, style=TableStyle(style)))

    story.append(Paragraph("Cast", h2))
    rows = [["Character", "Scenes", "Cues", "Words", "Speaks in", "Silent in"]]
    rows += [[p(c.name), len(c.scenes), c.dialogue_blocks, c.words, p(", ".join(c.scenes)),
              p(", ".join(c.silent_scenes) or "-")] for c in b.characters]
    story.append(Table(rows, colWidths=[55 * mm, 16 * mm, 14 * mm, 16 * mm, 100 * mm, 66 * mm],
                       repeatRows=1, style=TableStyle(base)))

    story.append(Paragraph("Locations", h2))
    rows = [["Location", "Scenes", "Length", "Scene numbers"]]
    rows += [[p(loc.location), len(loc.scenes), format_eighths(loc.eighths), p(", ".join(loc.scenes))]
             for loc in b.locations]
    story.append(Table(rows, colWidths=[90 * mm, 16 * mm, 20 * mm, 141 * mm], repeatRows=1, style=TableStyle(base)))

    all_issues = list(issues or []) + (analysis.issues if analysis else [])
    if all_issues:
        story.append(Paragraph("Formatting notes", h2))
        rows = [["Level", "Scene", "Note", "Source"]]
        rows += [[i.severity, i.scene or "-", p(i.message), i.source] for i in all_issues]
        story.append(Table(rows, colWidths=[20 * mm, 14 * mm, 215 * mm, 18 * mm], repeatRows=1, style=TableStyle(base)))

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), title=f"{title} - breakdown", author="Slugline",
                            leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=14 * mm)
    doc.build(story)
    return out.getvalue()
