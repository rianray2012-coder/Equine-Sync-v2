"""Phase 4B-5 — onboarding + reports barn scoping (live integration).

Proves per-barn isolation for routes/onboarding.py and routes/reports.py:
- the 5 onboarding list collections exclude other-barn rows;
- onboarding creates stamp barn_id="primary";
- a cross-barn DELETE is a silent no-op (other-barn doc survives);
- GET/PUT /barn resolve to the caller's barn (primary);
- CSV preview/commit dedup + owner-name mapping are barn-scoped (cross-barn
  rows neither flag duplicates, block imports, nor get linked);
- reports nudge-candidates + setup-health exclude other-barn onboarding rows.
"""
import os
import pathlib
import uuid
from datetime import datetime, timedelta, timezone

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


def _iso():
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# List scoping — other-barn rows excluded for all 5 onboarding collections.
# --------------------------------------------------------------------------
def _list_exclusion(coll, endpoint, extra=None):
    db = _mongo()
    H = _admin_headers()
    other_id = "other_" + uuid.uuid4().hex
    doc = {"id": other_id, "barn_id": "other", "name": "Ghost", "created_at": _iso()}
    if extra:
        doc.update(extra)
    db[coll].insert_one(doc)
    try:
        r = requests.get(f"{API}{endpoint}", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        ids = [d.get("id") for d in r.json()]
        assert other_id not in ids, f"other-barn {coll} leaked into {endpoint}"
    finally:
        db[coll].delete_many({"id": other_id})


def test_locations_other_barn_excluded():
    _list_exclusion("locations", "/locations", {"type": "stall"})


def test_feed_templates_other_barn_excluded():
    _list_exclusion("feed_templates", "/feed-templates", {"meal": "AM"})


def test_inventory_other_barn_excluded():
    _list_exclusion("inventory", "/inventory", {"category": "feed", "unit": "lbs", "quantity": 1})


def test_recurring_schedules_other_barn_excluded():
    _list_exclusion("recurring_schedules", "/recurring-schedules", {"type": "feed"})


def test_staff_invites_other_barn_excluded():
    db = _mongo()
    H = _admin_headers()
    other_id = "other_" + uuid.uuid4().hex
    db.staff_invites.insert_one({
        "id": other_id, "barn_id": "other", "email": f"{other_id}@example.com",
        "role": "groom", "status": "pending", "created_at": _iso(),
    })
    try:
        r = requests.get(f"{API}/staff-invites", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        ids = [d.get("id") for d in r.json()]
        assert other_id not in ids, "other-barn staff_invite leaked into list"
    finally:
        db.staff_invites.delete_many({"id": other_id})


def test_staff_invite_other_barn_dup_does_not_block():
    db = _mongo()
    H = _admin_headers()
    email = f"dupinvite_{uuid.uuid4().hex[:8]}@example.com"
    other_id = "other_" + uuid.uuid4().hex
    # A pending invite for the same email in ANOTHER barn must not block/leak.
    db.staff_invites.insert_one({
        "id": other_id, "barn_id": "other", "email": email,
        "role": "groom", "status": "pending", "created_at": _iso(),
    })
    created_id = None
    try:
        r = requests.post(f"{API}/staff-invites", headers=H,
                          json={"email": email, "role": "groom", "full_name": "Dup Tester"}, timeout=30)
        assert r.status_code == 200, r.text
        doc = r.json()
        created_id = doc.get("id")
        assert doc.get("barn_id") == "primary", doc
        assert doc.get("email") == email, doc
    finally:
        db.staff_invites.delete_many({"id": other_id})
        if created_id:
            db.staff_invites.delete_many({"id": created_id})


# --------------------------------------------------------------------------
# Create stamps primary; cross-barn delete is a silent no-op.
# --------------------------------------------------------------------------
def test_create_location_stamps_primary():
    db = _mongo()
    H = _admin_headers()
    r = requests.post(f"{API}/locations", headers=H,
                      json={"type": "stall", "name": "Stall Test", "capacity": 1}, timeout=30)
    assert r.status_code == 200, r.text
    doc = r.json()
    try:
        assert doc.get("barn_id") == "primary", doc
    finally:
        db.locations.delete_many({"id": doc.get("id")})


def test_cross_barn_delete_is_noop():
    db = _mongo()
    H = _admin_headers()
    other_id = "other_" + uuid.uuid4().hex
    db.locations.insert_one({
        "id": other_id, "barn_id": "other", "type": "stall", "name": "Ghost", "created_at": _iso(),
    })
    try:
        r = requests.delete(f"{API}/locations/{other_id}", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}
        # The other-barn doc must survive (silent no-op, no existence leak).
        assert db.locations.find_one({"id": other_id}) is not None, "cross-barn delete mutated other barn"
    finally:
        db.locations.delete_many({"id": other_id})


# --------------------------------------------------------------------------
# Barn settings resolve to caller's barn (primary), shape preserved.
# --------------------------------------------------------------------------
def test_barn_settings_resolve_primary():
    H = _admin_headers()
    r = requests.get(f"{API}/barn", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("id") == "primary", r.json()
    # PUT forces id=primary regardless of payload and persists.
    pr = requests.put(f"{API}/barn", headers=H, json={"name": "Scoping Test Barn"}, timeout=30)
    assert pr.status_code == 200, pr.text
    assert pr.json().get("id") == "primary", pr.json()


# --------------------------------------------------------------------------
# CSV: cross-barn dedup + owner mapping are barn-scoped.
# --------------------------------------------------------------------------
def test_csv_preview_cross_barn_horse_not_duplicate():
    db = _mongo()
    H = _admin_headers()
    name = "GhostHorse_" + uuid.uuid4().hex[:8]
    db.horses.insert_one({"id": "h_" + uuid.uuid4().hex, "barn_id": "other",
                          "name": name, "created_at": _iso()})
    try:
        csv_text = "name,breed\n" + f"{name},Hanoverian"
        r = requests.post(f"{API}/onboarding/csv-preview", headers=H,
                          json={"kind": "horses", "csv_text": csv_text}, timeout=30)
        assert r.status_code == 200, r.text
        assert name not in (r.json().get("duplicates") or []), "cross-barn horse flagged as duplicate"
    finally:
        db.horses.delete_many({"name": name})


def test_csv_commit_cross_barn_owner_not_linked_and_name_not_blocked():
    db = _mongo()
    H = _admin_headers()
    horse_name = "CsvHorse_" + uuid.uuid4().hex[:8]
    owner_name = "CsvOwner_" + uuid.uuid4().hex[:8]
    # Other-barn horse with the SAME name must not block import.
    db.horses.insert_one({"id": "h_" + uuid.uuid4().hex, "barn_id": "other",
                          "name": horse_name, "created_at": _iso()})
    # Other-barn owner must not be linkable via name mapping.
    db.owners.insert_one({"id": "o_" + uuid.uuid4().hex, "barn_id": "other",
                          "full_name": owner_name, "created_at": _iso()})
    try:
        r = requests.post(f"{API}/onboarding/csv-commit", headers=H,
                          json={"kind": "horses",
                                "rows": [{"name": horse_name, "owner": owner_name}]}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("created") == 1, body  # name not blocked by cross-barn dup
        assert body.get("skipped") == 0, body
        created = db.horses.find_one({"name": horse_name, "barn_id": "primary"})
        assert created is not None, "imported horse not stamped primary"
        assert created.get("owner_id") is None, "cross-barn owner was linked"
    finally:
        db.horses.delete_many({"name": horse_name})
        db.owners.delete_many({"full_name": owner_name})


# --------------------------------------------------------------------------
# Reports scoping — other-barn onboarding rows excluded.
# --------------------------------------------------------------------------
def test_reports_nudge_candidates_excludes_other_barn():
    db = _mongo()
    H = _admin_headers()
    uid = "TEST_otherbarn_" + uuid.uuid4().hex[:8]
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    db.users.insert_one({"id": uid, "email": f"{uid}@example.com", "full_name": "Other Barn",
                         "role": "barn_manager", "barn_id": "other", "created_at": old})
    db.onboarding_progress.insert_one({
        "user_id": uid, "completed": False, "barn_id": "other",
        "steps": {"barn": "complete"}, "current_step": "locations",
        "created_at": old, "updated_at": old,
    })
    try:
        r = requests.get(f"{API}/reports/nudge-candidates?min_days=5", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        ids = [c["user_id"] for c in r.json()]
        assert uid not in ids, "other-barn user surfaced as nudge candidate"
    finally:
        db.users.delete_one({"id": uid})
        db.onboarding_progress.delete_one({"user_id": uid})


def test_send_nudges_other_barn_user_not_updated():
    db = _mongo()
    H = _admin_headers()
    uid = "TEST_otherbarn_" + uuid.uuid4().hex[:8]
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    db.users.insert_one({"id": uid, "email": f"{uid}@example.com", "full_name": "Other Barn",
                         "role": "barn_manager", "barn_id": "other", "created_at": old})
    db.onboarding_progress.insert_one({
        "user_id": uid, "completed": False, "barn_id": "other",
        "steps": {"barn": "complete"}, "current_step": "locations",
        "created_at": old, "updated_at": old,
    })
    try:
        r = requests.post(f"{API}/admin/send-nudges", headers=H,
                          json={"min_days": 5, "cooldown_hours": 24, "user_ids": [uid]}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["candidates"] == 0, d  # other-barn row never becomes a candidate
        assert d["sent"] == 0, d
        # The other-barn progress doc must remain untouched.
        doc = db.onboarding_progress.find_one({"user_id": uid})
        assert doc is not None
        assert doc.get("last_nudged_at") is None, "other-barn last_nudged_at was set"
        assert "nudges_sent" not in doc, "other-barn nudges_sent was incremented"
    finally:
        db.users.delete_one({"id": uid})
        db.onboarding_progress.delete_one({"user_id": uid})



def test_reports_setup_health_excludes_other_barn():
    db = _mongo()
    H = _admin_headers()
    before = requests.get(f"{API}/reports/setup-health", headers=H, timeout=30).json()["total_setups"]
    uid = "TEST_otherbarn_" + uuid.uuid4().hex[:8]
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    db.onboarding_progress.insert_one({
        "user_id": uid, "completed": False, "barn_id": "other",
        "steps": {"barn": "complete"}, "current_step": "locations",
        "created_at": old, "updated_at": old,
    })
    try:
        after = requests.get(f"{API}/reports/setup-health", headers=H, timeout=30).json()["total_setups"]
        assert after == before, f"other-barn onboarding counted in setup-health ({before} -> {after})"
    finally:
        db.onboarding_progress.delete_one({"user_id": uid})
