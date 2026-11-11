"""Web API behind the dashboard. Run it with `slugline serve`.

Scripts live in memory for as long as the server runs; nothing is uploaded
anywhere except, when the AI features are used, to the Anthropic API.
"""

from __future__ import annotations

import io
import json
import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from slugline import __version__, elements, export, llm
from slugline.agent import ScriptAgent
from slugline.breakdown import Breakdown, breakdown
from slugline.lint import Issue, lint
from slugline.parser import parse

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD = 25 * 1024 * 1024
BOM = "﻿"  # makes Excel read accented names in a CSV correctly

NO_FRONTEND = """<!doctype html><meta charset="utf-8"><title>Slugline</title>
<body style="font: 16px system-ui; max-width: 40rem; margin: 4rem auto; padding: 0 1rem">
<h1>Slugline</h1>
<p>The API is running, but the dashboard has not been built yet. From the repository:</p>
<pre>cd web && npm install && npm run build</pre>
<p>Then reload this page.</p>"""


@dataclass
class Script:
    id: str
    filename: str
    text: str
    breakdown: Breakdown
    issues: list[Issue]
    analysis: llm.Analysis | None = None
    elements: elements.ElementSheet | None = None
    chats: dict[str, ScriptAgent] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def payload(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "breakdown": self.breakdown.to_dict(),
            "issues": [i.to_dict() for i in self.issues],
            "analysis": self.analysis.to_dict() if self.analysis else None,
            "elements": elements.to_payload(self.elements, self.breakdown),
        }


class Store:
    def __init__(self) -> None:
        self.scripts: dict[str, Script] = {}

    def add(self, filename: str, text: str) -> Script:
        play = parse(text)
        script = Script(
            id=uuid.uuid4().hex[:12],
            filename=filename,
            text=text,
            breakdown=breakdown(play),
            issues=lint(play),
            # A script analyzed before (here or from the CLI) shows its notes at once.
            analysis=llm.cached_analysis(text),
            # So does a breakdown of elements, with its hand edits.
            elements=elements.load_sheet(text),
        )
        self.scripts[script.id] = script
        return script

    def get(self, script_id: str) -> Script:
        try:
            return self.scripts[script_id]
        except KeyError:
            raise HTTPException(404, "That script is no longer loaded. Upload it again.") from None


class ChatRequest(BaseModel):
    message: str
    session: str = "default"


class ElementIn(BaseModel):
    category: str
    name: str
    notes: str = ""


class SceneElements(BaseModel):
    elements: list[ElementIn]


