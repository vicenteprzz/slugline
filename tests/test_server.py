"""The web API behind the dashboard."""

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("anthropic")

from fake_api import FakeAPI, text, tool_use  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from slugline import llm  # noqa: E402
from slugline.server import create_app  # noqa: E402
from test_llm import SCRIPT, overview_reply, scenes_reply  # noqa: E402


@pytest.fixture
def client():
    return TestClient(create_app())


def upload(client, text_=SCRIPT, filename="two_rooms.fountain"):
    data = text_ if isinstance(text_, bytes) else text_.encode()
    return client.post("/api/scripts", params={"filename": filename}, content=data)


def use_api(monkeypatch, api):
    monkeypatch.setattr(llm, "make_client", lambda: api.client)
    monkeypatch.setattr("slugline.agent.make_client", lambda: api.client)


def test_status_without_credentials(client):
    status = client.get("/api/status").json()
    assert status["llm"]["available"] is False and "ANTHROPIC_API_KEY" in status["llm"]["reason"]
    assert status["llm"]["model"] == "claude-opus-5-5"


def test_upload_returns_the_breakdown(client):
    response = upload(client)
    assert response.status_code == 200
    script = response.json()
    assert script["filename"] == "two_rooms.fountain" and script["analysis"] is None
    assert script["breakdown"]["title"] == "Two Rooms"
    assert [s["heading"] for s in script["breakdown"]["scenes"]] == ["INT. KITCHEN - NIGHT", "EXT. STREET - LATER"]
    assert script["breakdown"]["scenes"][0]["words"] == {"ANNA": 3, "BOB": 3}
    assert script["issues"] == []

    assert client.get(f"/api/scripts/{script['id']}").json() == script
    assert client.get("/api/scripts").json() == [{"id": script["id"], "filename": "two_rooms.fountain", "title": "Two Rooms"}]


@pytest.mark.parametrize(
    "data, filename, status, message",
    [
        (b"", "a.fountain", 422, "empty"),
        (b"\xff\xfe\x00bad", "a.fountain", 422, "not UTF-8"),
        (b"Just some notes, no scenes.\n", "a.fountain", 422, "No scene headings"),
        (b"not a pdf", "a.pdf", 422, "as a PDF"),
    ],
)
def test_bad_uploads_are_refused_with_a_reason(client, data, filename, status, message):
    response = upload(client, data, filename)
    assert response.status_code == status and message in response.json()["detail"]
    assert client.get("/api/scripts").json() == []


def test_unknown_script(client):
    assert client.get("/api/scripts/nope").status_code == 404
    assert client.post("/api/scripts/nope/analysis").status_code == 404


def test_exports(client):
    script_id = upload(client).json()["id"]
    scenes = client.get(f"/api/scripts/{script_id}/export/scenes.csv")
    assert scenes.status_code == 200 and scenes.headers["content-type"].startswith("text/csv")
    assert 'filename="two_rooms-scenes.csv"' in scenes.headers["content-disposition"]
    assert "KITCHEN" in scenes.text and scenes.content.startswith(b"\xef\xbb\xbf")
    assert "ANNA" in client.get(f"/api/scripts/{script_id}/export/characters.csv").text
    assert "STREET" in client.get(f"/api/scripts/{script_id}/export/locations.csv").text
    assert client.get(f"/api/scripts/{script_id}/export/script.fountain").text == SCRIPT
    assert client.get(f"/api/scripts/{script_id}/export/secrets.csv").status_code == 404

    pytest.importorskip("reportlab")
    pdf = client.get(f"/api/scripts/{script_id}/export/report.pdf")
    assert pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")


def test_analysis_runs_once_and_is_kept(client, monkeypatch):
    api = FakeAPI(scenes_reply("1", "2"), overview_reply(), scenes_reply("1", "2"), overview_reply())
    use_api(monkeypatch, api)
    script_id = upload(client).json()["id"]

    analysis = client.post(f"/api/scripts/{script_id}/analysis").json()
    assert analysis["logline"] == "A return." and len(analysis["scenes"]) == 2
    assert client.post(f"/api/scripts/{script_id}/analysis").json() == analysis
    assert len(api.requests) == 2
    assert client.get(f"/api/scripts/{script_id}").json()["analysis"] == analysis
    assert "Summary 1." in client.get(f"/api/scripts/{script_id}/export/scenes.csv").text
    # The same script uploaded again already has its analysis, from the disk cache.
    assert upload(client).json()["analysis"] == analysis

    client.post(f"/api/scripts/{script_id}/analysis", params={"refresh": True})
    assert len(api.requests) == 4


def test_analysis_failure_is_a_502_with_the_reason(client):
    script_id = upload(client).json()["id"]
    response = client.post(f"/api/scripts/{script_id}/analysis")
    assert response.status_code == 502 and "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_chat_streams_events_and_remembers_the_conversation(client, monkeypatch):
    api = FakeAPI([tool_use("list_scenes", {})], [text("Two scenes.")], [text("Still two.")])
    use_api(monkeypatch, api)
    script_id = upload(client).json()["id"]

    def ask(message, session="s1"):
        response = client.post(f"/api/scripts/{script_id}/chat", json={"message": message, "session": session})
        assert response.headers["content-type"].startswith("application/x-ndjson")
        return [json.loads(line) for line in response.text.splitlines()]

    events = ask("How many scenes?")
    assert events[0] == {"type": "tool", "name": "list_scenes", "input": {}}
    assert events[-1] == {"type": "done"}
    assert "".join(e["text"] for e in events if e["type"] == "text").strip() == "Two scenes."

    ask("Sure?")
    assert len(api.requests[2]["messages"]) == 5  # question, tool call, tool result, answer, new question

    client.delete(f"/api/scripts/{script_id}/chat/s1")
    api.responses.append([text("Fresh.")])
    ask("Hello again")
    assert len(api.requests[3]["messages"]) == 1


def test_chat_errors_arrive_as_an_event(client):
    script_id = upload(client).json()["id"]
    response = client.post(f"/api/scripts/{script_id}/chat", json={"message": "Hi"})
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events == [{"type": "error", "message": "No Anthropic credentials found. Set ANTHROPIC_API_KEY."}]
    assert client.post(f"/api/scripts/{script_id}/chat", json={"message": "  "}).status_code == 422


def test_index_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200 and "Slugline" in response.text
