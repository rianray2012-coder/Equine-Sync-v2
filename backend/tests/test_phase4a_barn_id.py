"""Phase 4A — barn_id stamping/hardening (live integration).

Covers:
- public registration -> stored user barn_id=primary AND low-privilege role (2E);
- invite creation IGNORES a client-supplied barn_id (forced to inviter's barn);
- accepting an invite yields a user with barn_id=primary;
- onboarding create paths stamp barn_id=primary at creation time.
"""
import pathlib
import uuid
from datetime import datetime, timezone, timedelta

import pymongo
import requests

from routes.invites import hash_token
from ._test_creds import ADMIN


def _read_env(key, root_index, sub):
    envf = pathlib.Path(__file__).resolve().parents[root_index] / sub
    for line in envf.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _base_url():
    import os
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    return _read_env("REACT_APP_BACKEND_URL", 2, "frontend/.env").rstrip("/")


API = f"{_base_url()}/api"


def _mongo():
    import os
    url = os.environ.get("MONGO_URL") or _read_env("MONGO_URL", 1, ".env")
    name = os.environ.get("DB_NAME") or _read_env("DB_NAME", 1, ".env")
    return pymongo.MongoClient(url)[name]


def _login(email, password):
    r = requests.post(f"{API}/auth/login",
                      json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    return r.json()["token"]


def _admin_headers():
    return {"Authorization": f"Bearer {_login(ADMIN['email'], ADMIN['password'])}"}


# ---------------- registration ----------------

def test_public_registration_gets_primary_barn_and_stays_low_privilege():
    email = f"phase4a_{uuid.uuid4().hex[:10]}@example.com"
    r = requests.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": "demo1234!",
            "full_name": "Phase 4A Tester",
            # Attempt privilege escalation — must be ignored (Security Patch 2E).
            "role": "admin",
        },
        timeout=30,
    )
    assert r.status_code == 200, r.text
    user = (r.json().get("user") or {})
    assert user.get("barn_id") == "primary", r.text
    assert user.get("role") == "horse_owner", r.text


# ---------------- invites ----------------

def test_invite_create_ignores_client_supplied_barn_id():
    H = _admin_headers()
    email = f"inv_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/invites", headers=H,
                      json={"email": email, "role": "groom", "barn_id": "other"},
                      timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["barn_id"] == "primary", r.text
    _mongo().invites.delete_many({"email": email})


def test_invite_accept_user_receives_primary_barn():
    db = _mongo()
    raw = "rawtok_" + uuid.uuid4().hex
    email = f"acc_{uuid.uuid4().hex[:8]}@example.com"
    db.invites.insert_one({
        "id": uuid.uuid4().hex,
        "email": email,
        "full_name": "Accept Tester",
        "role": "groom",
        "barn_id": "primary",  # created via the (now hardened) create flow
        "token_hash": hash_token(raw),
        "status": "pending",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sends": [],
    })
    try:
        r = requests.post(f"{API}/invites/accept",
                          json={"token": raw, "password": "demo1234!"}, timeout=30)
        assert r.status_code == 200, r.text
        user = r.json()["user"]
        assert user["barn_id"] == "primary", r.text
        db.users.delete_many({"email": email})
        db.onboarding_progress.delete_many({"user_id": user["id"]})
    finally:
        db.invites.delete_many({"email": email})
        db.users.delete_many({"email": email})


# ---------------- onboarding create paths ----------------

def test_onboarding_creates_stamp_primary_barn():
    H = _admin_headers()
    db = _mongo()
    cases = [
        ("/locations", {"type": "stall", "name": f"Stall {uuid.uuid4().hex[:6]}"}, "locations"),
        ("/feed-templates", {"meal": f"meal_{uuid.uuid4().hex[:6]}"}, "feed_templates"),
        ("/inventory", {"category": "feed", "name": f"item_{uuid.uuid4().hex[:6]}"}, "inventory"),
        ("/recurring-schedules", {"type": "turnout", "name": f"rs_{uuid.uuid4().hex[:6]}"}, "recurring_schedules"),
    ]
    created_ids = []
    try:
        for path, payload, coll in cases:
            r = requests.post(f"{API}{path}", headers=H, json=payload, timeout=30)
            assert r.status_code == 200, (path, r.text)
            doc = r.json()
            assert doc.get("barn_id") == "primary", (path, doc)
            created_ids.append((coll, doc["id"]))
    finally:
        for coll, _id in created_ids:
            db[coll].delete_many({"id": _id})


