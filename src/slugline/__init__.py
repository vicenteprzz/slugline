"""Slugline: screenplay breakdown and analysis for Fountain scripts."""

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
    "Dialogue",
    "Scene",
    "Screenplay",
    "Transition",
    "parse",
    "parse_file",
]

__version__ = "0.1.0"
