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


# Spanish text for the printed documents, in Spanish production terms.
PDF_ES = {
    "Untitled": "Sin título",
    "Production breakdown · {scenes} scenes · about {pages} pages · {characters} speaking characters · {locations} locations":
        "Desglose de producción · {scenes} secuencias · unas {pages} páginas · {characters} personajes con diálogo · {locations} localizaciones",
    "Stripboard": "Stripboard", "Location": "Localización", "Time": "Momento", "Length": "Duración", "Cast": "Reparto",
    "Cast / summary": "Reparto / resumen", "silent": "sin diálogo", "Character": "Personaje", "Scenes": "Secuencias",
    "Cues": "Interv.", "Words": "Palabras", "Speaks in": "Habla en", "Silent in": "Sin diálogo en", "Locations": "Localizaciones",
    "Scene numbers": "Números de secuencia", "Elements": "Elementos", "Department": "Departamento", "Element": "Elemento",
    "Formatting notes": "Notas de formato", "Level": "Nivel", "Scene": "Sec.", "Note": "Nota", "Source": "Origen",
    "warning": "corregir", "info": "nota", "rule": "regla", "ai": "IA",
    "Int./Ext.": "Int./Ext.", "Day/Night": "Día/Noche", "{n} pages": "{n} páginas", "Starts on page": "Empieza en la página",
    "SYNOPSIS": "SINOPSIS", "No lines: {names}": "Sin diálogo: {names}", "Production notes": "Notas de producción",
    "{title} · Breakdown sheets": "{title} · Hojas de desglose", "Slugline · page {n}": "Slugline · página {n}",
    "Set": "Decorado", "Pages": "Págs.", "DAY {i} OF {n}": "JORNADA {i} DE {n}", "over the {n}-page day": "supera las {n} páginas por jornada",
    "NOT SCHEDULED · {n} scenes": "SIN PROGRAMAR · {n} secuencias",
    "Shooting schedule · {days} days · {pages} pages · planned at {per_day} pages a day":
        "Plan de rodaje · {days} jornadas · {pages} páginas · a {per_day} páginas por jornada",
    "DAY": "JORNADA", "DATE": "FECHA", "CREW CALL": "CITACIÓN GENERAL", "CALL SHEET": "ORDEN DE RODAJE", "{i} of {n}": "{i} de {n}",
    "LOCATIONS": "LOCALIZACIONES", "MEETING POINT / ADDRESS": "PUNTO DE ENCUENTRO / DIRECCIÓN", "NOTES": "NOTAS",
    "Scenes · {pages} pages": "Secuencias · {pages} páginas", "Synopsis": "Sinopsis", "Actor": "Actor/actriz", "Status": "Estado",
    "Call": "Citación", "SW start work · W work · WF work finished · SWF one day only · H on hold today":
        "SW empieza · W trabaja · WF termina · SWF un solo día · H en espera hoy",
    "On hold today: {names}": "En espera hoy: {names}", "Departments": "Departamentos",
    "Advance schedule · day {n}": "Avance · jornada {n}", "call {time}": "citación {time}", "No scenes yet.": "Aún sin secuencias.",
    "{title} · Call sheet": "{title} · Orden de rodaje",
    "Extras": "Figuración", "Stunts": "Especialistas", "Props": "Atrezo", "Wardrobe": "Vestuario",
    "Makeup & hair": "Maquillaje y peluquería", "Vehicles": "Vehículos", "Animals": "Animales",
    "Special effects": "Efectos especiales", "Visual effects": "Efectos visuales", "Sound & music": "Sonido y música",
    "Set dressing": "Decoración", "Special equipment": "Equipo especial",
}
LIGHT_ES = {"DAY": "DÍA", "NIGHT": "NOCHE", "DAWN": "AMANECER", "DUSK": "ATARDECER"}
WEEKDAYS_ES = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MONTHS_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _translator(lang: str):
    table = PDF_ES if lang == "es" else {}

    def tr(text: str, **values) -> str:
        out = table.get(text, text)
        return out.format(**values) if values else out

    return tr


def _light(value: str | None, lang: str) -> str:
    if not value:
        return "-"
    return LIGHT_ES.get(value, value) if lang == "es" else value


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


