"""Command-line interface: `slugline script.fountain|script.pdf [--json] [--fountain OUT]`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from slugline.breakdown import breakdown, render_text
from slugline.parser import parse


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="slugline",
        description="Production breakdown for Fountain and PDF screenplays.",
    )
    ap.add_argument("script", help="path to a .fountain or .pdf file")
    ap.add_argument("--json", action="store_true", help="print the breakdown as JSON")
    ap.add_argument("--fountain", metavar="OUT", help="also save the script as Fountain to OUT")
    args = ap.parse_args(argv)

    path = Path(args.script)
    try:
        if path.suffix.lower() == ".pdf":
            from slugline.pdf_import import pdf_to_fountain

            text = pdf_to_fountain(path)
        else:
            text = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"slugline: cannot read {args.script}: {e.strerror}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"slugline: {e}", file=sys.stderr)
        return 1

    if args.fountain:
        out = Path(args.fountain)
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
        except OSError as e:
            print(f"slugline: cannot write {out}: {e.strerror}", file=sys.stderr)
            return 1

    result = breakdown(parse(text))
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(render_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
