"""Made-up screenplays, printed as PDFs in several layouts and read back:
the reading is scored against what was written (see tools/synth.py)."""

import random
import sys
from pathlib import Path

import pytest

pytest.importorskip("reportlab")
pytest.importorskip("pypdf")
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import synth  # noqa: E402


@pytest.mark.parametrize("layout", synth.LAYOUTS, ids=lambda layout: layout.name)
def test_made_up_scripts_are_read_back(layout):
    rng = random.Random(11)
    totals = {"scenes": 0, "found": 0, "headings_right": 0, "cues": 0, "cues_right": 0, "characters_wrong": 0, "extra": 0}
    for _ in range(4):
        script = synth.make_script(rng)
        result = synth.score(script, synth.read_back(synth.render(script, layout, rng), rng, 0),
                             both_numbers=layout.numbers != "none")
        for key in totals:
            totals[key] += result[key]
    assert totals["found"] >= 0.98 * totals["scenes"]
    assert totals["headings_right"] >= 0.98 * totals["scenes"]
    assert totals["cues_right"] >= 0.95 * totals["cues"]
    assert totals["characters_wrong"] <= 1 and totals["extra"] == 0