def _trial_mark(canvas, doc, lang: str) -> None:
    """What a trial prints on every page: a faint diagonal mark and a line at the top."""
    from reportlab.lib import colors

    width, height = doc.pagesize
    text = "SLUGLINE · VERSIÓN DE PRUEBA" if lang == "es" else "SLUGLINE · TRIAL VERSION"
    canvas.saveState()
    canvas.setFillColor(colors.Color(0.55, 0.55, 0.5, alpha=0.10))
    canvas.setFont("Helvetica-Bold", 46)
    canvas.translate(width / 2, height / 2)
    canvas.rotate(35)
    canvas.drawCentredString(0, 0, text)
    canvas.restoreState()
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#b4532a"))
    line = ("Hecho con la versión de prueba de Slugline" if lang == "es" else "Made with the trial version of Slugline")
    canvas.drawCentredString(width / 2, height - 7 * 2.835, line)
    canvas.restoreState()


def _page_decor(lang: str, trial: bool, footer=None):
    """onPage callback: the document's own footer, plus the trial mark if needed."""
    def decorate(canvas, doc) -> None:
        if footer:
            footer(canvas, doc)
        if trial:
            _trial_mark(canvas, doc, lang)
    return decorate


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
    lang: str = "en",
    trial: bool = False,
) -> bytes:
    """A printable production report: stripboard, cast, locations, elements and
    notes. Needs `reportlab`."""
    _reportlab()
    tr = _translator(lang)
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

    title = b.title or tr("Untitled")
    story = [
        Paragraph(escape(title), styles["Title"]),
        p(tr("Production breakdown · {scenes} scenes · about {pages} pages · {characters} speaking characters · {locations} locations",
             scenes=b.scene_count, pages=b.page_count, characters=len(b.characters), locations=len(b.locations)), small),
    ]
    if analysis and analysis.logline:
        story += [Spacer(1, 6), p(analysis.logline)]

    notes = analysis.by_scene() if analysis else {}
    story.append(Paragraph(tr("Stripboard"), h2))
    rows = [["#", "I/E", tr("Location"), tr("Time"), "D/N", tr("Length"), tr("Cast / summary") if notes else tr("Cast")]]
    style = list(base)
    for i, s in enumerate(b.scenes, start=1):
        cast = ", ".join(s.characters) + (f" ({tr('silent')}: {', '.join(s.silent)})" if s.silent else "")
        last = [p(cast)]
        if s.number in notes:
            last.append(p(f"{notes[s.number].summary} [{notes[s.number].tone}]", small))
        rows.append([s.number, s.int_ext or "-", p(s.location), p(s.time_of_day or "-"),
                     _light(s.day_night, lang), format_eighths(s.eighths), last])
        style.append(("BACKGROUND", (0, i), (4, i), colors.HexColor(strip_color(s.int_ext, s.day_night))))
    story.append(Table(rows, colWidths=[10 * mm, 14 * mm, 62 * mm, 34 * mm, 15 * mm, 15 * mm, 117 * mm],
                       repeatRows=1, style=TableStyle(style)))

    story.append(Paragraph(tr("Cast"), h2))
    rows = [[tr("Character"), tr("Scenes"), tr("Cues"), tr("Words"), tr("Speaks in"), tr("Silent in")]]
    rows += [[p(c.name), len(c.scenes), c.dialogue_blocks, c.words, p(", ".join(c.scenes)),
              p(", ".join(c.silent_scenes) or "-")] for c in b.characters]
    story.append(Table(rows, colWidths=[55 * mm, 16 * mm, 14 * mm, 16 * mm, 100 * mm, 66 * mm],
                       repeatRows=1, style=TableStyle(base)))

    story.append(Paragraph(tr("Locations"), h2))
    rows = [[tr("Location"), tr("Scenes"), tr("Length"), tr("Scene numbers")]]
    rows += [[p(loc.location), len(loc.scenes), format_eighths(loc.eighths), p(", ".join(loc.scenes))]
             for loc in b.locations]
    story.append(Table(rows, colWidths=[90 * mm, 16 * mm, 20 * mm, 141 * mm], repeatRows=1, style=TableStyle(base)))

    if elements and not elements.is_empty():
        story.append(Paragraph(tr("Elements"), h2))
        rows = [[tr("Department"), tr("Element"), tr("Scenes"), tr("Length"), tr("Scene numbers")]]
        rows += [[tr(LABELS[t.category]), p(t.name), len(t.scenes), format_eighths(t.eighths), p(", ".join(t.scenes))]
                 for t in totals(elements, b)]
        story.append(Table(rows, colWidths=[35 * mm, 85 * mm, 16 * mm, 20 * mm, 111 * mm], repeatRows=1,
                           style=TableStyle(base)))

    all_issues = list(issues or []) + (analysis.issues if analysis else [])
    if all_issues:
        story.append(Paragraph(tr("Formatting notes"), h2))
        rows = [[tr("Level"), tr("Scene"), tr("Note"), tr("Source")]]
        rows += [[tr(i.severity), i.scene or "-", p(i.message), tr(i.source)] for i in all_issues]
        story.append(Table(rows, colWidths=[20 * mm, 14 * mm, 215 * mm, 18 * mm], repeatRows=1, style=TableStyle(base)))

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), title=f"{title} - breakdown", author="Slugline",
                            leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=14 * mm)
    decor = _page_decor(lang, trial)
    doc.build(story, onFirstPage=decor, onLaterPages=decor)
    return out.getvalue()


