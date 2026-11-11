"""Draw the app icon (a stripboard: four coloured strips) and save Slugline.icns.

macOS only: draws with AppKit (installed with pywebview) and packs the sizes
with iconutil. Run: .venv/bin/python packaging/macos/make_icon.py
"""

import subprocess
import tempfile
from pathlib import Path

import AppKit

HERE = Path(__file__).parent
STRIPS = [(300, 552, "#fff3b0"), (430, 552, "#cfe2f7"), (560, 552, "#fde0c8"), (690, 360, "#cfe8cf")]


def color(hex_value: str, alpha: float = 1.0):
    r, g, b = (int(hex_value[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, alpha)


def draw(size: int) -> bytes:
    rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, size, size, 8, 4, True, False, AppKit.NSDeviceRGBColorSpace, 0, 0)
    AppKit.NSGraphicsContext.saveGraphicsState()
    AppKit.NSGraphicsContext.setCurrentContext_(AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
    k = size / 1024
    flip = lambda y, h: size - (y + h) * k  # noqa: E731  (the drawing is laid out top-down)

    def rounded(x, y, w, h, r, fill):
        fill.setFill()
        AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(((x * k, flip(y, h)), (w * k, h * k)), r * k, r * k).fill()

    rounded(100, 100, 824, 824, 185, color("#141413"))
    for y, w, c in STRIPS:
        rounded(236, y, w, 88, 18, color(c))
        rounded(236, y, 40, 88, 0, color("#141413", 0.18))
    AppKit.NSGraphicsContext.restoreGraphicsState()
    return bytes(rep.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, None))


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "Slugline.iconset"
        iconset.mkdir()
        for base in (16, 32, 128, 256, 512):
            (iconset / f"icon_{base}x{base}.png").write_bytes(draw(base))
            (iconset / f"icon_{base}x{base}@2x.png").write_bytes(draw(base * 2))
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(HERE / "Slugline.icns")], check=True)
        (HERE / "icon.png").write_bytes(draw(512))
    print(f"wrote {HERE / 'Slugline.icns'}")


if __name__ == "__main__":
    main()
