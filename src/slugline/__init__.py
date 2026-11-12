"""Slugline: screenplay breakdown and analysis for Fountain and PDF scripts."""

from slugline.breakdown import Breakdown, breakdown
from slugline.lint import Issue, lint
from slugline.parser import (
    Action,
    Dialogue,
    Scene,
    Screenplay,
    Transition,
    parse,
    parse_file,
)

__all__ = [
    "Action",
    "Breakdown",
    "Dialogue",
    "Issue",
    "Scene",
    "Screenplay",
    "Transition",
    "breakdown",
    "lint",
    "parse",
    "parse_file",
]

__version__ = "0.12.0"
