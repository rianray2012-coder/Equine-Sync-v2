"""Phase 4B-2 — care domain barn scoping (live integration).

Proves per-barn isolation for routes/care.py:
- other-barn docs are excluded from every care list read;
- POST create paths stamp barn_id="primary";
- a cross-barn feed-task complete returns 404 and does not mutate the task;
- POST /wellness for an other-barn horse_id does not mutate that horse's score.
"""
import uuid
from datetime import datetime, timezone

import pytest
import requests

from ._care_helpers import API, auth_headers, mongo_db


def _iso():
    return datetime.now(timezone.utc).isoformat()


# (list endpoint, collection, minimal extra fields for the other-barn doc)
# NOTE: vet_records and farrier_history reads are barn-scoped as of Phase 4B-7
# (complete). They are omitted from this parametrized list only to keep these
# cases minimal — their isolation is covered by the Phase 4E isolation suite.
LIST_CASES = [
    ("/owners", "owners", {"full_name": "Ghost Owner"}),
    ("/riders", "riders", {"full_name": "Ghost Rider"}),
    ("/medications", "medications", {"horse_id": "h", "name": "Bute", "dosage": "1g", "frequency": "daily"}),
    ("/medication-logs", "medication_logs", {"medication_id": "m", "scheduled_time": "2026-01-01T08:00:00", "status": "given"}),
    ("/feed-tasks", "feed_tasks", {"meal": "AM", "ration": "hay", "completed": False}),
    ("/injuries", "injuries", {"horse_id": "h", "title": "Strain"}),
    ("/wellness", "wellness", {"horse_id": "h", "appetite": 5}),
]

# (create endpoint, payload, collection) — Phase 6A: only the no-horse-ref
# creates belong here now. Horse/medication-referencing creates require a real
# barn-resident id (see test_care_create_with_real_refs_stamps_primary below).
POST_CASES = [
    ("/owners", {"full_name": "CareOwner"}, "owners"),
    ("/riders", {"full_name": "CareRider"}, "riders"),
]


@pytest.mark.parametrize("endpoint,collection,fields", LIST_CASES)
def test_other_barn_doc_excluded_from_care_list(endpoint, collection, fields):
    db = mongo_db()
    H = auth_headers()
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
    db = mongo_db()
    H = auth_headers()
    r = requests.post(f"{API}{endpoint}", headers=H, json=payload, timeout=30)
    assert r.status_code == 200, r.text
    doc = r.json()
    try:
        assert doc.get("barn_id") == "primary", doc
    finally:
        db[collection].delete_many({"id": doc.get("id")})


def test_care_create_with_real_refs_stamps_primary():
    # Phase 6A: horse/medication-referencing creates require a real barn horse.
    # With valid ids the create still 200s and stamps barn_id=primary.
    db = mongo_db()
    H = auth_headers()
    horse = requests.post(f"{API}/horses", headers=H,
                          json={"name": "CareScoping6A", "breed": "T", "age": 4}, timeout=30).json()
    hid = horse["id"]
    med = requests.post(f"{API}/medications", headers=H, json={
        "horse_id": hid, "name": "Bute", "dosage": "1g", "frequency": "daily"}, timeout=30).json()
    cases = [
        ("/medications", {"horse_id": hid, "name": "B2", "dosage": "1g", "frequency": "daily"}, "medications"),
        ("/medication-logs", {"medication_id": med["id"], "scheduled_time": "2026-01-01T08:00:00", "status": "given"}, "medication_logs"),
        ("/vet-records", {"horse_id": hid, "type": "exam", "title": "Checkup", "date": "2026-01-01"}, "vet_records"),
        ("/injuries", {"horse_id": hid, "title": "Strain"}, "injuries"),
        ("/wellness", {"horse_id": hid, "appetite": 5, "water_intake": 5, "energy": 5, "coat_quality": 5}, "wellness"),
    ]
    created = []
    try:
        for endpoint, payload, collection in cases:
            r = requests.post(f"{API}{endpoint}", headers=H, json=payload, timeout=30)
            assert r.status_code == 200, f"{endpoint}: {r.text}"
            assert r.json().get("barn_id") == "primary", r.json()
            created.append((collection, r.json()["id"]))
    finally:
        for collection, doc_id in created:
            db[collection].delete_many({"id": doc_id})
        db.medications.delete_many({"id": med["id"]})
        db.horses.delete_many({"id": hid})


def test_feed_task_complete_other_barn_returns_404_and_no_mutation():
    db = mongo_db()
    H = auth_headers()
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


def test_wellness_post_for_other_barn_horse_404s_and_no_mutation():
    # Phase 6A: a wellness create for a foreign/absent horse_id is now rejected
    # with a generic 404 (no existence leak), writes NO wellness doc, and never
    # touches the other barn's horse score.
    db = mongo_db()
    H = auth_headers()
    hid = "otherhorse_" + uuid.uuid4().hex
    db.horses.insert_one({
        "id": hid, "barn_id": "other", "name": "Ghost Horse",
        "wellness_score": 85, "created_at": _iso(),
    })
    try:
        r = requests.post(f"{API}/wellness", headers=H, json={
            "horse_id": hid, "appetite": 10, "water_intake": 10, "energy": 10, "coat_quality": 10,
        }, timeout=30)
        assert r.status_code == 404, r.text
        assert r.json()["detail"] == "Horse not found"
        # No wellness doc was written for the foreign horse ...
        assert db.wellness.count_documents({"horse_id": hid}) == 0
        # ... and the other-barn horse's score is untouched.
        assert db.horses.find_one({"id": hid})["wellness_score"] == 85
    finally:
        db.horses.delete_many({"id": hid})
        db.wellness.delete_many({"horse_id": hid})
