# PyInstaller recipe for the macOS app. Build it with packaging/macos/build.sh.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parents[1]
version = next(
    line.split('"')[1] for line in (ROOT / "pyproject.toml").read_text().splitlines() if line.startswith("version")
)

datas = collect_data_files("slugline")  # the built dashboard and the example script
datas += collect_data_files("reportlab")  # fonts for the PDFs
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("slugline")
    + ["webview.platforms.cocoa", "anthropic", "pypdf", "httpx2"]
)

a = Analysis(
    [str(ROOT / "src" / "slugline" / "desktop.py")],
    pathex=[str(ROOT / "src")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "PyInstaller"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Slugline", console=False, argv_emulation=True)
coll = COLLECT(exe, a.binaries, a.datas, name="Slugline")
app = BUNDLE(
    coll,
    name="Slugline.app",
    icon=str(Path(SPECPATH) / "Slugline.icns"),
    bundle_identifier="app.slugline.desktop",
    version=version,
    info_plist={
        "CFBundleDisplayName": "Slugline",
        "CFBundleShortVersionString": version,
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
        "NSHumanReadableCopyright": "© Vicente Pérez Pourtau",
        # "Open with Slugline" for screenplays in Finder.
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "Screenplay",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
                "CFBundleTypeExtensions": ["fountain", "fdx", "pdf"],
            }
        ],
    },
)
