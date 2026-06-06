"""Iter_14: Regression smoke for routes/care.py extraction.

Every endpoint moved from server.py to routes/care.py is exercised here.
Response shapes are NOT supposed to change post-refactor.
"""
import pytest
import requests

from ._care_helpers import API as BASE_API
from ._test_creds import ADMIN

# NOTE: the 3 horse-endpoint tests below (`test_horses_requires_auth`,
# `test_list_horses`, `test_create_get_patch_horse`) are *legacy placement* —
# horse-profile CRUD was extracted to routes/horses.py in Phase 3C. They are
# left here (covered by test_horses_routes.py too) and documented rather than
# moved, to avoid churn. New horse tests belong in test_horses_routes.py.
BASE_URL = BASE_API[:-4] if BASE_API.endswith("/api") else BASE_API


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------- Auth gate ----------

def test_horses_requires_auth():
    r = requests.get(f"{BASE_URL}/api/horses", timeout=15)
    assert r.status_code in (401, 403), r.status_code


# ---------- Horses ----------

def test_list_horses(h):
    r = requests.get(f"{BASE_URL}/api/horses", headers=h, timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_get_patch_horse(h):
    payload = {"name": "TEST_Horse_iter14", "breed": "Test", "age": 5, "wellness_score": 70}
    r = requests.post(f"{BASE_URL}/api/horses", headers=h, json=payload, timeout=15)
    assert r.status_code == 200, r.text
    horse = r.json()
    assert horse["name"] == "TEST_Horse_iter14"
    assert "id" in horse
    hid = horse["id"]

    # GET
    g = requests.get(f"{BASE_URL}/api/horses/{hid}", headers=h, timeout=15)
    assert g.status_code == 200
    assert g.json()["id"] == hid

    # PATCH
    p = requests.patch(f"{BASE_URL}/api/horses/{hid}", headers=h, json={"color": "bay"}, timeout=15)
    assert p.status_code == 200
    assert p.json().get("color") == "bay"

    # 404
    nf = requests.get(f"{BASE_URL}/api/horses/does-not-exist", headers=h, timeout=15)
    assert nf.status_code == 404


# ---------- Owners ----------

def test_owners(h):
    r = requests.get(f"{BASE_URL}/api/owners", headers=h, timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    c = requests.post(f"{BASE_URL}/api/owners", headers=h, json={
        "full_name": "TEST_Owner_iter14", "email": "test_iter14@example.com"
    }, timeout=15)
    assert c.status_code == 200
    assert c.json()["full_name"] == "TEST_Owner_iter14"


# ---------- Riders ----------

def test_riders(h):
    r = requests.get(f"{BASE_URL}/api/riders", headers=h, timeout=15)
    assert r.status_code == 200
    c = requests.post(f"{BASE_URL}/api/riders", headers=h, json={
        "full_name": "TEST_Rider_iter14", "skill_level": "intermediate"
    }, timeout=15)
    assert c.status_code == 200
    assert c.json()["skill_level"] == "intermediate"


# ---------- Medications + Med-Logs ----------

def test_medications_and_logs(h):
    # need a horse
    hs = requests.get(f"{BASE_URL}/api/horses", headers=h, timeout=15).json()
    assert hs, "no horses seeded"
    hid = hs[0]["id"]

    r = requests.get(f"{BASE_URL}/api/medications", headers=h, timeout=15)
    assert r.status_code == 200
    rq = requests.get(f"{BASE_URL}/api/medications?horse_id={hid}", headers=h, timeout=15)
    assert rq.status_code == 200

    c = requests.post(f"{BASE_URL}/api/medications", headers=h, json={
        "horse_id": hid, "name": "TEST_Bute", "dosage": "1g", "frequency": "daily"
    }, timeout=15)
    assert c.status_code == 200, c.text
    med = c.json()
    assert med["name"] == "TEST_Bute"

    ml = requests.get(f"{BASE_URL}/api/medication-logs", headers=h, timeout=15)
    assert ml.status_code == 200

    mlc = requests.post(f"{BASE_URL}/api/medication-logs", headers=h, json={
        "medication_id": med["id"], "scheduled_time": "2026-01-15T08:00:00",
        "status": "given", "notes": "ok"
    }, timeout=15)
    assert mlc.status_code == 200
    assert mlc.json()["status"] == "given"


# ---------- Feed tasks ----------

def test_feed_tasks(h):
    r = requests.get(f"{BASE_URL}/api/feed-tasks", headers=h, timeout=15)
    assert r.status_code == 200
    r2 = requests.get(f"{BASE_URL}/api/feed-tasks?date_str=2026-01-15", headers=h, timeout=15)
    assert r2.status_code == 200


# ---------- Vet records ----------

def test_vet_records(h):
    hs = requests.get(f"{BASE_URL}/api/horses", headers=h, timeout=15).json()
    hid = hs[0]["id"]
    r = requests.get(f"{BASE_URL}/api/vet-records", headers=h, timeout=15)
    assert r.status_code == 200
    rq = requests.get(f"{BASE_URL}/api/vet-records?horse_id={hid}", headers=h, timeout=15)
    assert rq.status_code == 200
    c = requests.post(f"{BASE_URL}/api/vet-records", headers=h, json={
        "horse_id": hid, "type": "exam", "title": "TEST_Annual", "date": "2026-01-15"
    }, timeout=15)
    assert c.status_code == 200
    assert c.json()["title"] == "TEST_Annual"


# ---------- Farrier history ----------

def test_farrier_history(h):
    r = requests.get(f"{BASE_URL}/api/farrier-history", headers=h, timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------- Injuries ----------

def test_injuries(h):
    hs = requests.get(f"{BASE_URL}/api/horses", headers=h, timeout=15).json()
    hid = hs[0]["id"]
    r = requests.get(f"{BASE_URL}/api/injuries", headers=h, timeout=15)
    assert r.status_code == 200
    c = requests.post(f"{BASE_URL}/api/injuries", headers=h, json={
        "horse_id": hid, "title": "TEST_Bruise", "severity": "mild"
    }, timeout=15)
    assert c.status_code == 200
    assert c.json()["title"] == "TEST_Bruise"


# ---------- Wellness (with wellness_score bump) ----------

def test_wellness_bumps_horse_score(h):
    hs = requests.get(f"{BASE_URL}/api/horses", headers=h, timeout=15).json()
    hid = hs[0]["id"]

    r = requests.get(f"{BASE_URL}/api/wellness", headers=h, timeout=15)
    assert r.status_code == 200

    # All-5s → avg*5 = (5+5+5+5)*5 = 100, expect horse.wellness_score == 100
    c = requests.post(f"{BASE_URL}/api/wellness", headers=h, json={
        "horse_id": hid, "appetite": 5, "water_intake": 5, "energy": 5,
        "body_condition": 5.0, "coat_quality": 5, "status": "normal"
    }, timeout=15)
    assert c.status_code == 200

    g = requests.get(f"{BASE_URL}/api/horses/{hid}", headers=h, timeout=15)
    assert g.status_code == 200
    assert g.json()["wellness_score"] == 100, g.json().get("wellness_score")
