import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

EXAMPLE = Path(__file__).parent.parent / "examples" / "johns_boys.fountain"


@pytest.fixture(scope="session")
def example_text() -> str:
    return EXAMPLE.read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def isolated_llm(tmp_path, monkeypatch):
    """No test reads the developer's API key, model setting, analysis cache or saved breakdowns."""
    monkeypatch.setenv("SLUGLINE_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("SLUGLINE_DATA", str(tmp_path / "data"))
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "SLUGLINE_MODEL"):
        monkeypatch.delenv(name, raising=False)