def test_onboarding_reset_creates_progress_with_primary_barn():
    # Fresh user with no onboarding_progress yet -> reset upsert must stamp barn_id.
    db = _mongo()
    email = f"reset_{uuid.uuid4().hex[:8]}@example.com"
    reg = requests.post(f"{API}/auth/register", json={
        "email": email, "password": "demo1234!", "full_name": "Reset Tester",
    }, timeout=30)
    assert reg.status_code == 200, reg.text
    data = reg.json()
    token = data.get("token")
    uid = (data.get("user") or {}).get("id")
    assert token and uid, data
    H = {"Authorization": f"Bearer {token}"}
    try:
        db.onboarding_progress.delete_many({"user_id": uid})  # ensure none exists
        r = requests.post(f"{API}/onboarding/reset", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        prog = db.onboarding_progress.find_one({"user_id": uid})
        assert prog is not None, "reset did not create onboarding_progress"
        assert prog.get("barn_id") == "primary", prog
    finally:
        db.onboarding_progress.delete_many({"user_id": uid})
        db.users.delete_many({"email": email})


def test_invite_accept_clamps_legacy_other_barn_to_primary():
    # Regression: a legacy/malformed invite with barn_id="other" must still
    # produce a user clamped to the canonical primary barn in Phase 4A.
    db = _mongo()
    raw = "rawtok_" + uuid.uuid4().hex
    email = f"legacy_{uuid.uuid4().hex[:8]}@example.com"
    db.invites.insert_one({
        "id": uuid.uuid4().hex,
        "email": email,
        "full_name": "Legacy Barn Tester",
        "role": "groom",
        "barn_id": "other",  # malformed / pre-4A invite
        "token_hash": hash_token(raw),
        "status": "pending",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sends": [],
    })
    try:
        r = requests.post(f"{API}/invites/accept",
                          json={"token": raw, "password": "demo1234!"}, timeout=30)
        assert r.status_code == 200, r.text
        user = r.json()["user"]
        assert user["barn_id"] == "primary", r.text
        db.users.delete_many({"email": email})
        db.onboarding_progress.delete_many({"user_id": user["id"]})
    finally:
        db.invites.delete_many({"email": email})
        db.users.delete_many({"email": email})


def test_csv_commit_stamps_primary_barn_horses_and_owners():
    H = _admin_headers()
    db = _mongo()
    horse_name = f"CsvHorse_{uuid.uuid4().hex[:8]}"
    owner_email = f"csvowner_{uuid.uuid4().hex[:8]}@example.com"
    try:
        rh = requests.post(f"{API}/onboarding/csv-commit", headers=H, json={
            "kind": "horses", "rows": [{"name": horse_name}],
        }, timeout=30)
        assert rh.status_code == 200, rh.text
        assert rh.json().get("created") == 1, rh.text
        horse = db.horses.find_one({"name": horse_name})
        assert horse is not None and horse.get("barn_id") == "primary", horse

        ro = requests.post(f"{API}/onboarding/csv-commit", headers=H, json={
            "kind": "owners", "rows": [{"full_name": "CSV Owner", "email": owner_email}],
        }, timeout=30)
        assert ro.status_code == 200, ro.text
        assert ro.json().get("created") == 1, ro.text
        owner = db.owners.find_one({"email": owner_email})
        assert owner is not None and owner.get("barn_id") == "primary", owner
    finally:
        db.horses.delete_many({"name": horse_name})
        db.owners.delete_many({"email": owner_email})
