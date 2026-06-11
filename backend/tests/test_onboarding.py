"""EquineSync Onboarding/Barn Setup backend tests."""
import requests
import pytest

from ._api_helpers import API, BASE as BASE_URL
from ._test_creds import ADMIN

EXPECTED_STEP_IDS = {
    "barn", "locations", "owners", "horses", "riders",
    "feed_templates", "inventory", "staff", "schedules", "review",
}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


# ---- Steps ----
def test_get_steps(H):
    r = requests.get(f"{API}/onboarding/steps", headers=H, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "steps" in data and isinstance(data["steps"], list)
    assert len(data["steps"]) == 10
    ids = {s["id"] for s in data["steps"]}
    assert ids == EXPECTED_STEP_IDS
    for s in data["steps"]:
        assert "label" in s and "required" in s


# ---- Progress GET creates ----
def test_progress_get_creates(H):
    r = requests.get(f"{API}/onboarding/progress", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert set(d["steps"].keys()) == EXPECTED_STEP_IDS
    assert d["current_step"] in EXPECTED_STEP_IDS
    assert "percent" in d
    assert d["completed"] in (False, True)
    assert "_id" not in d


# ---- Progress PATCH ----
def test_progress_patch_updates_and_percent(H):
    # Mark barn step complete
    r = requests.patch(f"{API}/onboarding/progress", headers=H,
                       json={"step_id": "barn", "status": "complete",
                             "current_step": "locations",
                             "data": {"barn_draft": {"name": "TEST_ Barn"}}}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["steps"]["barn"] == "complete"
    assert d["current_step"] == "locations"
    assert d["data"].get("barn_draft", {}).get("name") == "TEST_ Barn"
    # percent should be at least 10%
    assert d["percent"] >= 10


def test_progress_complete(H):
    r = requests.post(f"{API}/onboarding/complete", headers=H, timeout=30)
    assert r.status_code == 200
    assert r.json().get("ok") is True
    # Verify via GET
    g = requests.get(f"{API}/onboarding/progress", headers=H, timeout=30).json()
    assert g["completed"] is True
    # Reset for idempotency for later tests: mark uncompleted via patch (no endpoint to unset)
    # leave as-is; subsequent tests don't depend on completed flag


# ---- Barn settings ----
def test_barn_round_trip(H):
    payload = {
        "name": "TEST_ Equine Estate",
        "facility_type": "boarding",
        "disciplines": ["dressage", "show jumping"],
        "address": "123 Bridle Path",
        "timezone": "America/New_York",
        "contact_email": "barn@example.com",
        "contact_phone": "+1 555 0100",
    }
    r = requests.put(f"{API}/barn", headers=H, json=payload, timeout=30)
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["name"] == payload["name"]
    assert saved["disciplines"] == payload["disciplines"]

    g = requests.get(f"{API}/barn", headers=H, timeout=30)
    assert g.status_code == 200
    assert g.json()["name"] == payload["name"]
    assert g.json()["contact_email"] == "barn@example.com"


# ---- Locations CRUD ----
def test_locations_crud(H):
    r = requests.post(f"{API}/locations", headers=H,
                      json={"type": "stall", "name": "TEST_ Stall 99", "capacity": 1,
                            "notes": "test"}, timeout=30)
    assert r.status_code == 200
    loc = r.json()
    assert loc["name"] == "TEST_ Stall 99" and "id" in loc
    lid = loc["id"]

    g = requests.get(f"{API}/locations", headers=H, timeout=30)
    assert g.status_code == 200
    assert any(x["id"] == lid for x in g.json())

    d = requests.delete(f"{API}/locations/{lid}", headers=H, timeout=30)
    assert d.status_code == 200

    g2 = requests.get(f"{API}/locations", headers=H, timeout=30).json()
    assert not any(x["id"] == lid for x in g2)


# ---- Feed templates ----
def test_feed_templates_crud(H):
    r = requests.post(f"{API}/feed-templates", headers=H,
                      json={"meal": "morning", "hay_type": "Timothy", "hay_lbs": 5,
                            "grain_type": "Senior", "grain_lbs": 2}, timeout=30)
    assert r.status_code == 200
    tid = r.json()["id"]
    g = requests.get(f"{API}/feed-templates", headers=H, timeout=30).json()
    assert any(x["id"] == tid for x in g)
    requests.delete(f"{API}/feed-templates/{tid}", headers=H, timeout=30)


# ---- Inventory + low_stock ----
def test_inventory_low_stock(H):
    r = requests.post(f"{API}/inventory", headers=H,
                      json={"category": "grain", "name": "TEST_ Senior Grain",
                            "unit": "lbs", "quantity": 5, "reorder_at": 10}, timeout=30)
    assert r.status_code == 200
    iid = r.json()["id"]
    g = requests.get(f"{API}/inventory", headers=H, timeout=30).json()
    found = [x for x in g if x["id"] == iid]
    assert found and found[0]["low_stock"] is True

    # Higher stock - not low
    r2 = requests.post(f"{API}/inventory", headers=H,
                       json={"category": "hay", "name": "TEST_ Bale Hay",
                             "unit": "bales", "quantity": 100, "reorder_at": 10}, timeout=30)
    iid2 = r2.json()["id"]
    g2 = requests.get(f"{API}/inventory", headers=H, timeout=30).json()
    found2 = [x for x in g2 if x["id"] == iid2]
    assert found2 and found2[0]["low_stock"] is False

    requests.delete(f"{API}/inventory/{iid}", headers=H, timeout=30)
    requests.delete(f"{API}/inventory/{iid2}", headers=H, timeout=30)


# ---- Recurring schedules ----
def test_recurring_schedules_crud(H):
    r = requests.post(f"{API}/recurring-schedules", headers=H,
                      json={"type": "turnout", "name": "TEST_ AM Turnout",
                            "days_of_week": ["mon", "tue", "wed"], "time": "07:30"}, timeout=30)
    assert r.status_code == 200
    sid = r.json()["id"]
    g = requests.get(f"{API}/recurring-schedules", headers=H, timeout=30).json()
    assert any(x["id"] == sid for x in g)
    requests.delete(f"{API}/recurring-schedules/{sid}", headers=H, timeout=30)


# ---- Staff invites validate role ----
def test_staff_invites_valid_role(H):
    r = requests.post(f"{API}/staff-invites", headers=H,
                      json={"email": "test_staff@example.com", "full_name": "TEST_ Staff",
                            "role": "trainer", "permissions": ["horses:read"]}, timeout=30)
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    assert r.json()["status"] == "pending"
    g = requests.get(f"{API}/staff-invites", headers=H, timeout=30).json()
    assert any(x["id"] == sid for x in g)
    requests.delete(f"{API}/staff-invites/{sid}", headers=H, timeout=30)


def test_staff_invites_invalid_role(H):
    r = requests.post(f"{API}/staff-invites", headers=H,
                      json={"email": "bad@example.com", "role": "not_a_role"}, timeout=30)
    assert r.status_code == 400


# ---- CSV preview/commit/template horses ----
def test_csv_template_horses(H):
    r = requests.get(f"{API}/onboarding/csv-template", headers=H,
                     params={"kind": "horses"}, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "text" in data and "name" in data["text"]
    assert data["filename"].endswith(".csv")


def test_csv_template_owners(H):
    r = requests.get(f"{API}/onboarding/csv-template", headers=H,
                     params={"kind": "owners"}, timeout=30)
    assert r.status_code == 200
    assert "full_name" in r.json()["text"]


def test_csv_preview_and_commit_horses(H):
    import uuid
    suffix = uuid.uuid4().hex[:8]
    name_a = f"TEST_Comet_{suffix}"
    name_b = f"TEST_Luna_{suffix}"
    csv_text = ("name,breed,age,color,discipline\n"
                f"{name_a},Thoroughbred,8,Chestnut,Dressage\n"
                f"{name_b},Warmblood,12,Gray,Show Jumping\n")
    r = requests.post(f"{API}/onboarding/csv-preview", headers=H,
                      json={"kind": "horses", "csv_text": csv_text}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["count"] == 2
    assert len(d["rows"]) == 2
    assert isinstance(d["duplicates"], list)

    rc = requests.post(f"{API}/onboarding/csv-commit", headers=H,
                       json={"kind": "horses", "rows": d["rows"]}, timeout=30)
    assert rc.status_code == 200, rc.text
    assert rc.json()["created"] == 2

    # Re-preview should show duplicates now
    r2 = requests.post(f"{API}/onboarding/csv-preview", headers=H,
                       json={"kind": "horses", "csv_text": csv_text}, timeout=30).json()
    names = {n.lower() for n in r2["duplicates"]}
    assert name_a.lower() in names

    # Cleanup created horses
    horses = requests.get(f"{API}/horses", headers=H, timeout=30).json()
    for h in horses:
        if h.get("name", "").startswith("TEST_"):
            requests.delete(f"{API}/horses/{h['id']}", headers=H, timeout=30)


def test_csv_preview_and_commit_owners(H):
    import uuid
    suffix = uuid.uuid4().hex[:8]
    email_a = f"test_owner1_{suffix}@example.com"
    email_b = f"test_owner2_{suffix}@example.com"
    csv_text = ("full_name,email,phone,waiver_signed\n"
                f"TEST_Owner_One_{suffix},{email_a},555-0001,yes\n"
                f"TEST_Owner_Two_{suffix},{email_b},555-0002,no\n")
    r = requests.post(f"{API}/onboarding/csv-preview", headers=H,
                      json={"kind": "owners", "csv_text": csv_text}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 2

    rc = requests.post(f"{API}/onboarding/csv-commit", headers=H,
                       json={"kind": "owners", "rows": d["rows"]}, timeout=30)
    assert rc.status_code == 200
    assert rc.json()["created"] == 2

    # Re-preview should mark duplicates
    r2 = requests.post(f"{API}/onboarding/csv-preview", headers=H,
                       json={"kind": "owners", "csv_text": csv_text}, timeout=30).json()
    assert email_a in [d.lower() for d in r2["duplicates"]]

    # Cleanup
    owners = requests.get(f"{API}/owners", headers=H, timeout=30).json()
    for o in owners:
        if (o.get("full_name") or "").startswith("TEST_"):
            try:
                requests.delete(f"{API}/owners/{o['id']}", headers=H, timeout=30)
            except Exception:
                pass