def breakdown_sheets_pdf(
    b: Breakdown,
    elements: ElementSheet | None = None,
    analysis: Analysis | None = None,
    lang: str = "en",
    trial: bool = False,
) -> bytes:
    """One breakdown sheet per scene, the page each department head works from.
    Empty boxes are left open for notes by hand. Needs `reportlab`."""
    _reportlab()
    tr = _translator(lang)
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
    title = b.title or tr("Untitled")

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
        meta = [(tr("Int./Ext."), s.int_ext or "-"), (tr("Day/Night"), _light(s.day_night, lang)), (tr("Time"), s.time_of_day or "-"),
                (tr("Length"), tr("{n} pages", n=format_eighths(s.eighths))), (tr("Starts on page"), str(int(s.start_page)))]
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
        story.append(Paragraph(tr("SYNOPSIS"), label))
        if s.number in notes:
            story.append(Paragraph(escape(notes[s.number].summary), body))
        else:
            story.append(Spacer(1, 10 * mm))
        story.append(Spacer(1, 4 * mm))

        cast = [Paragraph(escape(", ".join(s.characters) or "-"), body)]
        if s.silent:
            cast.append(Paragraph(escape(tr("No lines: {names}", names=", ".join(s.silent))), muted))
        items = elements.for_scene(s.number) if elements else []
        cells = [box(tr("Cast"), None, cast)]
        cell_colors: list[str | None] = [None]
        for key, heading, color in [(k, tr(LABELS[k]), COLORS[k]) for k in LABELS]:
            lines = [
                Paragraph(f"• {escape(e.name)}" + (f" <font color='#52514e'>({escape(e.notes)})</font>" if e.notes else ""), body)
                for e in items if e.category == key
            ]
            cells.append(box(heading, color, lines))
            cell_colors.append(color)
        cells.append(box(tr("Production notes"), None, []))
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
        canvas.drawString(14 * mm, 9 * mm, tr("{title} · Breakdown sheets", title=title))
        canvas.drawRightString(A4[0] - 14 * mm, 9 * mm, tr("Slugline · page {n}", n=doc.page))
        canvas.restoreState()

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, title=f"{title} - breakdown sheets", author="Slugline",
                            leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=16 * mm)
    decor = _page_decor(lang, trial, footer)
    doc.build(story, onFirstPage=decor, onLaterPages=decor)
    return out.getvalue()


def _date_label(iso: str, lang: str = "en") -> str:
    from datetime import date

    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    if lang == "es":
        return f"{WEEKDAYS_ES[d.weekday()]} {d.day:02d} {MONTHS_ES[d.month - 1]} {d.year}"
    return d.strftime("%a %d %b %Y")


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


def schedule_pdf(b: Breakdown, schedule: Schedule, elements: ElementSheet | None = None, lang: str = "en",
                 trial: bool = False) -> bytes:
    """The shooting schedule as a stripboard, day by day. Needs `reportlab`."""
    _reportlab()
    tr = _translator(lang)
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
    title = b.title or tr("Untitled")
    total = sum(s.eighths for s in b.scenes)

    widths = [12 * mm, 12 * mm, 88 * mm, 15 * mm, 16 * mm, 70 * mm, 54 * mm]
    rows: list[list] = [["#", "I/E", tr("Set"), "D/N", tr("Pages"), tr("Cast"), tr("Elements")]]
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
        return [s.number, s.int_ext or "-", p(s.heading, slug), _light(s.day_night, lang), format_eighths(s.eighths),
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
        parts = [tr("DAY {i} OF {n}", i=i, n=len(schedule.days))]
        if day.date:
            parts.append(_date_label(day.date, lang))
        if day.call_time:
            parts.append(tr("call {time}", time=day.call_time))
        parts.append(tr("{n} pages", n=format_eighths(stats.eighths)))
        if stats.over:
            parts.append(tr("over the {n}-page day", n=f"{schedule.pages_per_day:g}"))
        if day.notes:
            parts.append(day.notes)
        banner(" · ".join(parts), "#0b0b0b")
        add_strips(day.scenes)
    unscheduled = [s.number for s in b.scenes if s.number not in schedule.scheduled()]
    if unscheduled:
        banner(tr("NOT SCHEDULED · {n} scenes", n=len(unscheduled)), "#898781")
        add_strips(unscheduled)

    story = [
        Paragraph(escape(title), styles["Title"]),
        p(tr("Shooting schedule · {days} days · {pages} pages · planned at {per_day} pages a day",
             days=len(schedule.days), pages=format_eighths(total), per_day=f"{schedule.pages_per_day:g}"), small),
        Table(rows, colWidths=widths, repeatRows=1, style=TableStyle(style)),
    ]
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), title=f"{title} - shooting schedule", author="Slugline",
                            leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    decor = _page_decor(lang, trial)
    doc.build(story, onFirstPage=decor, onLaterPages=decor)
    return out.getvalue()


