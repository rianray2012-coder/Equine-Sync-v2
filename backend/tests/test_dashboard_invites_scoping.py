"""Phase 4B-6 — dashboard, invites, and analytics barn scoping (live integration).

Proves per-barn isolation for the aggregation/list surfaces touched in 4B-6:
- /dashboard/summary barn-native counts ignore other-barn docs;
- /dashboard/barn-board lists exclude other-barn rows;
- GET /invites excludes other-barn invites;
- an other-barn pending invite does not block creating a primary invite;
- cross-barn invite resend/revoke return 404 with no mutation;
- POST /events stamps barn_id="primary".

Task-engine fields (feed/meds/task_completions) are intentionally NOT asserted
here — their barn reconciliation is deferred to 4B-7.
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


def _iso():
    return datetime.now(timezone.utc).isoformat()


def _today():
    return datetime.now(timezone.utc).date().isoformat()


# --------------------------------------------------------------------------
# Dashboard summary — barn-native counts ignore other-barn docs.
# --------------------------------------------------------------------------
def test_dashboard_summary_excludes_other_barn():
    db = _mongo()
    H = _admin_headers()
    before = requests.get(f"{API}/dashboard/summary", headers=H, timeout=30).json()
    sfx = uuid.uuid4().hex
    seeded = {
        "horses": {"id": "oh_" + sfx, "barn_id": "other", "status": "active",
                   "name": "Ghost", "wellness_score": 1, "created_at": _iso()},
        "injuries": {"id": "oi_" + sfx, "barn_id": "other", "status": "active", "created_at": _iso()},
        "invoices": {"id": "ov_" + sfx, "barn_id": "other", "status": "open",
                     "total": 999.0, "due_date": "2026-02-01", "created_at": _iso()},
        "service_requests": {"id": "os_" + sfx, "barn_id": "other", "status": "pending", "created_at": _iso()},
        "incidents": {"id": "oc_" + sfx, "barn_id": "other", "status": "open", "created_at": _iso()},
        "lessons": {"id": "ol_" + sfx, "barn_id": "other",
                    "start_time": f"{_today()}T10:00:00", "created_at": _iso()},
    }
    for coll, doc in seeded.items():
        db[coll].insert_one(doc)
    try:
        after = requests.get(f"{API}/dashboard/summary", headers=H, timeout=30).json()
        for key in ["total_horses", "active_injuries", "overdue_invoices", "overdue_amount",
                    "pending_service_requests", "open_incidents", "lessons_today"]:
            assert after[key] == before[key], f"{key} changed by other-barn doc ({before[key]} -> {after[key]})"
    finally:
        for coll, doc in seeded.items():
            db[coll].delete_many({"id": doc["id"]})


def test_dashboard_barn_board_excludes_other_barn():
    db = _mongo()
    H = _admin_headers()
    sfx = uuid.uuid4().hex
    seeded = {
        "lessons": {"id": "ol_" + sfx, "barn_id": "other",
                    "start_time": f"{_today()}T10:00:00", "created_at": _iso()},
        "horses": {"id": "oh_" + sfx, "barn_id": "other", "status": "stall_rest",
                   "name": "Ghost", "created_at": _iso()},
        "incidents": {"id": "oc_" + sfx, "barn_id": "other", "status": "open",
                      "occurred_at": _iso(), "created_at": _iso()},
    }
    for coll, doc in seeded.items():
        db[coll].insert_one(doc)
    try:
        board = requests.get(f"{API}/dashboard/barn-board", headers=H, timeout=30).json()
        lesson_ids = [d.get("id") for d in board.get("lessons", [])]
        stall_ids = [d.get("id") for d in board.get("stall_rest", [])]
        urgent_ids = [d.get("id") for d in board.get("urgent", [])]
        assert seeded["lessons"]["id"] not in lesson_ids, "other-barn lesson leaked into barn-board"
        assert seeded["horses"]["id"] not in stall_ids, "other-barn stall_rest horse leaked into barn-board"
        assert seeded["incidents"]["id"] not in urgent_ids, "other-barn incident leaked into barn-board"
    finally:
        for coll, doc in seeded.items():
            db[coll].delete_many({"id": doc["id"]})


# --------------------------------------------------------------------------
# Invites — list/dup/resend/revoke barn scoping.
# --------------------------------------------------------------------------
def test_other_barn_invite_excluded_from_list():
    db = _mongo()
    H = _admin_headers()
    inv_id = "oinv_" + uuid.uuid4().hex
    db.invites.insert_one({
        "id": inv_id, "barn_id": "other", "email": f"{inv_id}@example.com",
        "role": "groom", "status": "pending", "token_hash": "x",
        "created_at": _iso(),
    })
    try:
        r = requests.get(f"{API}/invites", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        ids = [d.get("id") for d in r.json()]
        assert inv_id not in ids, "other-barn invite leaked into GET /invites"
    finally:
        db.invites.delete_many({"id": inv_id})


def test_other_barn_pending_invite_does_not_block():
    db = _mongo()
    H = _admin_headers()
    email = f"invdup_{uuid.uuid4().hex[:8]}@example.com"
    other_id = "oinv_" + uuid.uuid4().hex
    db.invites.insert_one({
        "id": other_id, "barn_id": "other", "email": email,
        "role": "groom", "status": "pending", "token_hash": "x", "created_at": _iso(),
    })
    created_id = None
    try:
        r = requests.post(f"{API}/invites", headers=H,
                          json={"email": email, "role": "groom", "full_name": "Dup Tester"}, timeout=30)
        assert r.status_code in (200, 201), r.text
        doc = r.json()
        created_id = doc.get("id")
        assert doc.get("barn_id") == "primary", doc
        assert doc.get("email") == email, doc
    finally:
        db.invites.delete_many({"id": other_id})
        if created_id:
            db.invites.delete_many({"id": created_id})


def test_other_barn_resend_404_no_mutation():
    db = _mongo()
    H = _admin_headers()
    inv_id = "oinv_" + uuid.uuid4().hex
    db.invites.insert_one({
        "id": inv_id, "barn_id": "other", "email": f"{inv_id}@example.com",
        "role": "groom", "status": "pending", "token_hash": "x",
        "sends": [], "created_at": _iso(),
    })
    try:
        r = requests.post(f"{API}/invites/{inv_id}/resend", headers=H, timeout=30)
        assert r.status_code == 404, r.text
        doc = db.invites.find_one({"id": inv_id})
        assert doc["status"] == "pending"
        assert doc.get("sends") == [], "resend mutated other-barn invite"
    finally:
        db.invites.delete_many({"id": inv_id})


def test_same_barn_resend_happy_path():
    db = _mongo()
    H = _admin_headers()
    email = f"resend_{uuid.uuid4().hex[:8]}@example.com"
    cr = requests.post(f"{API}/invites", headers=H,
                       json={"email": email, "role": "groom", "full_name": "Resend OK"}, timeout=30)
    assert cr.status_code in (200, 201), cr.text
    created = cr.json()
    inv_id = created["id"]
    try:
        assert created.get("barn_id") == "primary", created
        before_sends = len(created.get("sends") or [])
        rr = requests.post(f"{API}/invites/{inv_id}/resend", headers=H, timeout=30)
        assert rr.status_code == 200, rr.text
        out = rr.json()
        assert out["id"] == inv_id
        assert out["status"] == "pending"
        assert len(out.get("sends") or []) == before_sends + 1, "resend did not append a send entry"
    finally:
        db.invites.delete_many({"id": inv_id})



def test_other_barn_revoke_404_no_mutation():
    db = _mongo()
    H = _admin_headers()
    inv_id = "oinv_" + uuid.uuid4().hex
    db.invites.insert_one({
        "id": inv_id, "barn_id": "other", "email": f"{inv_id}@example.com",
        "role": "groom", "status": "pending", "token_hash": "x", "created_at": _iso(),
    })
    try:
        r = requests.post(f"{API}/invites/{inv_id}/revoke", headers=H, timeout=30)
        assert r.status_code == 404, r.text
        doc = db.invites.find_one({"id": inv_id})
        assert doc["status"] == "pending", "revoke mutated other-barn invite"
        assert "revoked_at" not in doc
    finally:
        db.invites.delete_many({"id": inv_id})


# --------------------------------------------------------------------------
# Analytics — POST /events stamps the caller's barn.
# --------------------------------------------------------------------------
def test_post_events_stamps_primary_barn():
    db = _mongo()
    H = _admin_headers()
    name = "test.scoping." + uuid.uuid4().hex[:8]
    r = requests.post(f"{API}/events", headers=H, json={"name": name, "props": {"k": 1}}, timeout=30)
    assert r.status_code == 200, r.text
    try:
        doc = db.events.find_one({"name": name})
        assert doc is not None, "event not recorded"
        assert doc.get("barn_id") == "primary", doc
    finally:
        db.events.delete_many({"name": name})
