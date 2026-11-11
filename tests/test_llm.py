"""LLM features, run against the real Anthropic SDK with a canned API (see fake_api.py)."""

import json

import pytest

pytest.importorskip("anthropic")

from fake_api import FakeAPI, api_error, text, tool_use  # noqa: E402

from slugline import llm  # noqa: E402
from slugline.agent import TOOLS, ScriptAgent  # noqa: E402
from slugline.cli import main  # noqa: E402

SCRIPT = """Title: Two Rooms

INT. KITCHEN - NIGHT

ANNA pours coffee. Bob watches the door.

ANNA
You came back.

BOB
(quietly)
I never left.

EXT. STREET - LATER

Bob walks alone.

BOB
Taxi!
"""


def scenes_reply(*numbers: str) -> list[dict]:
    notes = [{"number": n, "summary": f"Summary {n}.", "tone": "tense", "valence": -1, "tension": 4} for n in numbers]
    return [text(json.dumps({"scenes": notes}))]


def overview_reply(issues: list[dict] | None = None) -> list[dict]:
    return [text(json.dumps({"logline": "A return.", "synopsis": "Bob comes back.", "themes": ["home"], "issues": issues or []}))]


# --- analysis ---------------------------------------------------------------

def test_analyze_builds_the_analysis_from_two_requests():
    api = FakeAPI(scenes_reply("1", "2", "7"), overview_reply([
        {"scene": "2", "severity": "warning", "message": "Line 16: cue typo."},
        {"scene": "", "severity": "info", "message": "No page numbers."},
    ]))
    result = llm.analyze(SCRIPT, client=api.client, use_cache=False)

    assert [s.number for s in result.scenes] == ["1", "2"]  # scene 7 does not exist, so it is dropped
    assert (result.scenes[0].tone, result.scenes[0].valence, result.scenes[0].tension) == ("tense", -1, 4)
    assert (result.logline, result.themes) == ("A return.", ["home"])
    assert [(i.scene, i.severity, i.source) for i in result.issues] == [("2", "warning", "ai"), (None, "info", "ai")]
    assert result.model == "claude-opus-5-5"


def test_analyze_request_shape():
    api = FakeAPI(scenes_reply("1", "2"), overview_reply())
    llm.analyze(SCRIPT, client=api.client, use_cache=False)
    first, second = api.requests

    assert first["model"] == "claude-opus-5-5" and first["stream"] is True
    assert first["output_config"]["effort"] == "medium"
    assert first["output_config"]["format"]["schema"] == llm.SCENES_SCHEMA
    assert second["output_config"]["format"]["schema"] == llm.OVERVIEW_SCHEMA
    # Refusal fallback is on for the default model.
    assert first["fallbacks"] == "default" and "server-side-fallback" in api.headers[0]["anthropic-beta"]
    # The script is sent as a cached block, identical in both requests, so the second one reads the cache.
    assert first["system"] == second["system"]
    script_block = first["system"][-1]
    assert script_block["cache_control"] == {"type": "ephemeral"}
    assert "[SCENE 1]\n3: INT. KITCHEN - NIGHT" in script_block["text"]
    assert "[SCENE 2]\n14: EXT. STREET - LATER" in script_block["text"]
    assert "1, 2" in first["messages"][0]["content"]
    assert "thinking" not in first and "temperature" not in first


def test_long_scripts_are_analyzed_in_batches(monkeypatch):
    monkeypatch.setattr(llm, "SCENES_PER_REQUEST", 1)
    api = FakeAPI(scenes_reply("1"), scenes_reply("2"), overview_reply())
    seen = []
    result = llm.analyze(SCRIPT, client=api.client, use_cache=False, progress=seen.append)
    assert [s.number for s in result.scenes] == ["1", "2"]
    assert len(api.requests) == 3 and len(seen) == 3


def test_analysis_is_cached_by_script_and_model():
    api = FakeAPI(scenes_reply("1", "2"), overview_reply())
    first = llm.analyze(SCRIPT, client=api.client)
    again = llm.analyze(SCRIPT, client=FakeAPI().client)  # would fail if it made a request
    assert again == first and llm.cached_analysis(SCRIPT) == first
    assert llm.cached_analysis(SCRIPT + "\nMore.\n") is None
    assert llm.cached_analysis(SCRIPT, model="claude-haiku-5-5") is None


