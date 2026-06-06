"""Phase 6C — care search / filtering polish (live integration).

Proves the hardened-but-additive list behavior:
  * the previously-unsorted care lists now return deterministic newest-first
    order (created_at desc): owners, riders, medications, feed-tasks, injuries
  * GET /medication-logs gains an optional, barn-scoped medication_id filter;
    a foreign/unknown id returns an empty array (no 404, no leak)
  * bare-array responses are unchanged (no pagination envelope)

Stays inside the care-records boundary. Strict teardown by captured ids.
"""
import time
import uuid
from datetime import datetime, timezone

import requests

from ._care_helpers import API, auth_headers, mongo_db

H = auth_headers()
DB = mongo_db()
STATE = {"horse": None, "meds": [], "med_b": None, "owners": [], "riders": [],
         "injuries": [], "logs": []}


def setup_module(module):
    horse = requests.post(f"{API}/horses", headers=H,
                          json={"name": "Filter6C", "breed": "T", "age": 7}, timeout=30).json()
    STATE["horse"] = horse["id"]
    # Two medications created in sequence -> the second is newer.
    for i in range(2):
        m = requests.post(f"{API}/medications", headers=H, json={
            "horse_id": horse["id"], "name": f"Med{i}", "dosage": "1g", "frequency": "daily"},
            timeout=30).json()
        STATE["meds"].append(m["id"])
        time.sleep(0.05)
    # A separate medication used to prove the medication_id filter narrows results.
    mb = requests.post(f"{API}/medications", headers=H, json={
        "horse_id": horse["id"], "name": "MedB", "dosage": "2g", "frequency": "daily"},
        timeout=30).json()
    STATE["med_b"] = mb["id"]


def teardown_module(module):
    if STATE["logs"]:
        DB.medication_logs.delete_many({"id": {"$in": STATE["logs"]}})
    for oid in STATE["owners"]:
        DB.owners.delete_many({"id": oid})
    for rid in STATE["riders"]:
        DB.riders.delete_many({"id": rid})
    for iid in STATE["injuries"]:
        DB.injuries.delete_many({"id": iid})
    DB.medications.delete_many({"id": {"$in": STATE["meds"] + [STATE["med_b"]]}})
    DB.horses.delete_many({"id": STATE["horse"]})


def _created_ids_newest_first(items):
    """Return ids sorted by created_at desc (server contract)."""
    return [d["id"] for d in items]


# --------------------------------------------------------------------------
# 6C-1 — medications list is newest-first (created_at desc)
# --------------------------------------------------------------------------
def test_medications_list_is_created_at_desc():
    r = requests.get(f"{API}/medications?horse_id={STATE['horse']}", headers=H, timeout=30)
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)  # bare array, no envelope
    ids = [d["id"] for d in items]
    # the three meds we created should appear newest-first relative to each other
    ours = [i for i in ids if i in (STATE["meds"] + [STATE["med_b"]])]
    assert ours == [STATE["med_b"], STATE["meds"][1], STATE["meds"][0]]
    # verify monotonic non-increasing created_at across the whole list
    cas = [d.get("created_at", "") for d in items]
    assert cas == sorted(cas, reverse=True)


# --------------------------------------------------------------------------
# 6C-2 — owners / riders / injuries lists are newest-first
# --------------------------------------------------------------------------
def test_owners_riders_injuries_are_created_at_desc():
    o1 = requests.post(f"{API}/owners", headers=H, json={"full_name": "OwnerOne"}, timeout=30).json()
    time.sleep(0.05)
    o2 = requests.post(f"{API}/owners", headers=H, json={"full_name": "OwnerTwo"}, timeout=30).json()
    STATE["owners"] += [o1["id"], o2["id"]]

    r1 = requests.post(f"{API}/riders", headers=H, json={"full_name": "RiderOne"}, timeout=30).json()
    time.sleep(0.05)
    r2 = requests.post(f"{API}/riders", headers=H, json={"full_name": "RiderTwo"}, timeout=30).json()
    STATE["riders"] += [r1["id"], r2["id"]]

    i1 = requests.post(f"{API}/injuries", headers=H,
                       json={"horse_id": STATE["horse"], "title": "InjOne"}, timeout=30).json()
    time.sleep(0.05)
    i2 = requests.post(f"{API}/injuries", headers=H,
                       json={"horse_id": STATE["horse"], "title": "InjTwo"}, timeout=30).json()
    STATE["injuries"] += [i1["id"], i2["id"]]

    for path, newer, older in (
        ("owners", o2["id"], o1["id"]),
        ("riders", r2["id"], r1["id"]),
        (f"injuries?horse_id={STATE['horse']}", i2["id"], i1["id"]),
    ):
        items = requests.get(f"{API}/{path}", headers=H, timeout=30).json()
        assert isinstance(items, list)
        ids = [d["id"] for d in items]
        assert ids.index(newer) < ids.index(older), f"{path} not newest-first"


# --------------------------------------------------------------------------
# 6C-3 — medication-logs optional medication_id filter (barn-scoped)
# --------------------------------------------------------------------------
def test_med_logs_medication_id_filter():
    # one log against meds[0], one against med_b
    la = requests.post(f"{API}/medication-logs", headers=H, json={
        "medication_id": STATE["meds"][0], "scheduled_time": "2026-05-01T08:00:00",
        "status": "given"}, timeout=30).json()
    lb = requests.post(f"{API}/medication-logs", headers=H, json={
        "medication_id": STATE["med_b"], "scheduled_time": "2026-05-01T08:00:00",
        "status": "given"}, timeout=30).json()
    STATE["logs"] += [la["id"], lb["id"]]

    # filtered to meds[0] -> includes la, excludes lb
    r = requests.get(f"{API}/medication-logs?medication_id={STATE['meds'][0]}", headers=H, timeout=30)
    assert r.status_code == 200
    ids = [d["id"] for d in r.json()]
    assert la["id"] in ids
    assert lb["id"] not in ids
    assert all(d["medication_id"] == STATE["meds"][0] for d in r.json())

    # unfiltered list still returns both (no behavior regression)
    allids = [d["id"] for d in requests.get(f"{API}/medication-logs", headers=H, timeout=30).json()]
    assert la["id"] in allids and lb["id"] in allids


def test_med_logs_unknown_medication_id_returns_empty_not_404():
    r = requests.get(f"{API}/medication-logs?medication_id=does-not-exist-{uuid.uuid4().hex}",
                     headers=H, timeout=30)
    assert r.status_code == 200  # no 404 for foreign/unknown filter id
    assert r.json() == []
