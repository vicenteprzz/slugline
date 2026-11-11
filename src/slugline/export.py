"""Exports: CSV tables for spreadsheets and a printable PDF production report."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import TYPE_CHECKING

from slugline.breakdown import Breakdown
from slugline.elements import COLORS, LABELS, ElementSheet, totals
from slugline.schedule import Schedule, day_stats
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


def elements_csv(b: Breakdown, sheet: ElementSheet) -> str:
    """One row per element per scene: easy to filter by department in a spreadsheet."""
    rows = []
    for s in b.scenes:
        for e in sheet.for_scene(s.number):
            rows.append([s.number, s.heading, LABELS[e.category], e.name, e.notes,
                         "suggested" if e.source == "ai" else "manual"])
    return _csv(["scene", "heading", "department", "element", "notes", "source"], rows)


CSV_EXPORTS = {"scenes": scenes_csv, "characters": characters_csv, "locations": locations_csv}


def write_csv(
    b: Breakdown,
    directory: str | Path,
    analysis: Analysis | None = None,
    elements: ElementSheet | None = None,
) -> list[Path]:
    """Write scenes.csv, characters.csv, locations.csv and, if there is a
    breakdown of elements, elements.csv into a directory."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "scenes.csv": scenes_csv(b, analysis),
        "characters.csv": characters_csv(b),
        "locations.csv": locations_csv(b),
    }
    if elements and not elements.is_empty():
        files["elements.csv"] = elements_csv(b, elements)
    paths = []
    for name, text in files.items():
        path = directory / name
        # utf-8-sig so Excel opens accented names correctly.
        path.write_text(text, encoding="utf-8-sig")
        paths.append(path)
    return paths


def _reportlab():
    try:
        import reportlab  # noqa: F401
    except ImportError as e:
        raise RuntimeError("PDF export needs reportlab: pip install 'slugline[export]'") from e


def report_pdf(
    b: Breakdown,
    issues: list[Issue] | None = None,
    analysis: Analysis | None = None,
    elements: ElementSheet | None = None,
) -> bytes:
    """A printable production report: stripboard, cast, locations, elements and
    notes. Needs `reportlab`."""
    _reportlab()
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
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

    if elements and not elements.is_empty():
        story.append(Paragraph("Elements", h2))
        rows = [["Department", "Element", "Scenes", "Length", "Scene numbers"]]
        rows += [[LABELS[t.category], p(t.name), len(t.scenes), format_eighths(t.eighths), p(", ".join(t.scenes))]
                 for t in totals(elements, b)]
        story.append(Table(rows, colWidths=[35 * mm, 85 * mm, 16 * mm, 20 * mm, 111 * mm], repeatRows=1,
                           style=TableStyle(base)))

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


