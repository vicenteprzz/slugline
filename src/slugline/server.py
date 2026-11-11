"""Web API behind the dashboard. Run it with `slugline serve`.

Scripts are kept on this computer (see `library`); nothing is uploaded
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
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from slugline import __version__, elements, export, library, licensing, llm, revisions, settings
from slugline import schedule as scheduling
from slugline.agent import ScriptAgent
from slugline.breakdown import Breakdown, breakdown
from slugline.lint import Issue, lint
from slugline.parser import parse

STATIC = Path(__file__).parent / "static"
EXAMPLES = {"johns-boys": Path(__file__).parent / "examples" / "johns_boys.fountain"}
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "testserver"}
# Requests that change something must carry this header. Browsers don't let
# another website add it without asking the server first, so a page open in
# another tab can't use this app (and its API key) behind the user's back.
APP_HEADER = "x-slugline"
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
    schedule: scheduling.Schedule | None = None
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
            "schedule": scheduling.to_payload(self.schedule, self.breakdown),
        }


class Store:
    def __init__(self) -> None:
        self.scripts: dict[str, Script] = {}

    def add(self, filename: str, text: str, keep: bool = True) -> Script:
        """Open a script: from memory if it's open, else parsed and, if `keep`,
        saved in the library so it's still there next time."""
        script_id = library.save(text, filename).id if keep else uuid.uuid4().hex[:12]
        if script_id in self.scripts:
            self.scripts[script_id].filename = filename or self.scripts[script_id].filename
            return self.scripts[script_id]
        play = parse(text)
        script = Script(
            id=script_id,
            filename=filename,
            text=text,
            breakdown=breakdown(play),
            issues=lint(play),
            # A script analyzed before (here or from the CLI) shows its notes at once.
            analysis=llm.cached_analysis(text),
            # So does a breakdown of elements, with its hand edits; a new
            # draft starts from the breakdown of the draft before it.
            elements=elements.load_or_carry(text),
            schedule=scheduling.load_or_carry(text),
        )
        self.scripts[script.id] = script
        return script

    def get(self, script_id: str) -> Script:
        if script_id in self.scripts:
            return self.scripts[script_id]
        saved = library.load(script_id)
        if saved is None:
            raise HTTPException(404, "That script is not in your library. Open the file again.")
        entry, text = saved
        return self.add(entry.filename, text)

    def remove(self, script_id: str) -> bool:
        self.scripts.pop(script_id, None)
        return library.remove(script_id)


class SettingsIn(BaseModel):
    # Omitted fields are left as they are; an empty string removes the setting.
    anthropic_api_key: str | None = None
    model: str | None = None
    language: str | None = None


class LicenseIn(BaseModel):
    key: str


class ChatRequest(BaseModel):
    message: str
    session: str = "default"


class ElementIn(BaseModel):
    category: str
    name: str
    notes: str = ""


class SceneElements(BaseModel):
    elements: list[ElementIn]


class SuggestSchedule(BaseModel):
    pages_per_day: float = scheduling.DEFAULT_PAGES_PER_DAY


class DayIn(BaseModel):
    id: str = ""
    scenes: list[str]
    date: str = ""
    notes: str = ""
    call_time: str = ""
    address: str = ""


class ScheduleIn(BaseModel):
    days: list[DayIn]
    pages_per_day: float | None = None
    actors: dict[str, str] | None = None


def _to_fountain(filename: str, data: bytes) -> str:
    if filename.lower().endswith(".fdx"):
        from slugline.fdx_import import fdx_to_fountain

        try:
            return fdx_to_fountain(data)
        except RuntimeError as e:
            message = str(e)
            raise HTTPException(422, message[:1].upper() + message[1:]) from None
    if filename.lower().endswith(".pdf"):
        from slugline.pdf_import import pdf_to_fountain

        try:
            return pdf_to_fountain(io.BytesIO(data))
        except RuntimeError as e:
            raise HTTPException(422, str(e)) from None
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(422, "The file is not UTF-8 text. Upload a .fountain, .fdx or .pdf file.") from None