def test_other_models_skip_the_fallback_beta(monkeypatch):
    monkeypatch.setenv("SLUGLINE_MODEL", "claude-haiku-5-5")
    api = FakeAPI(scenes_reply("1", "2"), overview_reply())
    assert llm.analyze(SCRIPT, client=api.client, use_cache=False).model == "claude-haiku-5-5"
    assert api.requests[0]["model"] == "claude-haiku-5-5"
    assert "fallbacks" not in api.requests[0] and "anthropic-beta" not in api.headers[0]


@pytest.mark.parametrize(
    "response, expected",
    [
        (api_error(401, "authentication_error", "invalid x-api-key"), "rejected the API key"),
        (api_error(404, "not_found_error", "model: nope"), "model was not found"),
        (api_error(429, "rate_limit_error", "slow down"), "rate limit"),
        (api_error(529, "overloaded_error", "Overloaded"), "returned an error (529)"),
        (([text("")], "refusal"), "declined"),
        (([text('{"scenes": [')], "max_tokens"), "cut off"),
    ],
)
def test_api_failures_become_readable_errors(response, expected):
    with pytest.raises(llm.LLMError, match=expected.replace("(", r"\(").replace(")", r"\)")):
        llm.analyze(SCRIPT, client=FakeAPI(response).client, use_cache=False)
    assert llm.cached_analysis(SCRIPT) is None  # a failed run leaves nothing in the cache


def test_no_scenes_and_no_credentials():
    with pytest.raises(llm.LLMError, match="no scenes"):
        llm.analyze("Just a note.\n", client=FakeAPI().client)
    assert llm.status()["available"] is False
    with pytest.raises(llm.LLMError, match="ANTHROPIC_API_KEY"):
        llm.analyze(SCRIPT, use_cache=False)


# --- agent ------------------------------------------------------------------

def test_agent_runs_tools_and_streams_the_answer():
    api = FakeAPI(
        [text("Checking. "), tool_use("list_characters", {}, "toolu_a"), tool_use("read_scenes", {"numbers": ["2"]}, "toolu_b")],
        [text("Bob has 4 words in 2 cues.")],
    )
    agent = ScriptAgent(SCRIPT, client=api.client)
    events = list(agent.ask("How much does Bob say?"))

    assert [e["type"] for e in events] == ["text", "tool", "tool", "text", "text", "done"]
    assert events[1] == {"type": "tool", "name": "list_characters", "input": {}}
    assert "".join(e["text"] for e in events if e["type"] == "text").strip() == "Checking. \n\nBob has 4 words in 2 cues."

    # Both tool results go back together, in one user message, matched by id.
    results = api.requests[1]["messages"][2]["content"]
    assert [r["tool_use_id"] for r in results] == ["toolu_a", "toolu_b"]
    cast = {c["name"]: c for c in json.loads(results[0]["content"])}
    assert cast["BOB"]["words"] == 4 and cast["BOB"]["cues"] == 2 and cast["ANNA"]["speaks_in_scenes"] == ["1"]
    assert "Bob walks alone." in json.loads(results[1]["content"])[0]["text"]
    assert results[0]["is_error"] is False


def test_agent_request_shape_and_history():
    api = FakeAPI([text("One.")], [text("Two.")])
    agent = ScriptAgent(SCRIPT, client=api.client)
    assert agent.answer("First?") == "One."
    assert agent.answer("Second?") == "Two."

    second = api.requests[1]
    assert [m["role"] for m in second["messages"]] == ["user", "assistant", "user"]
    assert second["messages"][1]["content"][0]["text"] == "One."
    assert [t["name"] for t in second["tools"]] == [t["name"] for t in TOOLS]
    assert all(t["strict"] and t["input_schema"]["additionalProperties"] is False for t in second["tools"])
    system = second["system"][0]
    assert "Two Rooms" in system["text"] and "2. EXT. STREET - LATER (1/8 pages)" in system["text"]
    assert system["cache_control"] == {"type": "ephemeral"}
    assert api.requests[0]["system"] == second["system"]  # stable prefix: cacheable