def breakdown_sheets_pdf(
    b: Breakdown,
    elements: ElementSheet | None = None,
    analysis: Analysis | None = None,
) -> bytes:
    """One breakdown sheet per scene, the page each department head works from.
    Empty boxes are left open for notes by hand. Needs `reportlab`."""
    _reportlab()
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9, leading=11.5)
    muted = ParagraphStyle("muted", parent=body, textColor=colors.HexColor("#52514e"))
    label = ParagraphStyle("label", parent=body, fontName="Helvetica-Bold", fontSize=7.5, leading=10,
                           textColor=colors.HexColor("#52514e"))
    number = ParagraphStyle("number", parent=body, fontName="Helvetica-Bold", fontSize=22, leading=24, alignment=1)
    slug = ParagraphStyle("slug", parent=body, fontName="Courier-Bold", fontSize=12, leading=15)
    meta_value = ParagraphStyle("meta", parent=body, fontName="Helvetica-Bold", fontSize=9.5)
    grid = colors.HexColor("#c3c2b7")
    width = A4[0] - 28 * mm
    notes = analysis.by_scene() if analysis else {}
    title = b.title or "Untitled"

    def box(heading: str, color: str | None, lines: list) -> list:
        return [Paragraph(escape(heading.upper()), label), *lines, Spacer(1, 12 * mm if not lines else 4 * mm)]

    story = []
    for i, s in enumerate(b.scenes):
        if i:
            story.append(PageBreak())
        story.append(Table(
            [[Paragraph(escape(s.number), number), Paragraph(escape(s.heading), slug)]],
            colWidths=[24 * mm, width - 24 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(strip_color(s.int_ext, s.day_night))),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                ("LINEAFTER", (0, 0), (0, 0), 0.8, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]),
        ))
        meta = [("Int./Ext.", s.int_ext or "-"), ("Day/Night", s.day_night or "-"), ("Time", s.time_of_day or "-"),
                ("Length", f"{format_eighths(s.eighths)} pages"), ("Starts on page", str(int(s.start_page)))]
        story.append(Table(
            [[Paragraph(k.upper(), label) for k, _ in meta], [Paragraph(escape(v), meta_value) for _, v in meta]],
            colWidths=[width / len(meta)] * len(meta),
            style=TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.5, grid),
                ("LINEAFTER", (0, 0), (-2, -1), 0.5, grid),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
            ]),
        ))
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("SYNOPSIS", label))
        if s.number in notes:
            story.append(Paragraph(escape(notes[s.number].summary), body))
        else:
            story.append(Spacer(1, 10 * mm))
        story.append(Spacer(1, 4 * mm))

        cast = [Paragraph(escape(", ".join(s.characters) or "-"), body)]
        if s.silent:
            cast.append(Paragraph(escape("No lines: " + ", ".join(s.silent)), muted))
        items = elements.for_scene(s.number) if elements else []
        cells = [box("Cast", None, cast)]
        cell_colors: list[str | None] = [None]
        for key, heading, color in [(k, LABELS[k], COLORS[k]) for k in LABELS]:
            lines = [
                Paragraph(f"• {escape(e.name)}" + (f" <font color='#52514e'>({escape(e.notes)})</font>" if e.notes else ""), body)
                for e in items if e.category == key
            ]
            cells.append(box(heading, color, lines))
            cell_colors.append(color)
        cells.append(box("Production notes", None, []))
        cell_colors.append(None)

        rows = [cells[j:j + 2] for j in range(0, len(cells), 2)]
        style = [
            ("GRID", (0, 0), (-1, -1), 0.5, grid),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]
        for j, color in enumerate(cell_colors):
            if color:
                style.append(("LINEABOVE", (j % 2, j // 2), (j % 2, j // 2), 3, colors.HexColor(color)))
        story.append(Table(rows, colWidths=[width / 2] * 2, style=TableStyle(style)))

    def footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#898781"))
        canvas.drawString(14 * mm, 9 * mm, f"{title} · Breakdown sheets")
        canvas.drawRightString(A4[0] - 14 * mm, 9 * mm, f"Slugline · page {doc.page}")
        canvas.restoreState()

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, title=f"{title} - breakdown sheets", author="Slugline",
                            leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=16 * mm)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()


def _date_label(iso: str) -> str:
    from datetime import date

    try:
        return date.fromisoformat(iso).strftime("%a %d %b %Y")
    except ValueError:
        return iso


def schedule_csv(b: Breakdown, schedule: Schedule) -> str:
    rows_by_number = {s.number: s for s in b.scenes}
    rows = []
    for i, day in enumerate(schedule.days, start=1):
        for order, n in enumerate(day.scenes, start=1):
            s = rows_by_number[n]
            rows.append([i, day.date, order, s.number, s.int_ext or "", s.location, s.day_night or "",
                         s.eighths, format_eighths(s.eighths), "; ".join(s.characters)])
    scheduled = schedule.scheduled()
    for s in b.scenes:
        if s.number not in scheduled:
            rows.append(["", "", "", s.number, s.int_ext or "", s.location, s.day_night or "",
                         s.eighths, format_eighths(s.eighths), "; ".join(s.characters)])
    return _csv(["day", "date", "order", "scene", "int_ext", "location", "day_night", "eighths", "length", "cast"], rows)


def schedule_pdf(b: Breakdown, schedule: Schedule, elements: ElementSheet | None = None) -> bytes:
    """The shooting schedule as a stripboard, day by day. Needs `reportlab`."""
    _reportlab()
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

    styles = getSampleStyleSheet()
    cell = ParagraphStyle("cell", parent=styles["BodyText"], fontSize=8, leading=10)
    small = ParagraphStyle("small", parent=cell, textColor=colors.HexColor("#52514e"))
    slug = ParagraphStyle("slug", parent=cell, fontName="Courier-Bold", fontSize=8.5)
    day_style = ParagraphStyle("day", parent=cell, fontName="Helvetica-Bold", fontSize=9, textColor=colors.white)
    p = lambda text, style=cell: Paragraph(escape(str(text)), style)  # noqa: E731
    rows_by_number = {s.number: s for s in b.scenes}
    title = b.title or "Untitled"
    total = sum(s.eighths for s in b.scenes)

    widths = [12 * mm, 12 * mm, 88 * mm, 15 * mm, 16 * mm, 70 * mm, 54 * mm]
    rows: list[list] = [["#", "I/E", "Set", "D/N", "Pages", "Cast", "Elements"]]
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#c3c2b7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]

    def strip(s) -> list:
        items = elements.for_scene(s.number) if elements else []
        return [s.number, s.int_ext or "-", p(s.heading, slug), s.day_night or "-", format_eighths(s.eighths),
                p(", ".join(s.characters) or "-"), p(", ".join(e.name for e in items) or "-", small)]

    def add_strips(numbers: list[str]) -> None:
        for n in numbers:
            s = rows_by_number[n]
            rows.append(strip(s))
            style.append(("BACKGROUND", (0, len(rows) - 1), (4, len(rows) - 1),
                          colors.HexColor(strip_color(s.int_ext, s.day_night))))

    def banner(text: str, color: str) -> None:
        rows.append([p(text, day_style)] + [""] * 6)
        r = len(rows) - 1
        style.extend([("SPAN", (0, r), (-1, r)), ("BACKGROUND", (0, r), (-1, r), colors.HexColor(color))])

    for i, day in enumerate(schedule.days, start=1):
        stats = day_stats(day, b, schedule.pages_per_day)
        parts = [f"DAY {i} OF {len(schedule.days)}"]
        if day.date:
            parts.append(_date_label(day.date))
        parts.append(f"{format_eighths(stats.eighths)} pages")
        if stats.over:
            parts.append(f"over the {schedule.pages_per_day:g}-page day")
        if day.notes:
            parts.append(day.notes)
        banner(" · ".join(parts), "#0b0b0b")
        add_strips(day.scenes)
    unscheduled = [s.number for s in b.scenes if s.number not in schedule.scheduled()]
    if unscheduled:
        banner(f"NOT SCHEDULED · {len(unscheduled)} scenes", "#898781")
        add_strips(unscheduled)

    story = [
        Paragraph(escape(title), styles["Title"]),
        p(f"Shooting schedule · {len(schedule.days)} days · {format_eighths(total)} pages · "
          f"planned at {schedule.pages_per_day:g} pages a day", small),
        Table(rows, colWidths=widths, repeatRows=1, style=TableStyle(style)),
    ]
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), title=f"{title} - shooting schedule", author="Slugline",
                            leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    doc.build(story)
    return out.getvalue()
