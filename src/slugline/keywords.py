"""Element suggestions without AI: a production dictionary read against the action.

When a script is opened, every scene's action lines are searched for words a
department would act on (a revolver for props, horses for animals, rain for
special effects, a crowd for extras...), in English and Spanish, and for the
capitalised sound cues screenplays use ("KNOCK KNOCK", "BANG"). It is a first
pass that is right more often than not and never empty: every suggestion is
marked as such to be checked, and Claude, when there is an API key, replaces
these suggestions with a fuller reading.
"""

from __future__ import annotations

import re

from slugline.elements import CATEGORY_KEYS, Element
from slugline.parser import Action, Screenplay

# (category, the name to show, the words that mean it). Plurals are found by
# themselves (s / es); irregular forms are listed. Words that are usually
# something else ("fire" someone, a "ring" of people) are left out.
WORDS: list[tuple[str, str, str]] = [
    # props
    ("props", "Gun", "gun|handgun|pistol"),
    ("props", "Revolver", "revolver|six-shooter"),
    ("props", "Rifle", "rifle|shotgun|winchester"),
    ("props", "Knife", "knife|knives|switchblade|dagger"),
    ("props", "Sword", "sword"),
    ("props", "Phone", "phone|cellphone|cell phone|smartphone|telephone|payphone"),
    ("props", "Letter", "letter|envelope"),
    ("props", "Money", "money|cash|banknote|dollar bill|wad of bills"),
    ("props", "Wallet", "wallet|purse"),
    ("props", "Briefcase", "briefcase|suitcase|duffel bag"),
    ("props", "Cigarette", "cigarette|cigar|lighter|ashtray"),
    ("props", "Bottle", "bottle|flask"),
    ("props", "Glass", "glass of|wine glass|shot glass|tumbler"),
    ("props", "Camera", "camera|camcorder"),
    ("props", "Laptop", "laptop|computer"),
    ("props", "Notebook", "notebook|journal|diary|notepad"),
    ("props", "Newspaper", "newspaper|magazine"),
    ("props", "Keys", "keys|car keys"),
    ("props", "Rope", "rope|noose"),
    ("props", "Pills", "pills|pill bottle|medication|syringe"),
    ("props", "Badge", "badge"),
    ("props", "Handcuffs", "handcuffs"),
    ("props", "Flowers", "flowers|bouquet"),
    ("props", "Pistola", "pistola"),
    ("props", "Revólver", "revólver|revolver"),
    ("props", "Escopeta", "escopeta|rifle|fusil"),
    ("props", "Cuchillo", "cuchillo|navaja|puñal"),
    ("props", "Espada", "espada"),
    ("props", "Teléfono", "teléfono|móvil|celular"),
    ("props", "Carta", "carta|sobre cerrado|sobre de papel"),
    ("props", "Dinero", "dinero|billetes|fajo"),
    ("props", "Cartera", "cartera|monedero"),
    ("props", "Maletín", "maletín|maleta"),
    ("props", "Cigarrillo", "cigarrillo|cigarro|puro|mechero|cenicero"),
    ("props", "Botella", "botella|petaca"),
    ("props", "Vaso", "vaso|copa"),
    ("props", "Cámara", "cámara"),
    ("props", "Ordenador", "ordenador|portátil"),
    ("props", "Libreta", "libreta|cuaderno|diario"),
    ("props", "Periódico", "periódico|revista"),
    ("props", "Llaves", "llaves"),
    ("props", "Cuerda", "cuerda|soga"),
    ("props", "Pastillas", "pastillas|jeringuilla|jeringa"),
    ("props", "Esposas", "esposas"),
    # wardrobe
    ("wardrobe", "Suit", "suit|tuxedo"),
    ("wardrobe", "Uniform", "uniform"),
    ("wardrobe", "Costume", "costume"),
    ("wardrobe", "Dress", "dress|gown"),
    ("wardrobe", "Coat", "coat|overcoat|trench coat|jacket"),
    ("wardrobe", "Hat", "hat|cap|cowboy hat"),
    ("wardrobe", "Mask", "mask"),
    ("wardrobe", "Wig", "wig"),
    ("wardrobe", "Traje", "traje|esmoquin"),
    ("wardrobe", "Uniforme", "uniforme"),
    ("wardrobe", "Disfraz", "disfraz"),
    ("wardrobe", "Vestido", "vestido"),
    ("wardrobe", "Abrigo", "abrigo|chaqueta|gabardina"),
    ("wardrobe", "Sombrero", "sombrero|gorra"),
    ("wardrobe", "Máscara", "máscara|careta"),
    ("wardrobe", "Peluca", "peluca"),
    # makeup and hair
    ("makeup", "Blood", "blood|bloody|bleeding|bloodied"),
    ("makeup", "Wound", "wound|gash|cut on|bruise|bruised|black eye|scar"),
    ("makeup", "Clown makeup", "clown makeup|face paint|greasepaint"),
    ("makeup", "Makeup", "makeup|make-up"),
    ("makeup", "Sangre", "sangre|sangrando|ensangrentado|ensangrentada"),
    ("makeup", "Herida", "herida|moratón|cicatriz|corte en"),
    ("makeup", "Maquillaje", "maquillaje|maquillado|maquillada"),
    # vehicles
    ("vehicles", "Car", "car|sedan|convertible|jeep"),
    ("vehicles", "Police car", "police car|cop car|squad car|patrol car"),
    ("vehicles", "Taxi", "taxi|cab"),
    ("vehicles", "Truck", "truck|pickup|van"),
    ("vehicles", "Bus", "bus"),
    ("vehicles", "Motorcycle", "motorcycle|motorbike"),
    ("vehicles", "Bicycle", "bicycle|bike"),
    ("vehicles", "Train", "train|subway|tram"),
    ("vehicles", "Ambulance", "ambulance"),
    ("vehicles", "Wagon", "wagon|carriage|stagecoach"),
    ("vehicles", "Boat", "boat|ship|yacht"),
    ("vehicles", "Plane", "plane|airplane|helicopter"),
    ("vehicles", "Coche", "coche|automóvil|todoterreno"),
    ("vehicles", "Coche de policía", "coche patrulla|coche de policía"),
    ("vehicles", "Taxi", "taxi"),
    ("vehicles", "Furgoneta", "furgoneta|camión|camioneta"),
    ("vehicles", "Autobús", "autobús"),
    ("vehicles", "Moto", "moto|motocicleta"),
    ("vehicles", "Bicicleta", "bicicleta"),
    ("vehicles", "Tren", "tren|metro|tranvía"),
    ("vehicles", "Ambulancia", "ambulancia"),
    ("vehicles", "Carreta", "carreta|carruaje|diligencia"),
    ("vehicles", "Barco", "barco|barca|yate"),
    ("vehicles", "Avión", "avión|avioneta|helicóptero"),
    # animals
    ("animals", "Horses", "horse|pony|mare|stallion"),
    ("animals", "Dog", "dog|puppy"),
    ("animals", "Cat", "cat|kitten"),
    ("animals", "Birds", "bird|pigeon|crow"),
    ("animals", "Cattle", "cow|cattle|bull"),
    ("animals", "Caballos", "caballo|yegua|potro"),
    ("animals", "Perro", "perro|cachorro"),
    ("animals", "Gato", "gato"),
    ("animals", "Pájaros", "pájaro|paloma|cuervo"),
    ("animals", "Ganado", "vaca|ganado|toro"),
    # extras
    ("extras", "Crowd", "crowd|mob|protesters|rioters"),
    ("extras", "Passengers", "passengers|commuters"),
    ("extras", "Customers", "customers|patrons|diners|shoppers"),
    ("extras", "Audience", "audience|spectators"),
    ("extras", "Pedestrians", "pedestrians|passersby|passers-by"),
    ("extras", "Guests", "guests|partygoers"),
    ("extras", "Police officers", "cops|police officers|policemen"),
    ("extras", "Multitud", "multitud|muchedumbre|manifestantes"),
    ("extras", "Pasajeros", "pasajeros|viajeros"),
    ("extras", "Clientes", "clientes|parroquianos|comensales"),
    ("extras", "Público", "público|espectadores"),
    ("extras", "Transeúntes", "transeúntes|peatones"),
    ("extras", "Invitados", "invitados"),
    ("extras", "Policías", "policías|agentes"),
    # stunts
    ("stunts", "Fight", "fight|brawl|punches|kicks him|kicks her|tackles|beats him|beats her|struggle"),
    ("stunts", "Fall", "falls down|falls to the ground|thrown to the ground|jumps from|falls off"),
    ("stunts", "Pelea", "pelea|forcejeo|puñetazo|patada|le golpea|la golpea"),
    ("stunts", "Caída", "cae al suelo|se cae|salta desde"),
    # special effects
    ("sfx", "Gunfire", "gunshot|gunfire|shoots|fires a|fires the|shot in"),
    ("sfx", "Explosion", "explosion|explodes|blast"),
    ("sfx", "Fire", "flames|fire burns|on fire|bonfire|fireplace"),
    ("sfx", "Smoke", "smoke|fog|mist"),
    ("sfx", "Rain", "rain|raining|downpour|storm"),
    ("sfx", "Snow", "snow|snowing"),
    ("sfx", "Breakaway glass", "shatters|smashes the window|broken glass"),
    ("sfx", "Disparos", "disparo|dispara|tiroteo|balazo"),
    ("sfx", "Explosión", "explosión|explota|estalla"),
    ("sfx", "Fuego", "llamas|hoguera|chimenea|en llamas"),
    ("sfx", "Humo", "humo|niebla"),
    ("sfx", "Lluvia", "lluvia|llueve|tormenta|chaparrón"),
    ("sfx", "Nieve", "nieve|nieva"),
    # sound and music
    ("sound", "Music", "music|song plays|singing|radio plays|jukebox"),
    ("sound", "Siren", "siren"),
    ("sound", "Knock at the door", "knock|knocking"),
    ("sound", "Phone ringing", "phone rings|ringing"),
    ("sound", "Música", "música|canción|cantando|radio"),
    ("sound", "Sirena", "sirena"),
    ("sound", "Llaman a la puerta", "llaman a la puerta|golpes en la puerta"),
    # set dressing
    ("set_dressing", "Television", "television|tv set|tv"),
    ("set_dressing", "Mirror", "mirror"),
    ("set_dressing", "Poster", "poster|billboard"),
    ("set_dressing", "Piano", "piano"),
    ("set_dressing", "Televisión", "televisión|tele|televisor"),
    ("set_dressing", "Espejo", "espejo"),
    ("set_dressing", "Póster", "póster|cartel|valla publicitaria"),
]

