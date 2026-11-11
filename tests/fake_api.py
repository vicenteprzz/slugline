"""A stand-in for the Anthropic API.

The real SDK client is used, with its HTTP layer replaced by a function that
answers from a script of canned responses. So the tests exercise the actual
request building and stream parsing, and can assert on what was sent, without
a network or an API key.
"""

from __future__ import annotations

import json

import anthropic
import httpx2


def text(value: str) -> dict:
    return {"type": "text", "text": value}


def tool_use(name: str, input: dict, id: str = "toolu_1") -> dict:
    return {"type": "tool_use", "id": id, "name": name, "input": input}


def _sse(blocks: list[dict], stop_reason: str) -> bytes:
    events: list[dict] = [{
        "type": "message_start",
        "message": {"id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
                    "content": [], "stop_reason": None, "stop_sequence": None,
                    "usage": {"input_tokens": 10, "output_tokens": 1}},
    }]
    for i, block in enumerate(blocks):
        if block["type"] == "text":
            start = {"type": "text", "text": ""}
            delta = {"type": "text_delta", "text": block["text"]}
        else:
            start = {**block, "input": {}}
            delta = {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}
        events += [
            {"type": "content_block_start", "index": i, "content_block": start},
            {"type": "content_block_delta", "index": i, "delta": delta},
            {"type": "content_block_stop", "index": i},
        ]
    events += [
        {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None},
         "usage": {"output_tokens": 20}},
        {"type": "message_stop"},
    ]
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


class FakeAPI:
    """Answers each request with the next canned response and records the request."""

    def __init__(self, *responses: list[dict] | tuple[list[dict], str] | httpx2.Response):
        self.responses = list(responses)
        self.requests: list[dict] = []
        self.headers: list[dict] = []
        self.client = anthropic.Anthropic(
            api_key="test-key",
            max_retries=0,
            http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(self._handle)),
        )

    def _handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content))
        self.headers.append(dict(request.headers))
        if not self.responses:
            raise AssertionError("the code made more API requests than the test expected")
        response = self.responses.pop(0)
        if isinstance(response, httpx2.Response):
            return response
        blocks, stop = response if isinstance(response, tuple) else (response, None)
        if stop is None:
            stop = "tool_use" if any(b["type"] == "tool_use" for b in blocks) else "end_turn"
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=_sse(blocks, stop))


def api_error(status: int, kind: str, message: str) -> httpx2.Response:
    return httpx2.Response(status, json={"type": "error", "error": {"type": kind, "message": message}})
