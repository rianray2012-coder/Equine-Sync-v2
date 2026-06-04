"""Phase 4B-1 — horse barn scoping (live integration).

Proves per-barn isolation for the horse CRUD endpoints:
- a horse in another barn is excluded from the primary list;
- GET/PATCH for an other-barn horse return 404 (no existence leak);
- POST /horses stamps barn_id="primary";
- PATCH cannot move a horse into another barn (barn_id mutation blocked).
"""
import os
import pathlib
import uuid
from datetime import datetime, timezone

import pymongo
import requests

from ._test_creds import ADMIN


def _read_env(key, root_index, sub):
    envf = pathlib.Path(__file__).resolve().parents[root_index] / sub
    for line in envf.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _base_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    return _read_env("REACT_APP_BACKEND_URL", 2, "frontend/.env").rstrip("/")


API = f"{_base_url()}/api"


def _mongo():
    url = os.environ.get("MONGO_URL") or _read_env("MONGO_URL", 1, ".env")
    name = os.environ.get("DB_NAME") or _read_env("DB_NAME", 1, ".env")
    return pymongo.MongoClient(url)[name]


def _admin_headers():
    r = requests.post(f"{API}/auth/login",
                      json={"email": ADMIN["email"], "password": ADMIN["password"]}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _insert_other_barn_horse(db, name="Ghost Horse"):
    hid = "otherhorse_" + uuid.uuid4().hex
    db.horses.insert_one({
        "id": hid, "name": name, "barn_id": "other",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return hid


def test_other_barn_horse_excluded_from_list():
    db = _mongo()
    H = _admin_headers()
    hid = _insert_other_barn_horse(db)
    try:
        r = requests.get(f"{API}/horses", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        ids = [h.get("id") for h in r.json()]
        assert hid not in ids, "other-barn horse leaked into primary list"
    finally:
        db.horses.delete_many({"id": hid})


def test_other_barn_horse_get_and_patch_return_404():
    db = _mongo()
    H = _admin_headers()
    hid = _insert_other_barn_horse(db)
    try:
        assert requests.get(f"{API}/horses/{hid}", headers=H, timeout=30).status_code == 404
        pr = requests.patch(f"{API}/horses/{hid}", headers=H, json={"name": "Hacked"}, timeout=30)
        assert pr.status_code == 404
        # The cross-barn doc must be untouched.
        assert db.horses.find_one({"id": hid})["name"] == "Ghost Horse"
    finally:
        db.horses.delete_many({"id": hid})


def test_create_horse_stamps_primary_barn():
    db = _mongo()
    H = _admin_headers()
    name = f"ScopeHorse_{uuid.uuid4().hex[:8]}"
    r = requests.post(f"{API}/horses", headers=H, json={"name": name}, timeout=30)
    assert r.status_code == 200, r.text
    doc = r.json()
    try:
        assert doc.get("barn_id") == "primary", doc
    finally:
        db.horses.delete_many({"id": doc["id"]})


def test_patch_cannot_move_horse_to_other_barn():
    db = _mongo()
    H = _admin_headers()
    name = f"PatchHorse_{uuid.uuid4().hex[:8]}"
    r = requests.post(f"{API}/horses", headers=H, json={"name": name}, timeout=30)
    assert r.status_code == 200, r.text
    hid = r.json()["id"]
    try:
        pr = requests.patch(f"{API}/horses/{hid}", headers=H,
                            json={"barn_id": "other", "name": name + "_upd"}, timeout=30)
        assert pr.status_code == 200, pr.text
        body = pr.json()
        # barn_id mutation ignored; legitimate field still updated.
        assert body.get("barn_id") == "primary", body
        assert body.get("name") == name + "_upd", body
        assert db.horses.find_one({"id": hid})["barn_id"] == "primary"
    finally:
        db.horses.delete_many({"id": hid})