def test_agent_tools():
    agent = ScriptAgent(SCRIPT)
    scenes, error = agent.run_tool("list_scenes", {})
    assert not error
    assert [(s["number"], s["day_night"], s["speaking"]) for s in json.loads(scenes)] == [
        ("1", "NIGHT", ["ANNA", "BOB"]), ("2", "NIGHT", ["BOB"]),
    ]

    lines = json.loads(agent.run_tool("character_dialogue", {"name": "bob"})[0])
    assert lines["scenes"][0]["lines"] == [{"parentheticals": ["(quietly)"], "text": "I never left."}]

    hits = json.loads(agent.run_tool("search_script", {"query": "COFFEE"})[0])
    assert hits["total"] == 1 and hits["hits"][0] == {"scene": "1", "kind": "action", "text": "ANNA pours coffee. Bob watches the door."}
    spoken = json.loads(agent.run_tool("search_script", {"query": "taxi"})[0])["hits"][0]
    assert (spoken["kind"], spoken["character"]) == ("dialogue", "BOB")

    assert json.loads(agent.run_tool("list_locations", {})[0])[0]["location"] in ("KITCHEN", "STREET")
    assert json.loads(agent.run_tool("format_issues", {})[0]) == []


def test_agent_tool_errors_are_reported_to_the_model_not_raised():
    agent = ScriptAgent(SCRIPT)
    assert agent.run_tool("read_scenes", {"numbers": ["9"]}) == ("No scene numbered 9. Scenes are: 1, 2.", True)
    message, error = agent.run_tool("character_dialogue", {"name": "BOBB"})
    assert error and "Did you mean BOB?" in message
    assert agent.run_tool("read_scenes", {"numbers": "1"})[1] is True
    assert agent.run_tool("search_script", {})[1] is True
    assert agent.run_tool("delete_everything", {}) == ("Unknown tool: delete_everything", True)
    assert agent.run_tool("list_scenes", "not an object")[1] is True


def test_failed_turn_leaves_the_history_untouched():
    api = FakeAPI([text("One.")], api_error(529, "overloaded_error", "Overloaded"), [text("Two.")])
    agent = ScriptAgent(SCRIPT, client=api.client)
    agent.answer("First?")
    with pytest.raises(llm.LLMError):
        agent.answer("Second?")
    assert len(agent.messages) == 2
    assert agent.answer("Second again?") == "Two."
    assert [m["role"] for m in api.requests[2]["messages"]] == ["user", "assistant", "user"]


def test_agent_stops_if_it_never_reaches_an_answer(monkeypatch):
    monkeypatch.setattr("slugline.agent.MAX_STEPS", 2)
    api = FakeAPI([tool_use("list_scenes", {})], [tool_use("list_scenes", {})])
    with pytest.raises(llm.LLMError, match="too many steps"):
        ScriptAgent(SCRIPT, client=api.client).answer("Loop?")


# --- CLI --------------------------------------------------------------------

def test_cli_analyze_and_ask(tmp_path, monkeypatch, capsys):
    path = tmp_path / "two_rooms.fountain"
    path.write_text(SCRIPT, encoding="utf-8")
    api = FakeAPI(scenes_reply("1", "2"), overview_reply(), [tool_use("list_scenes", {})], [text("Two scenes.")])
    monkeypatch.setattr(llm, "make_client", lambda: api.client)
    monkeypatch.setattr("slugline.agent.make_client", lambda: api.client)

    assert main(["analyze", str(path)]) == 0
    out = capsys.readouterr().out
    assert "A return." in out and "1. INT. KITCHEN - NIGHT" in out and "tone: tense · valence -1 · tension 4/5" in out

    assert main(["analyze", str(path), "--json"]) == 0  # served from the cache: no new request
    assert json.loads(capsys.readouterr().out)["logline"] == "A return."

    assert main(["ask", str(path), "How many scenes?"]) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "Two scenes." and "[list_scenes]" in captured.err


def test_cli_reports_llm_errors(tmp_path, capsys):
    path = tmp_path / "two_rooms.fountain"
    path.write_text(SCRIPT, encoding="utf-8")
    assert main(["ask", str(path), "Hello?"]) == 1
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
