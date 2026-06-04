"""Phase 4B-2 — care domain barn scoping (live integration).

Proves per-barn isolation for routes/care.py:
- other-barn docs are excluded from every care list read;
- POST create paths stamp barn_id="primary";
- a cross-barn feed-task complete returns 404 and does not mutate the task;
- POST /wellness for an other-barn horse_id does not mutate that horse's score.
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
# NOTE: vet_records and farrier_history are intentionally EXCLUDED here —
# their reads are not barn-scoped until 4B-7 (task_engine writes those rows
# without barn_id; see routes/care.py notes). Read-exclusion tests for them
# will be added in 4B-7.
LIST_CASES = [
    ("/owners", "owners", {"full_name": "Ghost Owner"}),
    ("/riders", "riders", {"full_name": "Ghost Rider"}),
    ("/medications", "medications", {"horse_id": "h", "name": "Bute", "dosage": "1g", "frequency": "daily"}),
    ("/medication-logs", "medication_logs", {"medication_id": "m", "scheduled_time": "2026-01-01T08:00:00", "status": "given"}),
    ("/feed-tasks", "feed_tasks", {"meal": "AM", "ration": "hay", "completed": False}),
    ("/injuries", "injuries", {"horse_id": "h", "title": "Strain"}),
    ("/wellness", "wellness", {"horse_id": "h", "appetite": 5}),
]

# (create endpoint, payload, collection)
POST_CASES = [
    ("/owners", {"full_name": "CareOwner"}, "owners"),
    ("/riders", {"full_name": "CareRider"}, "riders"),
    ("/medications", {"horse_id": "hX", "name": "Bute", "dosage": "1g", "frequency": "daily"}, "medications"),
    ("/medication-logs", {"medication_id": "mX", "scheduled_time": "2026-01-01T08:00:00", "status": "given"}, "medication_logs"),
    ("/vet-records", {"horse_id": "hX", "type": "exam", "title": "Checkup", "date": "2026-01-01"}, "vet_records"),
    ("/injuries", {"horse_id": "hX", "title": "Strain"}, "injuries"),
    ("/wellness", {"horse_id": "hX", "appetite": 5, "water_intake": 5, "energy": 5, "coat_quality": 5}, "wellness"),
]


@pytest.mark.parametrize("endpoint,collection,fields", LIST_CASES)
def test_other_barn_doc_excluded_from_care_list(endpoint, collection, fields):
    db = _mongo()
    H = _admin_headers()
    doc_id = "other_" + uuid.uuid4().hex
    db[collection].insert_one({"id": doc_id, "barn_id": "other", "created_at": _iso(), **fields})
    try:
        r = requests.get(f"{API}{endpoint}", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        ids = [d.get("id") for d in r.json()]
        assert doc_id not in ids, f"other-barn doc leaked into {endpoint}"
    finally:
        db[collection].delete_many({"id": doc_id})


@pytest.mark.parametrize("endpoint,payload,collection", POST_CASES)
def test_care_create_stamps_primary_barn(endpoint, payload, collection):
    db = _mongo()
    H = _admin_headers()
    r = requests.post(f"{API}{endpoint}", headers=H, json=payload, timeout=30)
    assert r.status_code == 200, r.text
    doc = r.json()
    try:
        assert doc.get("barn_id") == "primary", doc
    finally:
        db[collection].delete_many({"id": doc.get("id")})


def test_feed_task_complete_other_barn_returns_404_and_no_mutation():
    db = _mongo()
    H = _admin_headers()
    tid = "otherfeed_" + uuid.uuid4().hex
    db.feed_tasks.insert_one({
        "id": tid, "barn_id": "other", "meal": "AM", "ration": "hay",
        "completed": False, "created_at": _iso(),
    })
    try:
        r = requests.post(f"{API}/feed-tasks/{tid}/complete", headers=H, timeout=30)
        assert r.status_code == 404, r.text
        doc = db.feed_tasks.find_one({"id": tid})
        assert doc["completed"] is False
        assert "completed_at" not in doc
    finally:
        db.feed_tasks.delete_many({"id": tid})


def test_wellness_post_does_not_mutate_other_barn_horse_score():
    db = _mongo()
    H = _admin_headers()
    hid = "otherhorse_" + uuid.uuid4().hex
    db.horses.insert_one({
        "id": hid, "barn_id": "other", "name": "Ghost Horse",
        "wellness_score": 85, "created_at": _iso(),
    })
    created_wellness = None
    try:
        r = requests.post(f"{API}/wellness", headers=H, json={
            "horse_id": hid, "appetite": 10, "water_intake": 10, "energy": 10, "coat_quality": 10,
        }, timeout=30)
        assert r.status_code == 200, r.text
        created_wellness = r.json()
        assert created_wellness.get("barn_id") == "primary", created_wellness
        # The other-barn horse's score must be untouched.
        assert db.horses.find_one({"id": hid})["wellness_score"] == 85
    finally:
        db.horses.delete_many({"id": hid})
        if created_wellness:
            db.wellness.delete_many({"id": created_wellness.get("id")})
