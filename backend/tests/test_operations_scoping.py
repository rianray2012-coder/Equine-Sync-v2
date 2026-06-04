"""Phase 4B-3 — operations domain barn scoping (live integration).

Proves per-barn isolation for routes/operations.py:
- other-barn docs are excluded from every operations list read;
- POST create paths stamp barn_id="primary";
- cross-barn service-request approve/decline return 404 without mutation;
- cross-domain name enrichment (rider/horse/trainer/user) does not leak across barns.
"""
import os
import pathlib
import uuid
from datetime import datetime, timezone

import pymongo
import pytest
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


# (list endpoint, collection, minimal extra fields for the other-barn doc)
LIST_CASES = [
    ("/lessons", "lessons", {"start_time": "2026-01-01T10:00:00", "rider_id": "r"}),
    ("/training", "training", {"date": "2026-01-01", "horse_id": "h"}),
    ("/messages", "messages", {"subject": "Hi", "body": "secret", "created_at": _iso()}),
    ("/service-requests", "service_requests", {"type": "farrier", "status": "pending", "created_at": _iso()}),
    ("/incidents", "incidents", {"type": "injury", "title": "X", "occurred_at": _iso()}),
]

# (create endpoint, payload, collection)
POST_CASES = [
    ("/lessons", {"rider_id": "rX", "start_time": "2026-01-01T10:00:00"}, "lessons"),
    ("/training", {"horse_id": "hX", "date": "2026-01-01"}, "training"),
    ("/messages", {"subject": "Hello", "body": "Body"}, "messages"),
    ("/service-requests", {"horse_id": "hX", "type": "farrier"}, "service_requests"),
    ("/incidents", {"type": "injury", "title": "Cut", "description": "minor", "occurred_at": "2026-01-01T10:00:00"}, "incidents"),
]


@pytest.mark.parametrize("endpoint,collection,fields", LIST_CASES)
def test_other_barn_doc_excluded_from_ops_list(endpoint, collection, fields):
    db = _mongo()
    H = _admin_headers()
    doc_id = "other_" + uuid.uuid4().hex
    db[collection].insert_one({"id": doc_id, "barn_id": "other", **fields})
    try:
        r = requests.get(f"{API}{endpoint}", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        ids = [d.get("id") for d in r.json()]
        assert doc_id not in ids, f"other-barn doc leaked into {endpoint}"
    finally:
        db[collection].delete_many({"id": doc_id})


@pytest.mark.parametrize("endpoint,payload,collection", POST_CASES)
def test_ops_create_stamps_primary_barn(endpoint, payload, collection):
    db = _mongo()
    H = _admin_headers()
    r = requests.post(f"{API}{endpoint}", headers=H, json=payload, timeout=30)
    assert r.status_code == 200, r.text
    doc = r.json()
    try:
        assert doc.get("barn_id") == "primary", doc
    finally:
        db[collection].delete_many({"id": doc.get("id")})


def _insert_other_sr(db):
    sr_id = "othersr_" + uuid.uuid4().hex
    db.service_requests.insert_one({
        "id": sr_id, "barn_id": "other", "horse_id": "h", "type": "farrier",
        "status": "pending", "created_at": _iso(),
    })
    return sr_id


def test_sr_approve_cross_barn_404_no_mutation():
    db = _mongo()
    H = _admin_headers()
    sr_id = _insert_other_sr(db)
    try:
        r = requests.post(f"{API}/service-requests/{sr_id}/approve", headers=H, timeout=30)
        assert r.status_code == 404, r.text
        assert db.service_requests.find_one({"id": sr_id})["status"] == "pending"
    finally:
        db.service_requests.delete_many({"id": sr_id})


def test_sr_decline_cross_barn_404_no_mutation():
    db = _mongo()
    H = _admin_headers()
    sr_id = _insert_other_sr(db)
    try:
        r = requests.post(f"{API}/service-requests/{sr_id}/decline", headers=H,
                          json={"reason": "no"}, timeout=30)
        assert r.status_code == 404, r.text
        assert db.service_requests.find_one({"id": sr_id})["status"] == "pending"
    finally:
        db.service_requests.delete_many({"id": sr_id})


def test_lesson_cross_barn_rider_name_not_leaked():
    db = _mongo()
    H = _admin_headers()
    rid = "otherrider_" + uuid.uuid4().hex
    db.riders.insert_one({"id": rid, "barn_id": "other", "full_name": "Ghost Rider", "created_at": _iso()})
    created = None
    try:
        r = requests.post(f"{API}/lessons", headers=H,
                          json={"rider_id": rid, "start_time": "2026-01-01T10:00:00"}, timeout=30)
        assert r.status_code == 200, r.text
        created = r.json()
        assert created.get("rider_name") is None, created
    finally:
        db.riders.delete_many({"id": rid})
        if created:
            db.lessons.delete_many({"id": created.get("id")})


def test_incident_cross_barn_horse_name_not_leaked():
    db = _mongo()
    H = _admin_headers()
    hid = "otherhorse_" + uuid.uuid4().hex
    db.horses.insert_one({"id": hid, "barn_id": "other", "name": "Ghost Horse", "created_at": _iso()})
    created = None
    try:
        r = requests.post(f"{API}/incidents", headers=H, json={
            "horse_id": hid, "type": "injury", "title": "Cut", "description": "minor",
            "occurred_at": "2026-01-01T10:00:00",
        }, timeout=30)
        assert r.status_code == 200, r.text
        created = r.json()
        assert created.get("horse_name") is None, created
    finally:
        db.horses.delete_many({"id": hid})
        if created:
            db.incidents.delete_many({"id": created.get("id")})


def test_training_cross_barn_trainer_name_not_leaked():
    db = _mongo()
    H = _admin_headers()
    uid = "otheruser_" + uuid.uuid4().hex
    db.users.insert_one({"id": uid, "barn_id": "other", "full_name": "Ghost Trainer",
                         "role": "trainer", "email": f"{uid}@other.test", "created_at": _iso()})
    created = None
    try:
        r = requests.post(f"{API}/training", headers=H, json={
            "horse_id": "hX", "trainer_id": uid, "date": "2026-01-01",
        }, timeout=30)
        assert r.status_code == 200, r.text
        created = r.json()
        assert created.get("trainer_name") is None, created
    finally:
        db.users.delete_many({"id": uid})
        if created:
            db.training.delete_many({"id": created.get("id")})
