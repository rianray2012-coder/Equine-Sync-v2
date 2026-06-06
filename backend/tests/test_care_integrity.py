"""Phase 6A — care input integrity / cross-barn validation (live integration).

Proves every care create validates its referenced id against the caller's barn:
  * valid barn horse/medication -> 200 (+ barn_id=primary)
  * nonexistent id            -> 404 (generic, no existence leak)
  * other-barn id             -> 404 (same generic message)
  * owners.horses[] entries are validated too

Stays inside the care-records boundary (routes/care.py). Strict teardown.
"""
import uuid
from datetime import datetime, timezone

import requests

from ._care_helpers import API, auth_headers, mongo_db

H = auth_headers()
DB = mongo_db()


def _post(endpoint, payload):
    return requests.post(f"{API}{endpoint}", headers=H, json=payload, timeout=30)


# --------------------------------------------------------------------------
# Fixtures: a real primary horse + medication, and a seeded other-barn horse
# --------------------------------------------------------------------------
STATE = {"horse": None, "med": None, "other_horse": None, "created": []}


def setup_module(module):
    horse = _post("/horses", {"name": "Integrity6A", "breed": "T", "age": 5}).json()
    STATE["horse"] = horse["id"]
    med = _post("/medications", {"horse_id": horse["id"], "name": "Bute",
                                 "dosage": "1g", "frequency": "daily"}).json()
    STATE["med"] = med["id"]
    other = "otherbarn_horse_" + uuid.uuid4().hex
    DB.horses.insert_one({"id": other, "barn_id": "other", "name": "Foreign",
                          "created_at": datetime.now(timezone.utc).isoformat()})
    STATE["other_horse"] = other


def teardown_module(module):
    for collection, doc_id in STATE["created"]:
        DB[collection].delete_many({"id": doc_id})
    DB.medications.delete_many({"id": STATE["med"]})
    DB.horses.delete_many({"id": {"$in": [STATE["horse"], STATE["other_horse"]]}})


def _track(collection, resp):
    STATE["created"].append((collection, resp.json()["id"]))
    return resp


# --------------------------------------------------------------------------
# Valid creates still succeed (+ barn stamped)
# --------------------------------------------------------------------------
def test_valid_horse_ref_creates_succeed():
    hid = STATE["horse"]
    cases = [
        ("/medications", {"horse_id": hid, "name": "B2", "dosage": "2g", "frequency": "bid"}, "medications"),
        ("/vet-records", {"horse_id": hid, "type": "exam", "title": "Checkup", "date": "2026-02-02"}, "vet_records"),
        ("/injuries", {"horse_id": hid, "title": "Strain"}, "injuries"),
        ("/wellness", {"horse_id": hid, "appetite": 5, "water_intake": 5, "energy": 5, "coat_quality": 5}, "wellness"),
    ]
    for endpoint, payload, collection in cases:
        r = _post(endpoint, payload)
        assert r.status_code == 200, f"{endpoint}: {r.text}"
        assert r.json()["barn_id"] == "primary"
        _track(collection, r)


def test_valid_medication_log_succeeds():
    r = _post("/medication-logs",
              {"medication_id": STATE["med"], "scheduled_time": "2026-02-02T08:00:00", "status": "given"})
    assert r.status_code == 200, r.text
    _track("medication_logs", r)


def test_valid_owner_with_horses_succeeds():
    r = _post("/owners", {"full_name": "Owner With Horse", "horses": [STATE["horse"]]})
    assert r.status_code == 200, r.text
    _track("owners", r)


# --------------------------------------------------------------------------
# Nonexistent ids -> 404 (generic)
# --------------------------------------------------------------------------
def test_nonexistent_horse_ref_404():
    ghost = "nope_" + uuid.uuid4().hex
    for endpoint, payload in [
        ("/medications", {"horse_id": ghost, "name": "X", "dosage": "1g", "frequency": "daily"}),
        ("/vet-records", {"horse_id": ghost, "type": "exam", "title": "X", "date": "2026-01-01"}),
        ("/injuries", {"horse_id": ghost, "title": "X"}),
        ("/wellness", {"horse_id": ghost, "appetite": 5, "water_intake": 5, "energy": 5, "coat_quality": 5}),
    ]:
        r = _post(endpoint, payload)
        assert r.status_code == 404 and r.json()["detail"] == "Horse not found", f"{endpoint}: {r.text}"


def test_nonexistent_medication_ref_404():
    r = _post("/medication-logs",
              {"medication_id": "nope_" + uuid.uuid4().hex, "scheduled_time": "2026-01-01T08:00:00", "status": "given"})
    assert r.status_code == 404 and r.json()["detail"] == "Medication not found"


def test_nonexistent_owner_horse_ref_404():
    r = _post("/owners", {"full_name": "Bad Owner", "horses": ["nope_" + uuid.uuid4().hex]})
    assert r.status_code == 404 and r.json()["detail"] == "Horse not found"


# --------------------------------------------------------------------------
# Other-barn ids -> 404 (same generic message, no existence leak)
# --------------------------------------------------------------------------
def test_other_barn_horse_ref_404_no_leak():
    other = STATE["other_horse"]
    r = _post("/medications", {"horse_id": other, "name": "X", "dosage": "1g", "frequency": "daily"})
    assert r.status_code == 404 and r.json()["detail"] == "Horse not found"
    # No record written for the foreign horse.
    assert DB.medications.count_documents({"horse_id": other}) == 0


def test_other_barn_medication_ref_404():
    other_med = "otherbarn_med_" + uuid.uuid4().hex
    DB.medications.insert_one({"id": other_med, "barn_id": "other", "horse_id": "x",
                               "name": "Foreign Med", "created_at": datetime.now(timezone.utc).isoformat()})
    try:
        r = _post("/medication-logs",
                  {"medication_id": other_med, "scheduled_time": "2026-01-01T08:00:00", "status": "given"})
        assert r.status_code == 404 and r.json()["detail"] == "Medication not found"
        assert DB.medication_logs.count_documents({"medication_id": other_med}) == 0
    finally:
        DB.medications.delete_many({"id": other_med})
