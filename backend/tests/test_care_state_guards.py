"""Phase 6B — care record state guards (live integration).

Proves the two repeatable care mutations are safe under retries:
  * feed-task re-complete is an idempotent no-op preserving the first
    completed_by / completed_at (200, same response shape)
  * medication-log idempotency via optional client_log_id — repeat posts with
    the same (barn, client_log_id) return the same log and never duplicate;
    omitting it preserves the original insert behavior

Stays inside the care-records boundary. Strict teardown.
"""
import time
import uuid
from datetime import datetime, timezone

import requests

from ._care_helpers import API, auth_headers, mongo_db

H = auth_headers()
DB = mongo_db()
STATE = {"horse": None, "med": None, "feed": None, "logs": []}


def setup_module(module):
    horse = requests.post(f"{API}/horses", headers=H,
                          json={"name": "Guards6B", "breed": "T", "age": 6}, timeout=30).json()
    STATE["horse"] = horse["id"]
    med = requests.post(f"{API}/medications", headers=H, json={
        "horse_id": horse["id"], "name": "Bute", "dosage": "1g", "frequency": "daily"}, timeout=30).json()
    STATE["med"] = med["id"]
    fid = "guard6b_feed_" + uuid.uuid4().hex
    DB.feed_tasks.insert_one({
        "id": fid, "barn_id": "primary", "horse_id": horse["id"], "meal": "AM",
        "ration": "hay", "completed": False, "created_at": datetime.now(timezone.utc).isoformat(),
    })
    STATE["feed"] = fid


def teardown_module(module):
    if STATE["logs"]:
        DB.medication_logs.delete_many({"id": {"$in": STATE["logs"]}})
    DB.feed_tasks.delete_many({"id": STATE["feed"]})
    DB.medications.delete_many({"id": STATE["med"]})
    DB.horses.delete_many({"id": STATE["horse"]})


# --------------------------------------------------------------------------
# 6B-1 — feed-task completion idempotency
# --------------------------------------------------------------------------
def test_feed_task_recomplete_is_idempotent_noop():
    url = f"{API}/feed-tasks/{STATE['feed']}/complete"
    r1 = requests.post(url, headers=H, timeout=30)
    assert r1.status_code == 200 and r1.json()["completed"] is True
    first_by = r1.json()["completed_by"]
    first_at = r1.json()["completed_at"]
    assert first_by and first_at

    time.sleep(1.1)  # ensure a different timestamp would be visible if overwritten
    r2 = requests.post(url, headers=H, timeout=30)
    assert r2.status_code == 200
    body = r2.json()
    # same response shape; original completer + timestamp preserved (no overwrite)
    assert body["completed"] is True
    assert body["completed_by"] == first_by
    assert body["completed_at"] == first_at
    assert set(r1.json().keys()) == set(body.keys())


# --------------------------------------------------------------------------
# 6B-2 — medication-log idempotency via client_log_id
# --------------------------------------------------------------------------
def test_med_log_client_log_id_is_idempotent():
    key = "clid_" + uuid.uuid4().hex
    payload = {"medication_id": STATE["med"], "scheduled_time": "2026-03-03T08:00:00",
               "status": "given", "client_log_id": key}
    r1 = requests.post(f"{API}/medication-logs", headers=H, json=payload, timeout=30)
    assert r1.status_code == 200, r1.text
    log_id = r1.json()["id"]
    STATE["logs"].append(log_id)
    # response shape intact
    for k in ("id", "medication_id", "scheduled_time", "status", "barn_id", "client_log_id"):
        assert k in r1.json()

    # repeat with the same key (even with a different status) -> same log, no dup
    r2 = requests.post(f"{API}/medication-logs", headers=H,
                       json={**payload, "status": "missed"}, timeout=30)
    assert r2.status_code == 200 and r2.json()["id"] == log_id
    assert r2.json()["status"] == "given"  # first write wins ($setOnInsert)
    assert DB.medication_logs.count_documents({"barn_id": "primary", "client_log_id": key}) == 1


def test_med_log_without_key_inserts_normally():
    payload = {"medication_id": STATE["med"], "scheduled_time": "2026-03-04T08:00:00", "status": "given"}
    r1 = requests.post(f"{API}/medication-logs", headers=H, json=payload, timeout=30)
    r2 = requests.post(f"{API}/medication-logs", headers=H, json=payload, timeout=30)
    assert r1.status_code == 200 and r2.status_code == 200
    id1, id2 = r1.json()["id"], r2.json()["id"]
    STATE["logs"].extend([id1, id2])
    # no key -> original behavior: two distinct inserts
    assert id1 != id2
    # omitted-key shape stays as before: client_log_id absent from response AND DB
    assert "client_log_id" not in r1.json() and "client_log_id" not in r2.json()
    for doc_id in (id1, id2):
        assert "client_log_id" not in DB.medication_logs.find_one({"id": doc_id}, {"_id": 0})
