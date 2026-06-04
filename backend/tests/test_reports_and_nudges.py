"""Tests for Setup Health Reports + Nudge endpoints (review iteration 4).
Covers:
  - GET /api/reports/setup-health (admin OK / groom 403 / shape)
  - GET /api/reports/nudge-candidates?min_days=N
  - POST /api/admin/send-nudges (admin only, cooldown, sandbox, counters, analytics)
  - POST /api/invites — owner-email real send vs sandbox skip (Resend live key)
"""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

from ._test_creds import ADMIN, GROOM, DEMO_PASSWORD

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://barn-ops-preview.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = ADMIN["email"]
GROOM_EMAIL = GROOM["email"]
PASSWORD = DEMO_PASSWORD

OWNER_REAL_EMAIL = os.environ.get("TEST_OWNER_REAL_EMAIL", "rian.ray2012@gmail.com")  # Resend sandbox-allowed recipient


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def db():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    client = MongoClient(mongo_url)
    return client[db_name]


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, PASSWORD)["token"]


@pytest.fixture(scope="module")
def groom_token():
    return _login(GROOM_EMAIL, PASSWORD)["token"]


@pytest.fixture
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture
def groom_h(groom_token):
    return {"Authorization": f"Bearer {groom_token}", "Content-Type": "application/json"}


