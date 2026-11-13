"""Read a scanned screenplay: a PDF whose pages are pictures, with no text.

macOS reads the text itself (the Vision framework, the same text recognition
Photos and Preview use), on this computer and with no internet. Each line it
finds comes with where it sits on the page, so the page is laid out again as
monospaced text, column for column, the way a screenplay is typed: the PDF
reader then reads it like any other script.

Needs macOS and `pyobjc-framework-Vision` (and Quartz, which the desktop app
already has). `available()` says whether it can run here.
"""

from __future__ import annotations

import re
from pathlib import Path

# A screenplay is typed in 12 pt Courier: ten characters an inch, six lines an inch.
CHAR_WIDTH = 7.2  # points
LINE_HEIGHT = 12.0  # points
SCALE = 2.0  # render at 144 dpi: small enough to be quick, sharp enough to read


def available() -> bool:
    try:
        import Quartz  # noqa: F401
        import Vision  # noqa: F401
    except ImportError:
        return False
    return True


def _page_image(page, scale: float):
    import Quartz

    box = Quartz.CGPDFPageGetBoxRect(page, Quartz.kCGPDFMediaBox)
    # A scanned page is often stored sideways and turned for display (/Rotate 90):
    # draw it the way it is read, or every line lands in the wrong place.
    w, h = box.size.width, box.size.height
    if Quartz.CGPDFPageGetRotationAngle(page) % 180:
        w, h = h, w
    width, height = int(w * scale), int(h * scale)
    space = Quartz.CGColorSpaceCreateDeviceRGB()
    context = Quartz.CGBitmapContextCreate(None, width, height, 8, 0, space, Quartz.kCGImageAlphaPremultipliedLast)
    Quartz.CGContextSetRGBFillColor(context, 1, 1, 1, 1)
    Quartz.CGContextFillRect(context, Quartz.CGRectMake(0, 0, width, height))
    Quartz.CGContextScaleCTM(context, scale, scale)
    transform = Quartz.CGPDFPageGetDrawingTransform(page, Quartz.kCGPDFMediaBox, Quartz.CGRectMake(0, 0, w, h), 0, True)
    Quartz.CGContextConcatCTM(context, transform)
    Quartz.CGContextDrawPDFPage(context, page)
    return Quartz.CGBitmapContextCreateImage(context), w, h


def _read_lines(image) -> list[tuple[float, float, float, str]]:
    """(left, top, right, text) of every line of text, as fractions of the page."""
    import Vision

    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(False)  # names and slug lines are not dictionary words
    request.setRecognitionLanguages_(["en-US", "es-ES"])
    if hasattr(request, "setAutomaticallyDetectsLanguage_"):
        request.setAutomaticallyDetectsLanguage_(False)  # a smudge is not Russian
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, None)
    ok, _ = handler.performRequests_error_([request], None)
    lines = []
    for observation in (request.results() or []) if ok else []:
        candidates = observation.topCandidates_(1)
        if not candidates:
            continue
        box = observation.boundingBox()  # from the bottom left, 0 to 1
        text = _latin(str(candidates[0].string()))
        if text.strip():
            lines.append((box.origin.x, 1 - box.origin.y - box.size.height, box.origin.x + box.size.width, text))
    return lines


# Letters of other alphabets that look like Latin ones: a scan's "АДАМ" is ADAM.
LOOKALIKES = str.maketrans("АВЕКМНОРСТХУДЛаеорсухіїІЈјΑΒΕΗΙΚΜΝΟΡΤΧΥΖ", "ABEKMHOPCTXYDLaeopcyxiiIJjABEHIKMNOPTXYZ")


def _latin(text: str) -> str:
    """Lookalike letters made Latin; words still in another alphabet are smudges."""
    text = text.translate(LOOKALIKES)
    words = [w for w in text.split(" ") if not re.search(r"[\u0370-\u03ff\u0400-\u04ff\u0590-\u06ff]", w)]
    return " ".join(words)


def _lay_out(lines: list[tuple[float, float, float, str]], width: float, height: float) -> str:
    """The page as monospaced text: each line at its column, rows one after
    another. A scan is never quite 12 points a line, so rows are counted from
    the page's own line spacing, line to line, instead of from the top: a
    rounding error would otherwise leave a blank row inside a speech."""
    if not lines:
        return ""
    items = sorted((top * height, round(left * width / CHAR_WIDTH), text.strip()) for left, top, _, text in lines)
    steps = sorted(b[0] - a[0] for a, b in zip(items, items[1:]) if 0.6 * LINE_HEIGHT < b[0] - a[0] < 1.6 * LINE_HEIGHT)
    unit = steps[len(steps) // 2] if steps else LINE_HEIGHT
    rows: dict[int, list[tuple[int, str]]] = {}
    row, previous = round(items[0][0] / unit), items[0][0]
    for top, column, text in items:
        if top - previous > 0.5 * unit:
            row += max(1, round((top - previous) / unit))
            previous = top
        rows.setdefault(row, []).append((column, text))
    out = []
    for r in range(max(rows) + 1):
        line = ""
        for column, text in sorted(rows.get(r, [])):
            gap = column - len(line)
            line += (" " * gap if gap > 0 else ("   " if line else "")) + text
        out.append(line.rstrip())
    return "\n".join(out)


def pdf_text(path: str | Path, progress=None) -> str:
    """The text of a scanned PDF, pages separated by form feeds, laid out like
    pypdf's layout mode. `progress(done, total)` is called after each page."""
    import Quartz
    from Foundation import NSURL

    document = Quartz.CGPDFDocumentCreateWithURL(NSURL.fileURLWithPath_(str(path)))
    if document is None:
        raise RuntimeError(f"cannot open {path} as a PDF")
    total = Quartz.CGPDFDocumentGetNumberOfPages(document)
    pages = []
    for number in range(1, total + 1):
        image, width, height = _page_image(Quartz.CGPDFDocumentGetPage(document, number), SCALE)
        pages.append(_lay_out(_read_lines(image), width, height))
        if progress:
            progress(number, total)
    return "\f".join(pages)
