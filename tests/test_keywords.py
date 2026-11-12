"""Element suggestions without AI."""

from slugline import parse
from slugline.elements import load_or_carry, load_sheet, update_scene
from slugline.keywords import suggest

EN = """Title: Night Shift

INT. BAR - NIGHT

A crowd of customers. Mia pours whiskey from a bottle. The camera PUSHES IN on her face.

MIA
Put the gun down.

KNOCK KNOCK. Someone at the door. Rain hammers the window.

EXT. STREET - NIGHT

A police car pulls up. Its siren wails. Blood on the pavement.

INT. CAR - NIGHT

Quiet. Mia drives.
"""

ES = """Title: Turno de noche

INT. BAR - NOCHE

Una multitud de clientes. Mía sirve whisky de una botella. La cámara se acerca a su cara.

MÍA
Baja la pistola.

TOC TOC. Llueve contra la ventana.

EXT. CALLE - NOCHE

Llega un coche de policía. Se oye una sirena. Hay sangre en la acera.
"""


def names(text):
    """Each scene's suggestions as a set: order within a department doesn't matter."""
    return {n: {(e.category, e.name) for e in items} for n, items in suggest(parse(text)).items()}


def test_english_script():
    found = names(EN)
    assert found["1"] == {
        ("extras", "Crowd"), ("extras", "Customers"), ("props", "Bottle"),
        ("sfx", "Rain"), ("sound", "Knock at the door"),
    }
    # "the gun" is in the dialogue, not the action: no prop. "The camera PUSHES IN" is a direction.
    assert ("props", "Gun") not in found["1"] and ("props", "Camera") not in found["1"]
    assert found["2"] == {("makeup", "Blood"), ("vehicles", "Police car"), ("sound", "Siren")}  # not "Car" too
    assert found["3"] == set()


def test_spanish_script_uses_spanish_names():
    found = names(ES)
    assert found["1"] == {
        ("extras", "Multitud"), ("extras", "Clientes"), ("props", "Botella"),
        ("sfx", "Lluvia"), ("sound", "Llaman a la puerta"),
    }
    assert found["2"] == {("makeup", "Sangre"), ("vehicles", "Coche de policía"), ("sound", "Sirena")}


def test_suggestions_are_marked_and_give_way_to_hand_edits_and_ai():
    sheet = load_or_carry(EN, suggest=True)
    assert all(e.source == "auto" for items in sheet.scenes.values() for e in items)
    assert load_sheet(EN) == sheet  # saved, so it is worked out once

    # Removing a suggestion is remembered, keeping one leaves it a suggestion.
    kept = [{"category": e.category, "name": e.name, "notes": e.notes} for e in sheet.for_scene("2") if e.name != "Siren"]
    update_scene(sheet, "2", kept)
    assert sheet.dismissed == {"2": ["sound|siren"]}
    assert {e.source for e in sheet.for_scene("2")} == {"auto"}

    from slugline.elements import Element, merge_extraction

    merged = merge_extraction(sheet, {"2": [Element("vehicles", "Police car", "", "ai"), Element("sound", "Siren", "", "ai")]}, "m")
    assert [(e.name, e.source) for e in merged.for_scene("2")] == [("Police car", "ai")]  # Siren stays dismissed


def test_without_suggest_nothing_is_made_up():
    assert load_or_carry(EN) is None
    assert load_or_carry("INT. EMPTY ROOM - DAY\n\nSilence.\n", suggest=True) is None


def test_ambiguous_words_are_not_guessed():
    from slugline import parse
    from slugline.keywords import suggest

    found = suggest(parse("EXT. STREET - NIGHT\n\nSelina, in her cat suit, starts her bike. Her cats watch.\n"))
    names = {e.name for e in found["1"]}
    assert names == {"Catsuit", "Bike", "Cat"}