# Capitalised sound cues, the screenplay convention: KNOCK KNOCK, BANG.
SOUND_CUES = {
    "BANG", "BOOM", "KNOCK", "CRASH", "RING", "RRRING", "BEEP", "THUD", "SLAM", "CLICK", "BUZZ", "HONK",
    "SCREECH", "SMASH", "THUMP", "CLANG", "WHOOSH", "POP", "BLAM", "CRACK", "SPLASH", "DING", "TICK",
    "PUM", "BUM", "TOC", "RIIING", "CLIC", "ZAS", "CATAPUM",
}

# The same sounds named by the dictionary, so a cue and a line don't make two elements.
CUE_NAMES = {"KNOCK": "Knock at the door", "RING": "Phone ringing", "RRRING": "Phone ringing",
             "RIIING": "Phone ringing", "TOC": "Llaman a la puerta"}

LETTERS = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"

# Camera directions ("The camera PULLS BACK", "la cámara se acerca") are not a camera prop.
CAMERA_MOVES = re.compile(
    r"\b(?:the\s+)?camera\s+(?:[A-Z]{2,}[A-Z ]*|(?i:pans|pulls|pushes|moves|tracks|follows|zooms|tilts|cranes|"
    r"circles|holds|stays|finds|settles|drifts|rises|lingers))"
    r"|(?i:\b(?:la\s+)?cámara\s+(?:se\s+)?(?:acerca|aleja|sigue|gira|recorre|sube|baja|encuadra|panea|avanza|retrocede))"
)


