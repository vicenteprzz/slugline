"""The script library, app settings and the request guard."""

import os
import stat

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from slugline import library, llm, settings  # noqa: E402
from slugline.server import create_app  # noqa: E402

SCRIPT = "Title: Two Rooms\n\nINT. KITCHEN - NIGHT\n\nANNA\nYou came back.\n"
APP = {"x-slugline": "1"}


def test_library_keeps_scripts_between_sessions():
    first = TestClient(create_app(), headers=APP)
    sid = first.post("/api/scripts", params={"filename": "two.fountain"}, content=SCRIPT.encode()).json()["id"]

    # A new server (the app closed and opened again) still has it.
    second = TestClient(create_app(), headers=APP)
    assert [e["id"] for e in second.get("/api/scripts").json()] == [sid]
    reopened = second.get(f"/api/scripts/{sid}").json()
    assert reopened["breakdown"]["title"] == "Two Rooms" and reopened["filename"] == "two.fountain"

    # The same text is the same project, whatever the file is called.
    again = second.post("/api/scripts", params={"filename": "copy.fountain"}, content=SCRIPT.encode()).json()
    assert again["id"] == sid and len(second.get("/api/scripts").json()) == 1

    assert second.delete(f"/api/scripts/{sid}").json() == {"ok": True}
    assert second.get("/api/scripts").json() == []
    assert second.get(f"/api/scripts/{sid}").status_code == 404
    assert second.delete(f"/api/scripts/{sid}").status_code == 404


def test_library_lists_the_most_recent_first_and_rejects_odd_ids(monkeypatch):
    times = iter(["2027-01-01T00:00:00+00:00", "2027-01-02T00:00:00+00:00", "2027-01-03T00:00:00+00:00"])
    monkeypatch.setattr(library, "_now", lambda: next(times))
    a = library.save(SCRIPT, "a.fountain")
    b = library.save(SCRIPT.replace("Two Rooms", "Three Rooms"), "b.fountain")
    assert [e.filename for e in library.entries()] == ["b.fountain", "a.fountain"]
    library.save(SCRIPT, "")  # opened again: moves to the top, keeps its name and first date
    top = library.entries()[0]
    assert (top.id, top.filename, top.added_at) == (a.id, "a.fountain", a.added_at)
    assert b.id != a.id
    assert library.load("../../etc/passwd") is None and library.remove("../x") is False


def test_example_script():
    client = TestClient(create_app(), headers=APP)
    script = client.post("/api/examples/johns-boys").json()
    assert script["breakdown"]["title"] == "John's Boys" and script["breakdown"]["scene_count"] == 13
    assert client.post("/api/examples/nope").status_code == 404


def test_api_key_saved_in_the_app(monkeypatch):
    client = TestClient(create_app(), headers=APP)
    assert client.get("/api/settings").json()["has_api_key"] is False

    bad = client.put("/api/settings", json={"anthropic_api_key": "hello"})
    assert bad.status_code == 422 and "sk-ant-" in bad.json()["detail"]

    key = "sk-ant-api03-" + "x" * 40 + "WXYZ"
    saved = client.put("/api/settings", json={"anthropic_api_key": key, "language": "es", "model": "claude-sonnet-5-5"}).json()
    assert saved["has_api_key"] is True and saved["api_key_source"] == "app"
    assert saved["api_key_hint"] == "sk-ant-…WXYZ" and key not in str(saved)  # the key never comes back
    assert (saved["language"], saved["model"]) == ("es", "claude-sonnet-5-5")
    assert stat.S_IMODE(os.stat(settings.path()).st_mode) == 0o600
    assert client.get("/api/status").json()["llm"]["available"] is True
    assert llm.model_name() == "claude-sonnet-5-5"

    # The SDK client is built with the saved key.
    seen = {}
    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: seen.update(kwargs) or object())
    llm.make_client()
    assert seen == {"api_key": key}

    # An environment variable wins over the app's key.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-env-0000000000")
    assert client.get("/api/settings").json()["api_key_source"] == "environment"

    cleared = client.put("/api/settings", json={"anthropic_api_key": "", "model": ""}).json()
    assert cleared["model"] == "claude-opus-5-5" and settings.load() == {"language": "es"}
    assert client.put("/api/settings", json={"language": "fr"}).status_code == 422
    assert client.put("/api/settings", json={"model": "gpt-5"}).status_code == 422


def test_guard_against_other_websites():
    plain = TestClient(create_app())  # no app header: like a form posted from another site
    assert plain.post("/api/examples/johns-boys").status_code == 403
    assert plain.put("/api/settings", json={"language": "es"}).status_code == 403
    assert plain.get("/api/status").status_code == 200  # reading is harmless

    rebound = TestClient(create_app(), base_url="http://evil.example.com", headers=APP)
    assert rebound.get("/api/status").status_code == 400
    lan = TestClient(create_app(check_host=False), base_url="http://192.168.1.20:8000", headers=APP)
    assert lan.get("/api/status").status_code == 200
