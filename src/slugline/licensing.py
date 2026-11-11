"""Licences: the free trial and the paid version.

A licence is a short text the seller generates and sends to the buyer, who
pastes it in Settings. It holds who it is for, the kind of licence and its
dates, signed with the seller's private key (Ed25519). The app checks the
signature with the public key shipped in it, on the user's computer, with no
server and no account. Nobody can make a valid licence without the private
key, which stays with the seller and never goes in the repository.

Seller commands (see `slugline license --help`):

    slugline license keygen                     once: make the key pair
    slugline license issue "Name" --days 365    a licence to send a buyer

Without a licence the app is a trial: everything works, but the library
keeps a few scripts and the PDFs say "trial version".
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from slugline import settings

FREE_SCRIPTS = 2  # scripts a trial keeps in its library (the bundled example doesn't count)
KINDS = ("pro", "school", "studio", "pilot")
PREFIX = "SLUG1-"
# Where to buy, shown in Settings. Set it before building the app you sell.
PURCHASE_URL = os.environ.get("SLUGLINE_PURCHASE_URL", "")
PUBLIC_KEY_FILE = Path(__file__).with_name("license_public_key.txt")
DEFAULT_PRIVATE_KEY = Path.home() / ".slugline-seller" / "private_key.pem"


class LicenseError(ValueError):
    """A licence that can't be used; the message says why, for the user."""


@dataclass
class License:
    name: str  # who it's for: a person, a school, a production company
    kind: str  # pro, school, studio or pilot
    issued: str  # ISO date
    expires: str | None  # ISO date, or None for a licence that doesn't expire

    def expired(self, today: date | None = None) -> bool:
        return bool(self.expires) and (today or date.today()) > date.fromisoformat(self.expires)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _public_key():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        raw = _unb64(PUBLIC_KEY_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    return Ed25519PublicKey.from_public_bytes(raw)


def parse(key: str, today: date | None = None) -> License:
    """Check a licence text and return what it says. Raises LicenseError."""
    try:
        from cryptography.exceptions import InvalidSignature
    except ImportError:
        raise LicenseError("This build can't check licences (the cryptography package is missing).") from None
    text = "".join(key.split())
    if not text.startswith(PREFIX) or "." not in text:
        raise LicenseError("That is not a Slugline licence. It should start with SLUG1-.")
    payload_b64, _, signature_b64 = text[len(PREFIX):].partition(".")
    public = _public_key()
    if public is None:
        raise LicenseError("This build has no licence key to check against.")
    try:
        payload = _unb64(payload_b64)
        public.verify(_unb64(signature_b64), payload)
        data = json.loads(payload)
        found = License(name=str(data["n"]), kind=str(data["k"]), issued=str(data["i"]), expires=data.get("x"))
    except (InvalidSignature, ValueError, KeyError, TypeError):
        raise LicenseError("That licence is not valid. Check that it was copied whole.") from None
    if found.expired(today):
        raise LicenseError(f"That licence expired on {found.expires}.")
    return found


def current() -> License | None:
    """The licence saved in Settings, if it is valid today."""
    key = settings.load().get("license")
    if not key:
        return None
    try:
        return parse(key)
    except LicenseError:
        return None


def status() -> dict:
    found = current()
    return {
        "licensed": found is not None,
        "license": asdict(found) if found else None,
        "free_scripts": FREE_SCRIPTS,
        "purchase_url": PURCHASE_URL or None,
    }


def activate(key: str) -> License:
    found = parse(key)
    settings.update({"license": "".join(key.split())})
    return found


def deactivate() -> None:
    settings.update({"license": ""})


# --- seller tools -----------------------------------------------------------

def keygen(private_path: Path = DEFAULT_PRIVATE_KEY, force: bool = False) -> str:
    """Make the seller's key pair: the private key goes to `private_path`
    (readable only by its owner), the public key into the app."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    if private_path.exists() and not force:
        raise LicenseError(f"{private_path} already exists. Licences already sold depend on it; "
                           "use --force only if you really mean to replace it.")
    private = Ed25519PrivateKey.generate()
    pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
    private_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    public = _b64(private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    PUBLIC_KEY_FILE.write_text(public + "\n", encoding="utf-8")
    return public


def issue(name: str, kind: str = "pro", days: int | None = 365, private_path: Path = DEFAULT_PRIVATE_KEY,
          today: date | None = None) -> str:
    """A signed licence text for a buyer."""
    from cryptography.hazmat.primitives import serialization

    if kind not in KINDS:
        raise LicenseError(f"Unknown kind {kind!r}: use one of {', '.join(KINDS)}.")
    if not name.strip():
        raise LicenseError("A licence needs the buyer's name.")
    try:
        private = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    except FileNotFoundError:
        raise LicenseError(f"No private key at {private_path}. Run `slugline license keygen` first.") from None
    start = today or date.today()
    payload = json.dumps(
        {"n": name.strip(), "k": kind, "i": start.isoformat(),
         "x": (start + timedelta(days=days)).isoformat() if days else None},
        separators=(",", ":"), ensure_ascii=False,
    ).encode()
    return PREFIX + _b64(payload) + "." + _b64(private.sign(payload))
