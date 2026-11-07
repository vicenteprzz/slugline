"""Command-line interface: `slugline script.fountain [--json]`."""

from __future__ import annotations

import argparse
import json
import sys

from slugline.breakdown import breakdown, render_text
from slugline.parser import parse_file


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="slugline",
        description="Production breakdown for Fountain screenplays.",
    )
    ap.add_argument("script", help="path to a .fountain file")
    ap.add_argument("--json", action="store_true", help="print the breakdown as JSON")
    args = ap.parse_args(argv)

    try:
        play = parse_file(args.script)
    except OSError as e:
        print(f"slugline: cannot read {args.script}: {e.strerror}", file=sys.stderr)
        return 1

    result = breakdown(play)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(render_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