def _pattern(words: str) -> re.Pattern[str]:
    alternatives = sorted((w.strip() for w in words.split("|")), key=len, reverse=True)
    body = "|".join(re.escape(w).replace(r"\ ", r"\s+") for w in alternatives)
    return re.compile(rf"(?<![{LETTERS}])(?:{body})(?:e?s)?(?![{LETTERS}])", re.IGNORECASE)


# Longest words first: once "police car" matches, its "car" is not counted again.
PATTERNS = sorted(
    ((category, name, _pattern(words)) for category, name, words in WORDS),
    key=lambda entry: -max(len(w) for w in entry[2].pattern.split("|")),
)
CUE = re.compile(rf"(?<![{LETTERS}])([A-ZÁÉÍÓÚÑ]{{3,}})(?:[!.]|\s+\1)?(?![{LETTERS}])")


def _language(play: Screenplay) -> str:
    """'es' or 'en', from the most common short words in the action."""
    text = " ".join(e.text.lower() for s in play.scenes for e in s.elements if isinstance(e, Action))[:20000]
    es = len(re.findall(r"\b(el|la|los|las|que|de|y|en|con|una|se)\b", text))
    en = len(re.findall(r"\b(the|and|of|to|with|a|his|her|in|at)\b", text))
    return "es" if es > en else "en"


