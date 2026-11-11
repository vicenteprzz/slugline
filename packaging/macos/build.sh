#!/usr/bin/env bash
# Build dist/Slugline.app (and a .dmg to share it) on macOS.
#
#   packaging/macos/build.sh
#
# Needs the project's virtual environment with `pip install -e ".[desktop]"`
# and Node.js for the dashboard.
set -euo pipefail
cd "$(dirname "$0")/../.."

PY=${PYTHON:-.venv/bin/python}

echo "Building the dashboard…"
(cd web && npm ci --silent && npm run build)

echo "Packaging the app…"
"$PY" -m PyInstaller --noconfirm --clean --distpath dist --workpath build/pyinstaller packaging/macos/Slugline.spec

echo "Making the disk image…"
# The usual Mac installer: the app next to a shortcut to Applications, to drag it onto.
STAGE=build/dmg
rm -rf "$STAGE" dist/Slugline.dmg
mkdir -p "$STAGE"
cp -R dist/Slugline.app "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -quiet -volname Slugline -srcfolder "$STAGE" -ov -format UDZO dist/Slugline.dmg

echo "Done: dist/Slugline.app and dist/Slugline.dmg"
