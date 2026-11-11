"""Licences and the trial version."""

import io
from datetime import date

import pytest

pytest.importorskip("cryptography")

from slugline import licensing  # noqa: E402


@pytest.fixture
def seller(tmp_path, monkeypatch):
    """A throwaway key pair, so the tests never touch the real seller key or the app's public key."""
    monkeypatch.setattr(licensing, "PUBLIC_KEY_FILE", tmp_path / "public.txt")
    private = tmp_path / "seller" / "private_key.pem"
    licensing.keygen(private)
    return private


def test_issue_and_check(seller):
    key = licensing.issue("Escuela de Cine", "school", 365, seller, today=date(2027, 1, 10))
    assert key.startswith("SLUG1-")
    found = licensing.parse(key, today=date(2027, 6, 1))
    assert (found.name, found.kind, found.issued, found.expires) == ("Escuela de Cine", "school", "2027-01-10", "2028-01-10")
    # Pasted with line breaks or spaces, it still works.
    assert licensing.parse(key[:30] + "\n  " + key[30:], today=date(2027, 6, 1)) == found
    with pytest.raises(licensing.LicenseError, match="expired on 2028-01-10"):
        licensing.parse(key, today=date(2028, 1, 11))
    forever = licensing.issue("Ana", "pro", None, seller)
    assert licensing.parse(forever, today=date(2099, 1, 1)).expires is None


def test_forged_and_broken_licences_are_refused(seller, tmp_path):
    import base64
    import json

    key = licensing.issue("Ana", "pro", 30, seller)
    body, signature = key[len("SLUG1-"):].split(".")
    data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    data["x"] = "2099-12-31"  # a buyer extending their own licence
    forged_body = base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).rstrip(b"=").decode()
    for bad, message in [
        (f"SLUG1-{forged_body}.{signature}", "not valid"),
        (key[: len(key) // 2], "not valid"),
        ("hello", "not a Slugline licence"),
    ]:
        with pytest.raises(licensing.LicenseError, match=message):
            licensing.parse(bad)
    # A licence signed with someone else's key is refused too.
    other = tmp_path / "other.pem"
    original_public = licensing.PUBLIC_KEY_FILE.read_text()
    licensing.keygen(other)
    stranger = licensing.issue("Pirate", "pro", 30, other)
    licensing.PUBLIC_KEY_FILE.write_text(original_public)
    with pytest.raises(licensing.LicenseError, match="not valid"):
        licensing.parse(stranger)


def test_seller_tools_protect_the_key(seller):
    with pytest.raises(licensing.LicenseError, match="already exists"):
        licensing.keygen(seller)
    assert (seller.stat().st_mode & 0o777) == 0o600
    with pytest.raises(licensing.LicenseError, match="Unknown kind"):
        licensing.issue("Ana", "free-for-all", 30, seller)
    with pytest.raises(licensing.LicenseError, match="No private key"):
        licensing.issue("Ana", "pro", 30, seller.with_name("missing.pem"))


def test_activate_and_status(seller):
    assert licensing.status()["licensed"] is False and licensing.current() is None
    licensing.activate(licensing.issue("Ana Gil", "pro", 365, seller))
    status = licensing.status()
    assert status["licensed"] is True and status["license"]["name"] == "Ana Gil"
    licensing.deactivate()
    assert licensing.current() is None
    with pytest.raises(licensing.LicenseError):
        licensing.activate("SLUG1-nope.nope")
    assert licensing.current() is None  # a bad key is never saved


def test_cli(seller, capsys):
    from slugline.cli import main

    assert main(["license", "issue", "Productora Norte", "--kind", "studio", "--days", "0", "--key", str(seller)]) == 0
    key = capsys.readouterr().out.strip()
    assert main(["license", "check", key]) == 0
    out = capsys.readouterr().out
    assert "studio licence for Productora Norte" in out and "no expiry" in out
    assert main(["license", "check", "SLUG1-x.y"]) == 1
    assert main(["license", "activate", key]) == 0
    assert licensing.current().name == "Productora Norte"


# --- the trial in the app -------------------------------------------------------

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from slugline.server import create_app  # noqa: E402


def script(title: str) -> bytes:
    return f"Title: {title}\n\nINT. ROOM - DAY\n\nANNA\nHello.\n".encode()


def test_trial_keeps_two_scripts_and_a_licence_lifts_the_limit(seller):
    client = TestClient(create_app(), headers={"x-slugline": "1"})
    assert client.post("/api/examples/johns-boys").status_code == 200  # the example doesn't count
    for title in ("One", "Two"):
        assert client.post("/api/scripts", params={"filename": f"{title}.fountain"}, content=script(title)).status_code == 200
    status = client.get("/api/status").json()["license"]
    assert (status["licensed"], status["scripts"], status["free_scripts"]) == (False, 2, 2)

    third = client.post("/api/scripts", params={"filename": "three.fountain"}, content=script("Three"))
    assert third.status_code == 402 and "trial keeps 2 scripts" in third.json()["detail"]
    # Opening one already in the library is fine.
    assert client.post("/api/scripts", params={"filename": "one.fountain"}, content=script("One")).status_code == 200

    bad = client.put("/api/license", json={"key": "SLUG1-x.y"})
    assert bad.status_code == 422
    ok = client.put("/api/license", json={"key": licensing.issue("Ana", "pro", 365, seller)}).json()
    assert ok["licensed"] is True and ok["license"]["name"] == "Ana"
    assert client.post("/api/scripts", params={"filename": "three.fountain"}, content=script("Three")).status_code == 200

    assert client.delete("/api/license").json()["licensed"] is False


def test_trial_pdfs_carry_the_mark(seller):
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")
    client = TestClient(create_app(), headers={"x-slugline": "1"})
    sid = client.post("/api/examples/johns-boys").json()["id"]

    def text(lang="en"):
        pdf = client.get(f"/api/scripts/{sid}/export/breakdown-sheets.pdf", params={"lang": lang}).content
        return pypdf.PdfReader(io.BytesIO(pdf)).pages[0].extract_text()

    assert "TRIAL VERSION" in text() and "trial version of Slugline" in text()
    assert "VERSIÓN DE PRUEBA" in text("es")
    client.put("/api/license", json={"key": licensing.issue("Ana", "pro", 365, seller)})
    assert "TRIAL" not in text() and "trial" not in text()
