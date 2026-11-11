"""Settings the user changes from the app: their Anthropic API key, the model
and the interface language.

They are kept in settings.json in the data directory, readable only by the
user. Environment variables still win, so `ANTHROPIC_API_KEY=... slugline
serve` works as before.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from slugline import revisions

LANGUAGES = ("en", "es")
MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-2")


def path() -> Path:
    return revisions.data_dir() / "settings.json"


def load() -> dict:
    try:
        data = json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def update(changes: dict) -> dict:
    """Apply changes (a value of None or "" removes the setting) and save."""
    data = load()
    for key, value in changes.items():
        if value in (None, ""):
            data.pop(key, None)
        else:
            data[key] = value
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    # Created readable and writable by the user only: it can hold an API key.
    fd = os.open(target.with_suffix(".tmp"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    target.with_suffix(".tmp").replace(target)
    return data


def api_key() -> str | None:
    """The key to use: the environment's, else the one saved in the app."""
    return os.environ.get("ANTHROPIC_API_KEY") or load().get("anthropic_api_key") or None


def key_source() -> str | None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "environment"
    if load().get("anthropic_api_key"):
        return "app"
    return None


def key_hint(key: str | None) -> str | None:
    """Enough of a key to recognise it, never the key itself."""
    if not key:
        return None
    return f"{key[:7]}…{key[-4:]}" if len(key) > 16 else "…"
