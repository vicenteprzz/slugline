"""Slugline as a desktop app: the dashboard in its own window.

Starts the server on a free port of this computer and shows the dashboard in
a native window (pywebview). Closing the window quits. Without pywebview the
dashboard opens in the default browser instead.

Run it with `slugline-app [SCRIPT]`. The macOS application built from
packaging/macos runs this module.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

TITLE = "Slugline"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(app, port: int):
    import uvicorn

    # log_config=None: a windowed app has no console for uvicorn's log handlers.
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None, log_level="warning"))
    thread = threading.Thread(target=server.run, name="slugline-server", daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError("the Slugline server did not start")
        time.sleep(0.05)
    return server


def _say(message: str) -> None:
    # A windowed app has no stdout; printing there would raise.
    if sys.stdout is not None:
        print(message, flush=True)


def main(argv: list[str] | None = None) -> int:
    from slugline.server import create_app

    args = [a for a in (sys.argv[1:] if argv is None else argv) if not a.startswith("-psn_")]  # macOS adds -psn_ ids
    app = create_app()
    port = free_port()
    url = f"http://127.0.0.1:{port}/"
    if args:
        from slugline.cli import CLIError, read_script

        try:
            script = app.state.store.add(Path(args[0]).name, read_script(args[0]))
            url += f"#/scripts/{script.id}"
        except CLIError as e:
            _say(f"slugline: {e}")

    server = start_server(app, port)
    _say(f"Slugline is running at {url}")

    if os.environ.get("SLUGLINE_HEADLESS"):  # for checking a packaged build: serve, no window
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return 0
    try:
        import webview
    except ImportError:
        webbrowser.open(url)
        _say("Press Ctrl-C to quit.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
    else:
        webview.settings["ALLOW_DOWNLOADS"] = True  # the export menu downloads PDFs and CSVs
        webview.create_window(TITLE, url, width=1380, height=900, min_size=(960, 640), text_select=True)
        webview.start()  # returns when the window is closed
    server.should_exit = True
    return 0


if __name__ == "__main__":
    sys.exit(main())