def call_sheets_pdf(
    b: Breakdown,
    schedule: Schedule,
    elements: ElementSheet | None = None,
    analysis: Analysis | None = None,
    day: int | None = None,
    lang: str = "en",
    trial: bool = False,
) -> bytes:
    """Call sheets: one per shooting day (or only `day`, counted from 1), with
    the day's scenes, cast with their day-out-of-days status, what each
    department needs, and an advance look at the next day. Needs `reportlab`."""
    _reportlab()
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    from slugline.schedule import day_out_of_days

    tr = _translator(lang)
    if not schedule.days:
        raise ValueError("The schedule has no days.")
    if day is not None and not 1 <= day <= len(schedule.days):
        raise ValueError(f"There is no day {day}: the schedule has {len(schedule.days)} days.")

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=8.5, leading=10.5)
    muted = ParagraphStyle("muted", parent=body, textColor=colors.HexColor("#52514e"))
    label = ParagraphStyle("label", parent=body, fontName="Helvetica-Bold", fontSize=7.5, leading=9.5,
                           textColor=colors.HexColor("#52514e"))
    big = ParagraphStyle("big", parent=body, fontName="Helvetica-Bold", fontSize=18, leading=21)
    value = ParagraphStyle("value", parent=body, fontName="Helvetica-Bold", fontSize=11, leading=13)
    slug = ParagraphStyle("slug", parent=body, fontName="Courier-Bold", fontSize=8.5)
    h2 = ParagraphStyle("h2", parent=body, fontName="Helvetica-Bold", fontSize=9.5, leading=12, spaceBefore=8, spaceAfter=3)
    p = lambda text, style=body: Paragraph(escape(str(text)), style)  # noqa: E731
    grid = colors.HexColor("#c3c2b7")
    width = A4[0] - 28 * mm
    rows = {s.number: s for s in b.scenes}
    notes = analysis.by_scene() if analysis else {}
    dood = day_out_of_days(schedule, b)
    title = b.title or tr("Untitled")
    table_style = [
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, grid),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]

    def sheet(i: int) -> list:
        d = schedule.days[i]
        scenes = [rows[n] for n in d.scenes if n in rows]
        stats = day_stats(d, b, schedule.pages_per_day)
        story: list = []

        head = [
            [p(title, big), p(tr("DAY"), label), p(tr("DATE"), label), p(tr("CREW CALL"), label)],
            [p(tr("CALL SHEET"), label), p(tr("{i} of {n}", i=i + 1, n=len(schedule.days)), value),
             p(_date_label(d.date, lang) if d.date else "-", value), p(d.call_time or "-", value)],
        ]
        story.append(Table(head, colWidths=[width - 120 * mm, 30 * mm, 50 * mm, 40 * mm], style=TableStyle([
            ("SPAN", (0, 0), (0, 0)), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, -1), (-1, -1), 1.2, colors.black),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
        ])))

        where = [[p(tr("LOCATIONS"), label), p(tr("MEETING POINT / ADDRESS"), label)],
                 [p(", ".join(stats.locations) or "-"), p(d.address or "-")]]
        story.append(Table(where, colWidths=[width / 2] * 2, style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 6),
        ])))
        if d.notes:
            story += [p(tr("NOTES"), label), p(d.notes)]

        story.append(p(tr("Scenes · {pages} pages", pages=format_eighths(stats.eighths)), h2))
        scene_rows = [["#", tr("Set"), "D/N", tr("Pages"), tr("Cast"), tr("Synopsis")]]
        style = list(table_style)
        for s in scenes:
            scene_rows.append([s.number, p(s.heading, slug), _light(s.day_night, lang), format_eighths(s.eighths),
                               p(", ".join(s.characters) or "-"), p(notes[s.number].summary if s.number in notes else "", muted)])
            style.append(("BACKGROUND", (0, len(scene_rows) - 1), (3, len(scene_rows) - 1),
                          colors.HexColor(strip_color(s.int_ext, s.day_night))))
        story.append(Table(scene_rows, colWidths=[10 * mm, 52 * mm, 15 * mm, 13 * mm, 40 * mm, width - 130 * mm],
                           repeatRows=1, style=TableStyle(style)))

        working = [c for c in dood if c.codes[i] and c.codes[i] != "H"]
        holding = [c for c in dood if c.codes[i] == "H"]
        story.append(p(tr("Cast"), h2))
        cast_rows = [[tr("Character"), tr("Actor"), tr("Status"), tr("Scenes"), tr("Call")]]
        for c in working:
            their = [s.number for s in scenes if c.character in s.characters or c.character in s.silent]
            cast_rows.append([p(c.character), p(c.actor or "-"), c.codes[i], p(", ".join(their)), d.call_time or ""])
        story.append(Table(cast_rows, colWidths=[50 * mm, 50 * mm, 18 * mm, 40 * mm, width - 158 * mm],
                           repeatRows=1, style=TableStyle(table_style)))
        story.append(Spacer(1, 2 * mm))
        story.append(p(tr("SW start work · W work · WF work finished · SWF one day only · H on hold today"), muted))
        if holding:
            names = ", ".join(c.character + (f" ({c.actor})" if c.actor else "") for c in holding)
            story.append(p(tr("On hold today: {names}", names=names), muted))

        if elements:
            needs: dict[str, dict[str, list[str]]] = {}
            for s in scenes:
                for e in elements.for_scene(s.number):
                    needs.setdefault(e.category, {}).setdefault(e.name, []).append(s.number)
            if needs:
                dept_rows = [[p(tr(LABELS[k]), label), p(" · ".join(f"{name} ({', '.join(nums)})" for name, nums in needs[k].items()))]
                             for k in LABELS if k in needs]
                story.append(KeepTogether([
                    p(tr("Departments"), h2),
                    Table(dept_rows, colWidths=[38 * mm, width - 38 * mm], style=TableStyle([
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LINEBELOW", (0, 0), (-1, -1), 0.25, grid),
                        *[("LINEBEFORE", (0, r), (0, r), 3, colors.HexColor(COLORS[k]))
                          for r, k in enumerate(k for k in LABELS if k in needs)],
                    ])),
                ]))

        if i + 1 < len(schedule.days):
            nxt = schedule.days[i + 1]
            upcoming = [rows[n] for n in nxt.scenes if n in rows]
            when = " · ".join(x for x in (_date_label(nxt.date, lang) if nxt.date else "",
                                          nxt.call_time and tr("call {time}", time=nxt.call_time)) if x)
            story.append(p(tr("Advance schedule · day {n}", n=i + 2) + (f" · {when}" if when else ""), h2))
            story.append(p("; ".join(f"{s.number}. {s.heading}" for s in upcoming) or tr("No scenes yet."), muted))
        return story

    story: list = []
    for k, i in enumerate([day - 1] if day else range(len(schedule.days))):
        if k:
            story.append(PageBreak())
        story += sheet(i)

    def footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#898781"))
        canvas.drawString(14 * mm, 9 * mm, tr("{title} · Call sheet", title=title))
        canvas.drawRightString(A4[0] - 14 * mm, 9 * mm, tr("Slugline · page {n}", n=doc.page))
        canvas.restoreState()

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, title=f"{title} - call sheets", author="Slugline",
                            leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=16 * mm)
    decor = _page_decor(lang, trial, footer)
    doc.build(story, onFirstPage=decor, onLaterPages=decor)
    return out.getvalue()


def day_out_of_days_csv(b: Breakdown, schedule: Schedule) -> str:
    from slugline.schedule import day_out_of_days

    header = ["character", "actor"] + [f"day {i}" + (f" ({d.date})" if d.date else "") for i, d in enumerate(schedule.days, 1)]
    rows = [[c.character, c.actor, *c.codes] for c in day_out_of_days(schedule, b)]
    return _csv(header + ["work days", "hold days"], [r + [c.work, c.hold] for r, c in zip(rows, day_out_of_days(schedule, b))])
