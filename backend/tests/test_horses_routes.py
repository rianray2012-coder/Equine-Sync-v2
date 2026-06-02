"""Phase 3C — routes/horses.py extraction tests.

Covers the four horse-profile CRUD endpoints (now served by routes/horses.py)
and confirms GET /horses/{id}/timeline still responds (intentionally remains in
task_engine.py).
"""
import os
import pathlib

import requests

from ._test_creds import ADMIN


def _base_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    env = pathlib.Path(__file__).resolve().parents[2] / "frontend" / ".env"
    for line in env.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


API = f"{_base_url()}/api"


def _token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _auth():
    return {"Authorization": f"Bearer {_token()}"}


def test_horses_requires_auth():
    r = requests.get(f"{API}/horses", timeout=30)
    assert r.status_code == 401


def test_horse_create_list_get_patch_roundtrip():
    h = _auth()
    # create
    r = requests.post(f"{API}/horses", headers=h, json={
        "name": "Test Phase3C", "breed": "Arabian", "age": 5, "discipline": "Dressage",
    }, timeout=30)
    assert r.status_code == 200, r.text
    created = r.json()
    hid = created["id"]
    assert created["name"] == "Test Phase3C"
    assert created["breed"] == "Arabian"
    assert "created_at" in created
    # list includes it
    lst = requests.get(f"{API}/horses", headers=h, timeout=30)
    assert lst.status_code == 200
    assert any(x["id"] == hid for x in lst.json())
    # get by id
    got = requests.get(f"{API}/horses/{hid}", headers=h, timeout=30)
    assert got.status_code == 200
    assert got.json()["age"] == 5
    # patch (free-form body, no new validation introduced)
    patched = requests.patch(f"{API}/horses/{hid}", headers=h, json={"age": 6, "stall": "B12"}, timeout=30)
    assert patched.status_code == 200
    body = patched.json()
    assert body["age"] == 6
    assert body["stall"] == "B12"


def test_get_unknown_horse_returns_404():
    h = _auth()
    r = requests.get(f"{API}/horses/does-not-exist-xyz", headers=h, timeout=30)
    assert r.status_code == 404


def test_horse_timeline_still_served():
    # Intentional exception: timeline remains in task_engine.py.
    h = _auth()
    r = requests.post(f"{API}/horses", headers=h, json={"name": "Timeline Probe"}, timeout=30)
    assert r.status_code == 200
    hid = r.json()["id"]
    t = requests.get(f"{API}/horses/{hid}/timeline", headers=h, timeout=30)
    assert t.status_code == 200
    assert isinstance(t.json(), (list, dict))
