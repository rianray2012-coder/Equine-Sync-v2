"""Founder-Beta CRUD sprint regression.

Verifies (1) Inventory/Owners/Riders/Horses create+list flows wired to
QuickAddSheet, (2) Lessons tolerate non-existent rider_id (rider_name=null),
(3) Training tolerates missing horse (horse_name=null), (4) Incidents resolve
horse_name when horse_id given and default status='open', (5) Backend
/api/onboarding/steps still exposes all 10 steps (schedules hidden in FE only).
"""
import os
import uuid

import pytest
import requests

from ._test_creds import ADMIN

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def admin_h():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}",
            "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def horse_id(admin_h):
    r = requests.get(f"{API}/horses", headers=admin_h, timeout=20)
    assert r.status_code == 200 and r.json()
    return r.json()[0]["id"]


# ---------- Onboarding: schedules still in backend payload ----------

def test_onboarding_steps_still_has_schedules_in_backend(admin_h):
    r = requests.get(f"{API}/onboarding/steps", headers=admin_h, timeout=20)
    assert r.status_code == 200
    payload = r.json()
    steps = payload.get("steps") if isinstance(payload, dict) else payload
    ids = [s["id"] for s in steps]
    assert "schedules" in ids, "Backend MUST still expose schedules per PRD"
    assert len(ids) == 10, f"Expected 10 steps, got {len(ids)}: {ids}"


# ---------- Inventory ----------

def test_inventory_create_and_list(admin_h):
    payload = {
        "name": f"TEST_grain_{uuid.uuid4().hex[:6]}",
        "category": "feed",
        "quantity": 5,
        "unit": "bags",
        "reorder_at": 10,
    }
    c = requests.post(f"{API}/inventory", headers=admin_h, json=payload, timeout=20)
    assert c.status_code == 200, c.text
    item = c.json()
    assert item["name"] == payload["name"]
    assert item["quantity"] == 5
    assert item["reorder_at"] == 10
    assert "id" in item
    assert "_id" not in item

    g = requests.get(f"{API}/inventory", headers=admin_h, timeout=20)
    assert g.status_code == 200
    assert any(i["id"] == item["id"] for i in g.json())


# ---------- Owners ----------

def test_owners_create_and_list(admin_h):
    payload = {
        "full_name": f"TEST_owner_{uuid.uuid4().hex[:6]}",
        "email": f"test_{uuid.uuid4().hex[:6]}@x.com",
        "phone": "555-0100",
    }
    c = requests.post(f"{API}/owners", headers=admin_h, json=payload, timeout=20)
    assert c.status_code == 200, c.text
    o = c.json()
    assert o["full_name"] == payload["full_name"]
    assert "id" in o and "_id" not in o

    g = requests.get(f"{API}/owners", headers=admin_h, timeout=20)
    assert g.status_code == 200
    assert any(x["id"] == o["id"] for x in g.json())


# ---------- Riders ----------

def test_riders_create_and_list(admin_h):
    payload = {
        "full_name": f"TEST_rider_{uuid.uuid4().hex[:6]}",
        "skill_level": "intermediate",
        "goals": "TEST_goals",
        "age": 15,
    }
    c = requests.post(f"{API}/riders", headers=admin_h, json=payload, timeout=20)
    assert c.status_code == 200, c.text
    r = c.json()
    assert r["full_name"] == payload["full_name"]
    assert r["skill_level"] == "intermediate"
    assert "_id" not in r

    g = requests.get(f"{API}/riders", headers=admin_h, timeout=20)
    assert g.status_code == 200


# ---------- Horses ----------

def test_horses_create_active_status(admin_h):
    payload = {
        "name": f"TEST_horse_{uuid.uuid4().hex[:6]}",
        "breed": "TEST_breed",
        "status": "stall_rest",
        "discipline": "dressage",
    }
    c = requests.post(f"{API}/horses", headers=admin_h, json=payload, timeout=20)
    assert c.status_code == 200, c.text
    h = c.json()
    assert h["name"] == payload["name"]
    assert h["status"] == "stall_rest"
    assert "_id" not in h


# ---------- Lessons: tolerates missing rider_id ----------

def test_lessons_tolerates_missing_rider(admin_h):
    payload = {
        "rider_id": f"TEST_ghost_{uuid.uuid4().hex[:6]}",
        "start_time": "2026-04-01T10:00:00Z",
        "duration_min": 30,
        "focus": "TEST_ghost_focus",
    }
    c = requests.post(f"{API}/lessons", headers=admin_h, json=payload, timeout=20)
    assert c.status_code == 200, c.text
    body = c.json()
    # rider_name should be None (or absent) since rider does not exist
    assert body.get("rider_name") in (None, "", "Unknown"), f"rider_name={body.get('rider_name')}"
    assert body["focus"] == "TEST_ghost_focus"


# ---------- Training: tolerates missing horse_id ----------

def test_training_tolerates_missing_horse(admin_h):
    payload = {
        "horse_id": f"TEST_ghost_{uuid.uuid4().hex[:6]}",
        "date": "2026-04-01T08:00:00Z",
        "discipline": "TEST_ghost_disc",
    }
    c = requests.post(f"{API}/training", headers=admin_h, json=payload, timeout=20)
    assert c.status_code == 200, c.text
    body = c.json()
    assert body.get("horse_name") in (None, "", "Unknown")


# ---------- Incidents: resolves horse_name + default open ----------

def test_incidents_resolves_horse_name_and_open_status(admin_h, horse_id):
    payload = {
        "horse_id": horse_id,
        "type": "TEST_lameness",
        "title": "TEST_inc_title",
        "description": "TEST_desc",
        "severity": "medium",
        "occurred_at": "2026-04-02T12:00:00Z",
    }
    c = requests.post(f"{API}/incidents", headers=admin_h, json=payload, timeout=20)
    assert c.status_code == 200, c.text
    inc = c.json()
    assert inc.get("status") == "open"
    # horse_name should be resolved
    assert inc.get("horse_name"), f"horse_name missing: {inc}"