SPANISH_NAMES = {name for _, name, words in WORDS if any(c in name + words for c in "áéíóúñ")} | {
    "Pistola", "Escopeta", "Cuchillo", "Espada", "Carta", "Dinero", "Cartera", "Botella", "Vaso", "Libreta",
    "Llaves", "Cuerda", "Pastillas", "Esposas", "Traje", "Uniforme", "Disfraz", "Vestido", "Abrigo", "Sombrero",
    "Peluca", "Sangre", "Herida", "Maquillaje", "Coche", "Furgoneta", "Moto", "Bicicleta", "Tren", "Ambulancia",
    "Carreta", "Barco", "Caballos", "Perro", "Gato", "Ganado", "Multitud", "Pasajeros", "Clientes", "Invitados",
    "Pelea", "Disparos", "Fuego", "Humo", "Lluvia", "Nieve", "Sirena", "Espejo", "Llaman a la puerta",
    "Coche de policía", "Policías", "Transeúntes", "Público",
}


def suggest(play: Screenplay) -> dict[str, list[Element]]:
    """Suggested elements for every scene, keyed by scene number, from the action lines only."""
    spanish = _language(play) == "es"
    patterns = [(c, n, p) for c, n, p in PATTERNS if (n in SPANISH_NAMES) == spanish or n == "Taxi"]
    found: dict[str, list[Element]] = {}
    for scene in play.scenes:
        action = CAMERA_MOVES.sub(" ", "\n".join(e.text for e in scene.elements if isinstance(e, Action)))
        items: dict[str, Element] = {}
        for category, name, pattern in patterns:
            if pattern.search(action):
                items.setdefault(f"{category}|{name}", Element(category, name, "", "auto"))
                action = pattern.sub(lambda m: " " * len(m.group(0)), action)
        for word in CUE.findall(action):
            if word in SOUND_CUES:
                cue = CUE_NAMES.get(word, word.capitalize())
                key = f"sound|{cue}"
                # The words the script uses are the clearest name for a sound cue.
                items.setdefault(key, Element("sound", cue, "", "auto"))
        found[scene.number] = sorted(items.values(), key=lambda e: CATEGORY_KEYS.index(e.category))
    return found
