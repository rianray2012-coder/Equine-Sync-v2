"""EquineSync backend regression tests."""
import os
import requests
import pytest

from ._test_creds import ADMIN

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://barn-ops-preview.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data and data["user"]["email"] == ADMIN["email"]
    return data["token"]


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


# ---- Auth ----
def test_auth_me(H):
    r = requests.get(f"{API}/auth/me", headers=H, timeout=30)
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_auth_invalid():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN["email"], "password": "wrong"}, timeout=30)
    assert r.status_code == 401


# ---- Dashboard ----
def test_dashboard_summary(H):
    r = requests.get(f"{API}/dashboard/summary", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    for k in ["total_horses", "meds_due", "overdue_invoices", "avg_wellness"]:
        assert k in d
    assert d["total_horses"] >= 6


def test_dashboard_barn_board(H):
    r = requests.get(f"{API}/dashboard/barn-board", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    for k in ["feed", "medications", "lessons", "stall_rest"]:
        assert k in d
    # Weather was a hardcoded fake surface — intentionally removed Feb 20 2026
    # as part of the founder-beta trust-tightening sprint.
    assert "weather" not in d


# ---- Horses ----
def test_horses_list_and_detail(H):
    r = requests.get(f"{API}/horses", headers=H, timeout=30)
    assert r.status_code == 200
    horses = r.json()
    assert len(horses) >= 6
    hid = horses[0]["id"]
    r2 = requests.get(f"{API}/horses/{hid}", headers=H, timeout=30)
    assert r2.status_code == 200
    assert r2.json()["id"] == hid


# ---- Seeded lists ----
@pytest.mark.parametrize("path", [
    "medications", "vet-records", "injuries", "wellness", "lessons",
    "training", "invoices", "messages", "owners", "riders",
])
def test_seeded_lists(H, path):
    r = requests.get(f"{API}/{path}", headers=H, timeout=30)
    assert r.status_code == 200, f"{path} -> {r.status_code}"
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1, f"{path} empty"


# ---- Feed complete (legacy collection — being deprecated Phase-A) ----
def test_feed_complete(H):
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()
    r = requests.get(f"{API}/feed-tasks", headers=H, params={"date_str": today}, timeout=30)
    assert r.status_code == 200
    tasks = r.json()
    pending = [t for t in tasks if not t.get("completed")]
    if not pending:
        # Legacy collection has no POST endpoint and is being retired. Once all
        # pre-seeded rows are completed, skip — the engine test_task_engine.py
        # already covers feed completion via the unified engine.
        pytest.skip("Legacy feed_tasks fully completed; covered by engine tests")
    tid = pending[0]["id"]
    r2 = requests.post(f"{API}/feed-tasks/{tid}/complete", headers=H, timeout=30)
    assert r2.status_code == 200
    assert r2.json()["completed"] is True


# ---- Invoice pay ----
def test_invoice_pay(H):
    r = requests.get(f"{API}/invoices", headers=H, timeout=30)
    open_inv = [i for i in r.json() if i["status"] != "paid"]
    # Idempotent fixture: create one if all paid.
    if not open_inv:
        owners = requests.get(f"{API}/owners", headers=H, timeout=30).json()
        horses = requests.get(f"{API}/horses", headers=H, timeout=30).json()
        r_seed = requests.post(f"{API}/invoices", headers=H, json={
            "owner_id": owners[0]["id"], "horse_id": horses[0]["id"],
            "amount": 100, "total": 100, "due_date": "2026-12-31",
            "status": "open", "items": [{"label": "TEST", "amount": 100}],
        }, timeout=30)
        assert r_seed.status_code == 200, r_seed.text
        open_inv = [r_seed.json()]
    iid = open_inv[0]["id"]
    r2 = requests.post(f"{API}/invoices/{iid}/pay", headers=H, timeout=30)
    assert r2.status_code == 200
    assert r2.json()["status"] == "paid"


# ---- Service request create + approve ----
def test_service_request_flow(H):
    horses = requests.get(f"{API}/horses", headers=H, timeout=30).json()
    payload = {"horse_id": horses[0]["id"], "type": "extra_ride", "details": "TEST_ extra ride"}
    r = requests.post(f"{API}/service-requests", json=payload, headers=H, timeout=30)
    assert r.status_code == 200
    sr_id = r.json()["id"]
    assert r.json()["status"] == "pending"
    r2 = requests.post(f"{API}/service-requests/{sr_id}/approve", headers=H, timeout=30)
    assert r2.status_code == 200
    assert r2.json()["status"] == "approved"


# ---- Message create ----
def test_message_create(H):
    payload = {"to_role": "trainer", "subject": "TEST_ msg", "body": "Hello", "visibility": "staff_only"}
    r = requests.post(f"{API}/messages", json=payload, headers=H, timeout=30)
    assert r.status_code == 200
    assert r.json()["subject"] == "TEST_ msg"
    assert r.json()["from_name"]


# ---- AI generate (REMOVED Feb 20 2026 — founder-beta trust sprint) ----
# The /ai/generate endpoint and its HorseProfile UI buttons were deleted to
# match the agreed "no speculative AI / no pseudo-veterinary advice" direction.
# Wellness Pulse remains the calm rule-based observational layer.
def test_ai_generate_endpoint_is_gone(H):
    body = {"kind": "owner_update", "context": {"horse": "Valentino"}}
    r = requests.post(f"{API}/ai/generate", json=body, headers=H, timeout=10)
    assert r.status_code == 404