def _download(body: str | bytes, media_type: str, filename: str) -> Response:
    return Response(body, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _settings_payload() -> dict:
    saved = settings.load()
    key = settings.api_key()
    return {
        "has_api_key": bool(key),
        "api_key_hint": settings.key_hint(key),
        "api_key_source": settings.key_source(),
        "model": llm.model_name(),
        "models": list(settings.MODELS),
        "language": saved.get("language"),
    }


def _example_ids() -> set[str]:
    return {revisions.script_key(p.read_text(encoding="utf-8")) for p in EXAMPLES.values() if p.is_file()}


def _license_status() -> dict:
    found = licensing.status()
    examples = _example_ids()
    found["scripts"] = sum(1 for e in library.entries() if e.id not in examples)
    return found


def create_app(check_host: bool = True) -> FastAPI:
    app = FastAPI(title="Slugline", version=__version__)
    store = app.state.store = Store()

    @app.middleware("http")
    async def guard(request: Request, call_next):
        # Only answer to this computer's own addresses (protects against DNS
        # rebinding), and only accept changes from the app itself.
        host = (request.headers.get("host") or "").rsplit(":", 1)[0]
        if check_host and host not in LOCAL_HOSTS:
            return JSONResponse({"detail": "Slugline only answers on this computer."}, status_code=400)
        if request.method in ("POST", "PUT", "DELETE") and request.url.path.startswith("/api/") \
                and request.headers.get(APP_HEADER) != "1":
            return JSONResponse({"detail": "Requests must come from the Slugline app."}, status_code=403)
        return await call_next(request)

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
            "license": _license_status(),
            "categories": [{"key": k, "label": label, "color": c} for k, label, c in elements.CATEGORIES],
        }

    @app.get("/api/scripts")
    def list_scripts() -> list[dict]:
        """The library: every saved script, most recently opened first."""
        return [e.to_dict() for e in library.entries()]

    @app.delete("/api/scripts/{script_id}")
    def remove_script(script_id: str) -> dict:
        if not store.remove(script_id):
            raise HTTPException(404, "That script is not in your library.")
        return {"ok": True}

    @app.post("/api/examples/{name}")
    def open_example(name: str) -> dict:
        path = EXAMPLES.get(name)
        if path is None or not path.is_file():
            raise HTTPException(404, "There is no example with that name.")
        return store.add(path.name, path.read_text(encoding="utf-8")).payload()

    @app.put("/api/license")
    def activate_license(body: LicenseIn) -> dict:
        try:
            licensing.activate(body.key)
        except licensing.LicenseError as e:
            raise HTTPException(422, str(e)) from None
        except OSError as e:
            raise HTTPException(500, f"The licence could not be saved: {e.strerror}") from None
        return _license_status()

    @app.delete("/api/license")
    def remove_license() -> dict:
        licensing.deactivate()
        return _license_status()

    @app.get("/api/settings")
    def get_settings() -> dict:
        return _settings_payload()

    @app.put("/api/settings")
    def put_settings(body: SettingsIn) -> dict:
        changes: dict = {}
        if body.anthropic_api_key is not None:
            key = body.anthropic_api_key.strip()
            if key and (not key.startswith("sk-ant-") or len(key) > 300 or any(c.isspace() for c in key)):
                raise HTTPException(422, "That doesn't look like an Anthropic API key. Keys start with sk-ant-.")
            changes["anthropic_api_key"] = key
        if body.model is not None:
            if body.model and body.model not in settings.MODELS:
                raise HTTPException(422, f"Unknown model. Choose one of: {', '.join(settings.MODELS)}.")
            changes["model"] = body.model
        if body.language is not None:
            if body.language and body.language not in settings.LANGUAGES:
                raise HTTPException(422, "The interface is available in English (en) and Spanish (es).")
            changes["language"] = body.language
        try:
            settings.update(changes)
        except OSError as e:
            raise HTTPException(500, f"The settings could not be saved: {e.strerror}") from None
        return _settings_payload()

    @app.post("/api/scripts")
    async def upload(request: Request, filename: str = "script.fountain") -> dict:
        data = await request.body()
        if not data:
            raise HTTPException(422, "The file is empty.")
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "The file is larger than 25 MB.")
        text = await run_in_threadpool(_to_fountain, filename, data)
        if not parse(text).scenes:  # checked before anything is saved
            raise HTTPException(422, "No scene headings found. Is this a screenplay in Fountain, Final Draft or PDF format?")
        if licensing.current() is None:
            known = {e.id for e in library.entries()}
            examples = _example_ids()
            kept = len(known - examples)
            if revisions.script_key(text) not in known and kept >= licensing.FREE_SCRIPTS:
                raise HTTPException(
                    402,
                    f"The trial keeps {licensing.FREE_SCRIPTS} scripts. Remove one from your scripts, "
                    "or activate a licence in Settings.",
                )
        script = await run_in_threadpool(store.add, Path(filename).name, text)
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

    @app.delete("/api/scripts/{script_id}/elements")
    def clear_elements(script_id: str) -> dict:
        """Start this draft's breakdown from scratch (and stop carrying an old one over)."""
        script = store.get(script_id)
        with script.lock:
            sheet = elements.ElementSheet()
            try:
                elements.save_sheet(script.text, sheet)
            except OSError as e:
                raise HTTPException(500, f"The change could not be saved: {e.strerror}") from None
            script.elements = sheet
        return elements.to_payload(sheet, script.breakdown)

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

    def _save_schedule(script: Script, plan: scheduling.Schedule) -> dict:
        try:
            scheduling.save_schedule(script.text, plan)
        except OSError as e:
            raise HTTPException(500, f"The schedule could not be saved: {e.strerror}") from None
        script.schedule = plan
        return scheduling.to_payload(plan, script.breakdown)

    @app.post("/api/scripts/{script_id}/schedule")
    def suggest_schedule(script_id: str, body: SuggestSchedule) -> dict:
        script = store.get(script_id)
        if not 0.5 <= body.pages_per_day <= 30:
            raise HTTPException(422, "Pages per day must be between 0.5 and 30.")
        with script.lock:
            plan = scheduling.suggest(script.breakdown, body.pages_per_day)
            if script.schedule:
                plan.actors = script.schedule.actors  # a new plan keeps the cast list
            return _save_schedule(script, plan)

    @app.put("/api/scripts/{script_id}/schedule")
    def edit_schedule(script_id: str, body: ScheduleIn) -> dict:
        script = store.get(script_id)
        if body.pages_per_day is not None and not 0.5 <= body.pages_per_day <= 30:
            raise HTTPException(422, "Pages per day must be between 0.5 and 30.")
        with script.lock:
            try:
                plan = scheduling.set_days(script.breakdown, [d.model_dump() for d in body.days],
                                           body.pages_per_day, script.schedule, body.actors)
            except ValueError as e:
                raise HTTPException(422, str(e)) from None
            return _save_schedule(script, plan)

    @app.delete("/api/scripts/{script_id}/schedule")
    def clear_schedule(script_id: str) -> dict:
        script = store.get(script_id)
        with script.lock:
            _save_schedule(script, scheduling.Schedule())
            script.schedule = None
        return {"ok": True}

    @app.post("/api/scripts/{script_id}/chat")
    def chat(script_id: str, body: ChatRequest) -> StreamingResponse:
        script = store.get(script_id)
        question = body.message.strip()
        if not question:
            raise HTTPException(422, "The message is empty.")
        agent = script.chats.get(body.session)
        if agent is None:
            agent = script.chats[body.session] = ScriptAgent(
                script.text, elements=lambda: script.elements, schedule=lambda: script.schedule
            )

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
    def export_file(script_id: str, name: str, day: int | None = None, lang: str = "en") -> Response:
        lang = lang if lang in settings.LANGUAGES else "en"
        trial = licensing.current() is None
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
        if name in ("schedule.csv", "schedule.pdf", "day-out-of-days.csv", "call-sheets.pdf"):
            if not script.schedule or not script.schedule.days:
                raise HTTPException(404, "This script has no shooting schedule yet.")
            if name == "schedule.csv":
                body = export.schedule_csv(script.breakdown, script.schedule)
                return _download(BOM + body, "text/csv; charset=utf-8", f"{stem}-schedule.csv")
            if name == "day-out-of-days.csv":
                body = export.day_out_of_days_csv(script.breakdown, script.schedule)
                return _download(BOM + body, "text/csv; charset=utf-8", f"{stem}-day-out-of-days.csv")
            try:
                if name == "schedule.pdf":
                    body = export.schedule_pdf(script.breakdown, script.schedule, script.elements, lang, trial)
                    filename = f"{stem}-schedule.pdf"
                else:
                    body = export.call_sheets_pdf(script.breakdown, script.schedule, script.elements,
                                                  script.analysis, day, lang, trial)
                    filename = f"{stem}-call-sheet-day-{day}.pdf" if day else f"{stem}-call-sheets.pdf"
            except RuntimeError as e:
                raise HTTPException(501, str(e)) from None
            except ValueError as e:
                raise HTTPException(404, str(e)) from None
            return _download(body, "application/pdf", filename)
        if name in ("report.pdf", "breakdown-sheets.pdf"):
            try:
                if name == "report.pdf":
                    body = export.report_pdf(script.breakdown, script.issues, script.analysis, script.elements, lang, trial)
                    filename = f"{stem}-breakdown.pdf"
                else:
                    body = export.breakdown_sheets_pdf(script.breakdown, script.elements, script.analysis, lang, trial)
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
