"""The desktop launcher: a real server on a free port of this computer."""

import json
import urllib.request

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

from slugline.desktop import free_port, start_server  # noqa: E402
from slugline.server import create_app  # noqa: E402


def test_server_starts_on_a_free_local_port():
    port = free_port()
    server = start_server(create_app(), port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=5) as response:
            assert json.load(response)["version"]
        request = urllib.request.Request(f"http://127.0.0.1:{port}/api/examples/johns-boys", method="POST",
                                         headers={"X-Slugline": "1"})
        with urllib.request.urlopen(request, timeout=5) as response:
            assert json.load(response)["breakdown"]["title"] == "John's Boys"
    finally:
        server.should_exit = True
