"""Command-line interface.

    slugline SCRIPT                  breakdown tables (same as `slugline breakdown SCRIPT`)
    slugline lint SCRIPT             formatting checks
    slugline export SCRIPT ...       CSV tables and a PDF production report
    slugline analyze SCRIPT          AI scene summaries, tone and formatting notes
    slugline elements SCRIPT         props, wardrobe, vehicles... for every scene
    slugline schedule SCRIPT         a shooting schedule, day by day
    slugline ask SCRIPT "question"   ask the script assistant one question
    slugline chat SCRIPT             talk to the script assistant
    slugline serve [SCRIPT]          open the dashboard
    slugline license ...             make and check licences (for the seller)

SCRIPT is a .fountain, .fdx (Final Draft) or .pdf file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from slugline.breakdown import breakdown, render_text
from slugline.parser import parse

COMMANDS = ("breakdown", "lint", "export", "analyze", "elements", "schedule", "ask", "chat", "serve", "license")


class CLIError(Exception):
    pass


def read_script(script: str) -> str:
    """The script as Fountain text, converting from PDF if needed."""
    path = Path(script)
    try:
        if path.suffix.lower() == ".pdf":
            from slugline.pdf_import import pdf_to_fountain

            return pdf_to_fountain(path)
        if path.suffix.lower() == ".fdx":
            from slugline.fdx_import import fdx_to_fountain

            if not path.is_file():
                raise CLIError(f"cannot read {script}: No such file or directory")
            return fdx_to_fountain(path)
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise CLIError(f"{script} is not UTF-8 text") from None
    except OSError as e:
        raise CLIError(f"cannot read {script}: {e.strerror}") from None
    except RuntimeError as e:
        raise CLIError(str(e)) from None


def _write(path: Path, data: str | bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data, encoding="utf-8")
    except OSError as e:
        raise CLIError(f"cannot write {path}: {e.strerror}") from None


def cmd_breakdown(args: argparse.Namespace) -> int:
    text = read_script(args.script)
    if args.fountain:
        _write(Path(args.fountain), text)
    result = breakdown(parse(text))
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(render_text(result))
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    from slugline.lint import lint

    issues = lint(parse(read_script(args.script)))
    if args.json:
        print(json.dumps([i.to_dict() for i in issues], indent=2, ensure_ascii=False))
    elif not issues:
        print("No formatting issues found.")
    else:
        for i in issues:
            where = f"scene {i.scene}" if i.scene else "script"
            print(f"{i.severity:<8} {where:<10} {i.message}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from slugline import export
    from slugline.elements import load_or_carry
    from slugline.lint import lint

    if not (args.csv or args.pdf or args.sheets):
        raise CLIError("nothing to export: pass --csv DIR, --pdf FILE and/or --sheets FILE")
    text = read_script(args.script)
    play = parse(text)
    result = breakdown(play)
    analysis = None
    if args.ai:
        from slugline.llm import analyze

        analysis = analyze(text, progress=lambda m: print(m, file=sys.stderr))
    sheet = load_or_carry(text)  # elements, if this draft or an earlier one was broken down
    if args.csv:
        try:
            for path in export.write_csv(result, args.csv, analysis, sheet):
                print(f"wrote {path}")
        except OSError as e:
            raise CLIError(f"cannot write to {args.csv}: {e.strerror}") from None
    if args.pdf:
        _write(Path(args.pdf), export.report_pdf(result, lint(play), analysis, sheet))
        print(f"wrote {args.pdf}")
    if args.sheets:
        _write(Path(args.sheets), export.breakdown_sheets_pdf(result, sheet, analysis))
        print(f"wrote {args.sheets}")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    from slugline.llm import analyze

    text = read_script(args.script)
    analysis = analyze(text, use_cache=not args.no_cache, progress=lambda m: print(m, file=sys.stderr))
    if args.json:
        print(json.dumps(analysis.to_dict(), indent=2, ensure_ascii=False))
        return 0
    result = breakdown(parse(text))
    notes = analysis.by_scene()
    print(f"{(result.title or 'Untitled').upper()}\n")
    print(f"{analysis.logline}\n\n{analysis.synopsis}\n")
    if analysis.themes:
        print("Themes: " + ", ".join(analysis.themes) + "\n")
    print("SCENES")
    for s in result.scenes:
        print(f"  {s.number}. {s.heading}")
        if s.number in notes:
            n = notes[s.number]
            print(f"     {n.summary}")
            print(f"     tone: {n.tone} · valence {n.valence:+d} · tension {n.tension}/5")
    if analysis.issues:
        print("\nFORMATTING NOTES")
        for i in analysis.issues:
            where = f"scene {i.scene}" if i.scene else "script"
            print(f"  {i.severity:<8} {where:<10} {i.message}")
    return 0


def cmd_elements(args: argparse.Namespace) -> int:
    from slugline.elements import LABELS, load_or_carry, to_payload, totals
    from slugline.parser import format_eighths

    text = read_script(args.script)
    sheet = load_or_carry(text)
    if sheet is None or sheet.is_empty() or args.refresh:
        from slugline.llm import break_down_elements

        sheet = break_down_elements(text, progress=lambda m: print(m, file=sys.stderr))
    result = breakdown(parse(text))
    if args.json:
        print(json.dumps(to_payload(sheet, result), indent=2, ensure_ascii=False))
        return 0
    print(f"{(result.title or 'Untitled').upper()} — ELEMENTS\n")
    if sheet.revision:
        r = sheet.revision
        when = (r["from"].get("saved_at") or "")[:10]
        unchanged = sum(m["status"] == "unchanged" for m in r["scenes"].values())
        print(f"Carried over from the draft saved {when}: {unchanged} scenes unchanged, "
              f"{len(sheet.needs_review())} changed, {len(r['new'])} new, {len(r['omitted'])} omitted.")
        if sheet.needs_review():
            print(f"Check the elements of scenes {', '.join(sheet.needs_review())}: they were rewritten.")
        for scene in r["omitted"]:
            print(f"Omitted: {scene['number']}. {scene['heading']} ({scene.get('elements', 0)} elements dropped)")
        print()
    for s in result.scenes:
        items = sheet.for_scene(s.number)
        print(f"{s.number}. {s.heading}")
        if not items:
            print("   (none)")
        for key, label in LABELS.items():
            names = [e.name + (f" ({e.notes})" if e.notes else "") for e in items if e.category == key]
            if names:
                print(f"   {label}: {', '.join(names)}")
        print()
    print("BY DEPARTMENT")
    for key, label in LABELS.items():
        rows = [t for t in totals(sheet, result) if t.category == key]
        if rows:
            print(f"  {label}")
            for t in rows:
                print(f"    {t.name:<34} scenes {', '.join(t.scenes):<20} {format_eighths(t.eighths)} pages")
    if any(e.source == "ai" for items in sheet.scenes.values() for e in items):
        print("\nSuggested by Claude: check them against the script. Edit them in `slugline serve`.")
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    from slugline import export
    from slugline import schedule as scheduling
    from slugline.elements import load_or_carry
    from slugline.parser import format_eighths

    if not 0.5 <= args.pages <= 30:
        raise CLIError("--pages must be between 0.5 and 30")
    text = read_script(args.script)
    result = breakdown(parse(text))
    plan = None if args.replan else scheduling.load_or_carry(text)
    if plan is None or not plan.days:
        plan = scheduling.suggest(result, args.pages)
        try:
            scheduling.save_schedule(text, plan)
        except OSError as e:
            raise CLIError(f"cannot save the schedule: {e.strerror}") from None
    if args.csv:
        _write(Path(args.csv), "\ufeff" + export.schedule_csv(result, plan))
        print(f"wrote {args.csv}", file=sys.stderr)
    if args.pdf:
        _write(Path(args.pdf), export.schedule_pdf(result, plan, load_or_carry(text)))
        print(f"wrote {args.pdf}", file=sys.stderr)
    if args.call_sheets:
        from slugline.llm import cached_analysis

        sheets = export.call_sheets_pdf(result, plan, load_or_carry(text), cached_analysis(text))
        _write(Path(args.call_sheets), sheets)
        print(f"wrote {args.call_sheets}", file=sys.stderr)
    if args.json:
        print(json.dumps(scheduling.to_payload(plan, result), indent=2, ensure_ascii=False))
        return 0
    rows = {s.number: s for s in result.scenes}
    print(f"{(result.title or 'Untitled').upper()} — SHOOTING SCHEDULE "
          f"({len(plan.days)} days, {plan.pages_per_day:g} pages a day)\n")
    for i, day in enumerate(plan.days, start=1):
        stats = scheduling.day_stats(day, result, plan.pages_per_day)
        extra = (f" · {day.date}" if day.date else "") + (f" · call {day.call_time}" if day.call_time else "")
        extra += " · OVER" if stats.over else ""
        print(f"DAY {i} · {format_eighths(stats.eighths)} pages{extra}")
        for n in day.scenes:
            s = rows[n]
            print(f"  {s.number:>4}  {s.heading:<44} {format_eighths(s.eighths):>6}  {', '.join(s.characters)}")
        print()
    unscheduled = [s for s in result.scenes if s.number not in plan.scheduled()]
    if unscheduled:
        print("NOT SCHEDULED")
        for s in unscheduled:
            print(f"  {s.number:>4}  {s.heading}")
        print()
    print("DAY OUT OF DAYS (SW start, W work, WF finish, SWF one day, H hold)")
    print(f"  {'':<20}" + "".join(f"{i:>5}" for i in range(1, len(plan.days) + 1)) + "   work  hold")
    for c in scheduling.day_out_of_days(plan, result):
        print(f"  {c.character[:20]:<20}" + "".join(f"{x or '.':>5}" for x in c.codes) + f"   {c.work:>4}  {c.hold:>4}")
    return 0


def _print_answer(agent, question: str) -> None:
    for event in agent.ask(question):
        if event["type"] == "text":
            print(event["text"], end="", flush=True)
        elif event["type"] == "tool":
            detail = ", ".join(str(v) for v in event["input"].values()) if event["input"] else ""
            print(f"[{event['name']}{': ' + detail if detail else ''}]", file=sys.stderr, flush=True)
    print()


def cmd_ask(args: argparse.Namespace) -> int:
    from slugline.agent import ScriptAgent

    _print_answer(ScriptAgent(read_script(args.script)), args.question)
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    from slugline.agent import ScriptAgent
    from slugline.llm import LLMError

    agent = ScriptAgent(read_script(args.script))
    print(f"Ask about {agent.play.title or args.script}. An empty line or Ctrl-D ends the chat.")
    while True:
        try:
            question = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not question:
            return 0
        try:
            _print_answer(agent, question)
        except LLMError as e:
            print(f"slugline: {e}", file=sys.stderr)


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn

        from slugline.server import create_app
    except ImportError:
        raise CLIError("the dashboard needs FastAPI: pip install 'slugline[web]'") from None
    local = args.host in ("127.0.0.1", "localhost", "::1")
    # Listening on the network means being reached by other names; on this
    # computer only, requests for any other host name are refused.
    app = create_app(check_host=local)
    url = f"http://{'127.0.0.1' if local else args.host}:{args.port}/"
    if args.script:
        script = app.state.store.add(Path(args.script).name, read_script(args.script))
        url += f"#/scripts/{script.id}"
    print(f"Slugline dashboard: {url}")
    if args.open:
        import threading
        import webbrowser

        threading.Timer(1.0, webbrowser.open, [url]).start()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def cmd_license(args: argparse.Namespace) -> int:
    from slugline import licensing

    try:
        if args.action == "keygen":
            public = licensing.keygen(Path(args.key), force=args.force)
            print(f"Private key: {args.key}  (keep it safe and backed up; never share it)")
            print(f"Public key, now built into the app: {public}")
        elif args.action == "issue":
            key = licensing.issue(args.name, args.kind, None if args.days == 0 else args.days, Path(args.key))
            print(key)
        elif args.action == "check":
            found = licensing.parse(args.licence)
            until = f"until {found.expires}" if found.expires else "with no expiry"
            print(f"Valid: {found.kind} licence for {found.name}, issued {found.issued}, {until}.")
        elif args.action == "activate":
            found = licensing.activate(args.licence)
            print(f"Activated: {found.kind} licence for {found.name}.")
    except licensing.LicenseError as e:
        raise CLIError(str(e)) from None
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="slugline",
        description="Production breakdown for Fountain, Final Draft and PDF screenplays.",
        epilog="`slugline SCRIPT` is short for `slugline breakdown SCRIPT`.",
    )
    sub = ap.add_subparsers(dest="command", required=True, metavar="COMMAND")

    def command(name: str, handler, help: str, script: bool = True) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help, description=help)
        p.set_defaults(handler=handler)
        if script:
            p.add_argument("script", help="path to a .fountain, .fdx or .pdf file")
        return p

    p = command("breakdown", cmd_breakdown, "Print the scene, character and location breakdown.")
    p.add_argument("--json", action="store_true", help="print the breakdown as JSON")
    p.add_argument("--fountain", metavar="OUT", help="also save the script as Fountain to OUT")

    p = command("lint", cmd_lint, "Check the script's formatting.")
    p.add_argument("--json", action="store_true", help="print the issues as JSON")

    p = command("export", cmd_export, "Export the breakdown as CSV tables and PDF reports.")
    p.add_argument("--csv", metavar="DIR", help="write scenes, characters, locations (and elements) CSV files to DIR")
    p.add_argument("--pdf", metavar="FILE", help="write a printable production report to FILE")
    p.add_argument("--sheets", metavar="FILE", help="write one breakdown sheet per scene to FILE (PDF)")
    p.add_argument("--ai", action="store_true", help="include AI scene summaries and tone (uses the Anthropic API)")

    p = command("analyze", cmd_analyze, "AI scene summaries, emotional tone and formatting notes.")
    p.add_argument("--json", action="store_true", help="print the analysis as JSON")
    p.add_argument("--no-cache", action="store_true", help="ignore and don't write the cached analysis")

    p = command("elements", cmd_elements,
                "Break down props, wardrobe, vehicles, effects... for every scene (uses the Anthropic API once).")
    p.add_argument("--json", action="store_true", help="print the elements as JSON")
    p.add_argument("--refresh", action="store_true",
                   help="ask Claude again; elements added or edited by hand are kept")

    p = command("schedule", cmd_schedule,
                "Plan the shoot day by day (the saved schedule, or a first suggestion if there is none).")
    p.add_argument("--pages", type=float, default=5.0, help="pages to shoot per day when suggesting (default: 5)")
    p.add_argument("--replan", action="store_true", help="replace the saved schedule with a new suggestion")
    p.add_argument("--pdf", metavar="FILE", help="also write the schedule as a PDF stripboard")
    p.add_argument("--csv", metavar="FILE", help="also write the schedule as CSV")
    p.add_argument("--call-sheets", metavar="FILE", help="also write a call sheet for every day (PDF)")
    p.add_argument("--json", action="store_true", help="print the schedule as JSON")

    p = command("ask", cmd_ask, "Ask the script assistant one question.")
    p.add_argument("question", help="what you want to know about the script")

    command("chat", cmd_chat, "Talk to the script assistant.")

    p = command("serve", cmd_serve, "Run the web dashboard.", script=False)
    p.add_argument("script", nargs="?", help="a .fountain, .fdx or .pdf file to open")
    p.add_argument("--host", default="127.0.0.1", help="address to listen on (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=8000, help="port to listen on (default: 8000)")
    p.add_argument("--open", action="store_true", help="open the dashboard in the browser")

    p = command("license", cmd_license, "Make and check licences. The keygen and issue actions are for the seller.",
                script=False)
    actions = p.add_subparsers(dest="action", required=True, metavar="ACTION")
    from slugline.licensing import DEFAULT_PRIVATE_KEY, KINDS

    a = actions.add_parser("keygen", help="make the seller's key pair (once)")
    a.add_argument("--key", default=str(DEFAULT_PRIVATE_KEY), help=f"where to save the private key (default: {DEFAULT_PRIVATE_KEY})")
    a.add_argument("--force", action="store_true", help="replace an existing key: licences already sold stop working")
    a = actions.add_parser("issue", help="make a licence for a buyer")
    a.add_argument("name", help="who it is for, as it will show in the app")
    a.add_argument("--kind", choices=KINDS, default="pro", help="kind of licence (default: pro)")
    a.add_argument("--days", type=int, default=365, help="days it lasts; 0 for no expiry (default: 365)")
    a.add_argument("--key", default=str(DEFAULT_PRIVATE_KEY), help="the private key to sign with")
    a = actions.add_parser("check", help="check a licence")
    a.add_argument("licence")
    a = actions.add_parser("activate", help="activate a licence on this computer")
    a.add_argument("licence")
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # `slugline script.fountain [--json]` keeps working as the breakdown command.
    if argv and argv[0] not in COMMANDS and not argv[0].startswith("-"):
        argv.insert(0, "breakdown")
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except CLIError as e:
        print(f"slugline: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:  # LLMError and missing optional dependencies
        print(f"slugline: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