def _to_fountain(filename: str, data: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        from slugline.pdf_import import pdf_to_fountain

        try:
            return pdf_to_fountain(io.BytesIO(data))
        except RuntimeError as e:
            raise HTTPException(422, str(e)) from None
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(422, "The file is not UTF-8 text. Upload a .fountain or .pdf file.") from None


def _download(body: str | bytes, media_type: str, filename: str) -> Response:
    return Response(body, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def create_app() -> FastAPI:
    app = FastAPI(title="Slugline", version=__version__)
    store = app.state.store = Store()

    @app.get("/api/status")
    def status() -> dict:
        try:
            import reportlab  # noqa: F401
            pdf = True
        except ImportError:
            pdf = False
        return {
            "version": __version__,
            "llm": llm.status(),
            "pdf_export": pdf,
            "categories": [{"key": k, "label": label, "color": c} for k, label, c in elements.CATEGORIES],
        }

    @app.get("/api/scripts")
    def list_scripts() -> list[dict]:
        return [{"id": s.id, "filename": s.filename, "title": s.breakdown.title} for s in store.scripts.values()]

    @app.post("/api/scripts")
    async def upload(request: Request, filename: str = "script.fountain") -> dict:
        data = await request.body()
        if not data:
            raise HTTPException(422, "The file is empty.")
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "The file is larger than 25 MB.")
        text = await run_in_threadpool(_to_fountain, filename, data)
        script = await run_in_threadpool(store.add, Path(filename).name, text)
        if not script.breakdown.scenes:
            del store.scripts[script.id]
            raise HTTPException(422, "No scene headings found. Is this a screenplay in Fountain or PDF format?")
        return script.payload()

    @app.get("/api/scripts/{script_id}")
    def get_script(script_id: str) -> dict:
        return store.get(script_id).payload()

    @app.post("/api/scripts/{script_id}/analysis")
    def analyze(script_id: str, refresh: bool = False) -> dict:
        script = store.get(script_id)
        with script.lock:  # two clicks make one analysis, not two
            if script.analysis is None or refresh:
                try:
                    script.analysis = llm.analyze(script.text, use_cache=not refresh)
                except llm.LLMError as e:
                    raise HTTPException(502, str(e)) from None
        return script.analysis.to_dict()

    @app.post("/api/scripts/{script_id}/elements")
    def extract_elements(script_id: str) -> dict:
        script = store.get(script_id)
        with script.lock:
            try:
                script.elements = llm.break_down_elements(script.text)
            except llm.LLMError as e:
                raise HTTPException(502, str(e)) from None
        return elements.to_payload(script.elements, script.breakdown)

    @app.put("/api/scripts/{script_id}/elements/{scene}")
    def edit_elements(script_id: str, scene: str, body: SceneElements) -> dict:
        script = store.get(script_id)
        if scene not in {s.number for s in script.breakdown.scenes}:
            raise HTTPException(404, f"There is no scene {scene} in this script.")
        with script.lock:
            try:
                sheet = elements.update_scene(script.elements, scene, [e.model_dump() for e in body.elements])
            except ValueError as e:
                raise HTTPException(422, str(e)) from None
            try:
                elements.save_sheet(script.text, sheet)
            except OSError as e:
                raise HTTPException(500, f"The change could not be saved: {e.strerror}") from None
            script.elements = sheet
        return elements.to_payload(sheet, script.breakdown)

    @app.post("/api/scripts/{script_id}/chat")
    def chat(script_id: str, body: ChatRequest) -> StreamingResponse:
        script = store.get(script_id)
        question = body.message.strip()
        if not question:
            raise HTTPException(422, "The message is empty.")
        agent = script.chats.get(body.session)
        if agent is None:
            agent = script.chats[body.session] = ScriptAgent(script.text, elements=lambda: script.elements)

        def events() -> Iterator[str]:
            # One JSON object per line, so the browser can show the answer as it is written.
            try:
                for event in agent.ask(question):
                    yield json.dumps(event, ensure_ascii=False) + "\n"
            except llm.LLMError as e:
                yield json.dumps({"type": "error", "message": str(e)}) + "\n"

        return StreamingResponse(events(), media_type="application/x-ndjson")

    @app.delete("/api/scripts/{script_id}/chat/{session}")
    def reset_chat(script_id: str, session: str) -> dict:
        store.get(script_id).chats.pop(session, None)
        return {"ok": True}

    @app.get("/api/scripts/{script_id}/export/{name}")
    def export_file(script_id: str, name: str) -> Response:
        script = store.get(script_id)
        stem = Path(script.filename).stem
        table, _, ext = name.partition(".")
        if ext == "csv" and table in export.CSV_EXPORTS:
            make = export.CSV_EXPORTS[table]
            body = make(script.breakdown, script.analysis) if table == "scenes" else make(script.breakdown)
            return _download(BOM + body, "text/csv; charset=utf-8", f"{stem}-{table}.csv")
        if name == "elements.csv":
            if script.elements is None or script.elements.is_empty():
                raise HTTPException(404, "This script has no elements yet.")
            body = export.elements_csv(script.breakdown, script.elements)
            return _download(BOM + body, "text/csv; charset=utf-8", f"{stem}-elements.csv")
        if name in ("report.pdf", "breakdown-sheets.pdf"):
            try:
                if name == "report.pdf":
                    body = export.report_pdf(script.breakdown, script.issues, script.analysis, script.elements)
                    filename = f"{stem}-breakdown.pdf"
                else:
                    body = export.breakdown_sheets_pdf(script.breakdown, script.elements, script.analysis)
                    filename = f"{stem}-breakdown-sheets.pdf"
            except RuntimeError as e:
                raise HTTPException(501, str(e)) from None
            return _download(body, "application/pdf", filename)
        if name == "script.fountain":
            return _download(script.text, "text/plain; charset=utf-8", f"{stem}.fountain")
        raise HTTPException(404, "Unknown export.")

    if (STATIC / "index.html").is_file():
        app.mount("/", StaticFiles(directory=STATIC, html=True), name="dashboard")
    else:
        @app.get("/", response_class=HTMLResponse)
        def no_frontend() -> str:
            return NO_FRONTEND

    return app