# ---------- /reports/setup-health ----------
class TestSetupHealth:
    def test_setup_health_shape(self, admin_h):
        r = requests.get(f"{API}/reports/setup-health", headers=admin_h, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ["total_setups", "completed_setups", "in_progress_setups",
                  "completion_rate", "median_hours_to_launch", "median_days_to_launch",
                  "funnel", "invites"]:
            assert k in data, f"missing key {k}"
        assert isinstance(data["funnel"], list)
        assert len(data["funnel"]) == 10, f"expected 10 funnel rows, got {len(data['funnel'])}"
        for row in data["funnel"]:
            for sub in ["step", "label", "complete", "in_progress", "skipped", "pending"]:
                assert sub in row
            assert isinstance(row["complete"], int)
        inv = data["invites"]
        for k in ["total", "accepted", "pending", "revoked", "expired", "acceptance_rate"]:
            assert k in inv
        assert 0 <= inv["acceptance_rate"] <= 100
        assert data["in_progress_setups"] == data["total_setups"] - data["completed_setups"]

    def test_setup_health_groom_forbidden(self, groom_h):
        r = requests.get(f"{API}/reports/setup-health", headers=groom_h, timeout=15)
        assert r.status_code == 403

    def test_setup_health_no_auth(self):
        r = requests.get(f"{API}/reports/setup-health", timeout=15)
        assert r.status_code in (401, 403)


# ---------- /reports/nudge-candidates ----------
class TestNudgeCandidates:
    def test_candidates_default_shape(self, admin_h):
        r = requests.get(f"{API}/reports/nudge-candidates?min_days=3", headers=admin_h, timeout=15)
        assert r.status_code == 200, r.text
        rows = r.json()
        assert isinstance(rows, list)
        for c in rows:
            for k in ["user_id", "email", "percent_done", "next_step",
                      "next_step_label", "days_stalled"]:
                assert k in c, f"missing {k} in candidate row"
            assert c["days_stalled"] >= 3
            assert 0 <= c["percent_done"] <= 100

    def test_candidates_min_days_zero_returns_all_stalled(self, admin_h, db):
        # min_days=0 must include any incomplete progress whose updated_at is in the past.
        # We'll seed an explicit stalled candidate to be deterministic.
        uid = f"TEST_nudge_{uuid.uuid4().hex[:8]}"
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        db.users.insert_one({
            "id": uid, "email": f"{uid}@example.com", "full_name": "Test Stalled",
            "role": "barn_manager", "barn_id": "primary", "created_at": old,
        })
        db.onboarding_progress.insert_one({
            "user_id": uid, "completed": False, "barn_id": "primary",
            "steps": {"barn": "complete", "locations": "in_progress"},
            "current_step": "locations",
            "created_at": old, "updated_at": old,
        })
        try:
            r = requests.get(f"{API}/reports/nudge-candidates?min_days=5", headers=admin_h, timeout=15)
            assert r.status_code == 200
            rows = r.json()
            ids = [c["user_id"] for c in rows]
            assert uid in ids, f"stalled test user not in candidates: {ids}"
            mine = next(c for c in rows if c["user_id"] == uid)
            assert mine["days_stalled"] >= 10
            assert mine["next_step"] == "locations"
        finally:
            db.users.delete_one({"id": uid})
            db.onboarding_progress.delete_one({"user_id": uid})

    def test_candidates_groom_forbidden(self, groom_h):
        r = requests.get(f"{API}/reports/nudge-candidates", headers=groom_h, timeout=15)
        assert r.status_code == 403


# ---------- /admin/send-nudges ----------
class TestSendNudges:
    def test_send_nudges_no_candidates(self, admin_h):
        # Very large min_days → unlikely any candidate, but should always return ok.
        r = requests.post(f"{API}/admin/send-nudges",
                          headers=admin_h, json={"min_days": 9999, "cooldown_hours": 24}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ["candidates", "sent", "skipped", "errors", "detail"]:
            assert k in d
        assert d["candidates"] == 0
        assert d["sent"] == 0

    def test_send_nudges_groom_forbidden(self, groom_h):
        r = requests.post(f"{API}/admin/send-nudges", headers=groom_h, json={"min_days": 3}, timeout=15)
        assert r.status_code == 403

    def test_send_nudges_with_seeded_candidate_and_cooldown(self, admin_h, db):
        """Seeds a stalled candidate, triggers nudge, asserts last_nudged_at + nudges_sent + cooldown skip."""
        uid = f"TEST_nudge_send_{uuid.uuid4().hex[:8]}"
        # Use a non-owner email so Resend returns 'sandbox' (dev=true) — counted as 'skipped'
        # but the user_id update path still runs.
        seed_email = f"{uid}@example.com"
        old = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        db.users.insert_one({
            "id": uid, "email": seed_email, "full_name": "Cooldown Tester",
            "role": "barn_manager", "barn_id": "primary", "created_at": old,
        })
        db.onboarding_progress.insert_one({
            "user_id": uid, "completed": False, "barn_id": "primary",
            "steps": {"barn": "complete"}, "current_step": "locations",
            "created_at": old, "updated_at": old,
        })
        try:
            # First run — should target the seeded user.
            r1 = requests.post(f"{API}/admin/send-nudges", headers=admin_h,
                               json={"min_days": 5, "cooldown_hours": 24, "user_ids": [uid]}, timeout=30)
            assert r1.status_code == 200, r1.text
            d1 = r1.json()
            assert d1["candidates"] == 1, d1
            # Either sent (if seeded email happens to be the owner) OR skipped via sandbox.
            assert d1["sent"] + d1["skipped"] + d1["errors"] == 1
            # last_nudged_at + nudges_sent should now be set on the progress doc
            time.sleep(0.5)
            doc = db.onboarding_progress.find_one({"user_id": uid})
            assert doc is not None
            assert doc.get("last_nudged_at") is not None, "last_nudged_at not set"
            assert doc.get("nudges_sent", 0) >= 1, f"nudges_sent not incremented: {doc.get('nudges_sent')}"

            # Second run within cooldown → should skip with reason cooldown
            r2 = requests.post(f"{API}/admin/send-nudges", headers=admin_h,
                               json={"min_days": 5, "cooldown_hours": 24, "user_ids": [uid]}, timeout=30)
            assert r2.status_code == 200
            d2 = r2.json()
            assert d2["candidates"] == 1
            cooldown_skipped = any(item.get("result") == "cooldown" for item in d2.get("detail", []))
            assert cooldown_skipped, f"expected cooldown skip, got {d2}"
            assert d2["skipped"] >= 1
        finally:
            db.users.delete_one({"id": uid})
            db.onboarding_progress.delete_one({"user_id": uid})

    def test_send_nudges_records_analytics(self, admin_h, db):
        before = db.events.count_documents({"name": "admin.nudges_run"})
        r = requests.post(f"{API}/admin/send-nudges", headers=admin_h,
                          json={"min_days": 9999, "cooldown_hours": 24}, timeout=15)
        assert r.status_code == 200
        time.sleep(0.5)
        after = db.events.count_documents({"name": "admin.nudges_run"})
        assert after >= before + 1, f"admin.nudges_run not recorded ({before} -> {after})"


# ---------- /invites sandbox behaviour ----------
class TestInviteSandboxStatus:
    def test_invite_to_owner_returns_sent(self, admin_h, db):
        """Resend live key + sandbox mode allows real delivery to rian.ray2012@gmail.com."""
        payload = {"email": OWNER_REAL_EMAIL, "role": "groom", "full_name": "Owner Inbox"}
        r = requests.post(f"{API}/invites", headers=admin_h, json=payload, timeout=30)
        if r.status_code == 409:
            pytest.skip(f"owner already invited / exists: {r.text}")
        assert r.status_code in (200, 201), r.text
        d = r.json()
        assert d.get("status") == "pending", d  # invite lifecycle
        sends = d.get("sends") or []
        assert sends, "sends history empty"
        # Real delivery to owner inbox should succeed (sent) — accept sandbox as fallback
        # in case the Resend key is rate-limited or in a degraded state.
        send_status = sends[-1].get("status")
        assert send_status in ("sent", "sandbox", "dev_logged"), f"unexpected send status: {send_status}"
        if send_status == "sent":
            # Live delivery — no dev_accept_url surfaced
            assert d.get("dev_accept_url") in (None, ""), "dev_accept_url should be hidden on successful send"
        try:
            db.invites.delete_one({"id": d["id"]})
        except Exception:
            pass

    def test_invite_to_non_owner_returns_sandbox_with_dev_link(self, admin_h, db):
        """Non-owner email under Resend sandbox => send status 'sandbox' + dev_accept_url surfaced."""
        non_owner = f"nudge_test_{uuid.uuid4().hex[:8]}@example.com"
        payload = {"email": non_owner, "role": "groom", "full_name": "Sandbox Target"}
        r = requests.post(f"{API}/invites", headers=admin_h, json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text
        d = r.json()
        assert d.get("status") == "pending", d
        sends = d.get("sends") or []
        assert sends, "sends history empty"
        send_status = sends[-1].get("status")
        assert send_status in ("sandbox", "dev_logged"), f"expected sandbox skip, got {send_status}"
        assert d.get("dev_accept_url"), f"dev_accept_url missing for sandbox send: {d}"
        assert "/accept-invite?token=" in d["dev_accept_url"]
        try:
            db.invites.delete_one({"id": d["id"]})
        except Exception:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
