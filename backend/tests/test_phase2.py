"""
Phase 2 tests — Auth hardening, Curated Owner Timeline, Notifications, Engine-backed pages.

Covers:
- /api/auth/login response shape (token, refresh_token, expires_in_seconds, user)
- /api/auth/refresh rotation (single-use), revoke on rotated token, logout
- Security headers + CSP
- GET /api/horses/{id}/timeline?owner_view=true curation
- GET /api/tasks?category=... date window
- POST /api/tasks/{id}/complete + appears on timeline
- GET /api/task-templates?category=medication&active=true
- /api/notifications endpoints (list, read, read-all, prefs, drain)
- Notification fan-out for non-actor admin
- Owner notification visibility (only curated categories)
"""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta

from ._test_creds import ADMIN as ADMIN_DICT, OWNER as OWNER_DICT, GROOM as GROOM_DICT

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://barn-ops-preview.preview.emergentagent.com"

# Tuple form preserved for the (email, pwd) call sites below.
ADMIN = (ADMIN_DICT["email"], ADMIN_DICT["password"])
OWNER = (OWNER_DICT["email"], OWNER_DICT["password"])
GROOM = (GROOM_DICT["email"], GROOM_DICT["password"])


# ---------- helpers ----------

def _login(email, pwd):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def admin_session():
    return _login(*ADMIN)


@pytest.fixture(scope="session")
def owner_session():
    return _login(*OWNER)


@pytest.fixture(scope="session")
def groom_session():
    return _login(*GROOM)


# ---------- 1. Auth login response shape ----------

class TestAuthShape:
    def test_login_returns_full_shape(self):
        r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
        assert r.status_code == 200
        d = r.json()
        assert "token" in d and isinstance(d["token"], str) and len(d["token"]) > 20
        assert "refresh_token" in d and isinstance(d["refresh_token"], str) and len(d["refresh_token"]) > 20
        assert d.get("expires_in_seconds") == 14400, f"expected 14400, got {d.get('expires_in_seconds')}"
        assert "user" in d and d["user"]["email"] == ADMIN[0]
        assert "password_hash" not in d["user"]

    def test_login_invalid(self):
        r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN[0], "password": "wrong"})
        assert r.status_code == 401

    def test_me_endpoint(self, admin_session):
        r = requests.get(f"{BASE}/api/auth/me", headers=_h(admin_session["token"]))
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN[0]


# ---------- 2. Refresh-token rotation ----------

class TestRefreshRotation:
    def test_rotate_and_revoke_old(self):
        s = _login(*ADMIN)
        rt = s["refresh_token"]
        r1 = requests.post(f"{BASE}/api/auth/refresh", json={"refresh_token": rt})
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["refresh_token"] != rt, "refresh token did not rotate"
        assert d1["expires_in_seconds"] == 14400
        # Old token should now 401
        r2 = requests.post(f"{BASE}/api/auth/refresh", json={"refresh_token": rt})
        assert r2.status_code == 401, f"old token still works: {r2.status_code}"
        # New token works for /me
        rme = requests.get(f"{BASE}/api/auth/me", headers=_h(d1["token"]))
        assert rme.status_code == 200

    def test_logout_revokes_refresh(self):
        s = _login(*ADMIN)
        rt = s["refresh_token"]
        rlo = requests.post(f"{BASE}/api/auth/logout", json={"refresh_token": rt},
                            headers=_h(s["token"]))
        assert rlo.status_code == 200
        # Using the revoked refresh should fail
        rr = requests.post(f"{BASE}/api/auth/refresh", json={"refresh_token": rt})
        assert rr.status_code == 401


# ---------- 3. Security headers ----------

class TestSecurityHeaders:
    def test_headers_present(self):
        r = requests.get(f"{BASE}/api/")
        h = {k.lower(): v for k, v in r.headers.items()}
        assert h.get("x-frame-options") == "DENY"
        assert h.get("x-content-type-options") == "nosniff"
        assert h.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert "permissions-policy" in h and "camera=()" in h["permissions-policy"]
        csp = h.get("content-security-policy", "")
        assert csp.startswith("default-src 'self'"), f"CSP unexpected: {csp[:80]}"
        assert "frame-ancestors 'none'" in csp


# ---------- 4. Curated owner timeline ----------

CURATED = {"medication", "farrier", "vet", "rehab", "feed"}


class TestCuratedTimeline:
    def _first_horse_id(self, token):
        r = requests.get(f"{BASE}/api/horses", headers=_h(token))
        assert r.status_code == 200
        hs = r.json()
        assert hs, "no horses seeded"
        return hs[0]["id"]

    def test_owner_view_filters_categories(self, admin_session):
        hid = self._first_horse_id(admin_session["token"])
        r = requests.get(f"{BASE}/api/horses/{hid}/timeline?owner_view=true",
                         headers=_h(admin_session["token"]))
        assert r.status_code == 200, r.text
        data = r.json()
        # Accept either list or {items:[...]} shape
        items = data if isinstance(data, list) else data.get("items", data.get("timeline", []))
        cats = {it.get("category") for it in items if it.get("category")}
        bad = cats - CURATED
        assert not bad, f"non-curated categories leaked: {bad}"

    def test_owner_role_always_curated(self, owner_session):
        # Owner can only see horses they own — try /api/horses first
        r = requests.get(f"{BASE}/api/horses", headers=_h(owner_session["token"]))
        if r.status_code != 200 or not r.json():
            pytest.skip("owner has no horses visible")
        hid = r.json()[0]["id"]
        # Even without owner_view=true, owner role should be enforced
        r2 = requests.get(f"{BASE}/api/horses/{hid}/timeline",
                          headers=_h(owner_session["token"]))
        assert r2.status_code == 200
        data = r2.json()
        items = data if isinstance(data, list) else data.get("items", data.get("timeline", []))
        cats = {it.get("category") for it in items if it.get("category")}
        bad = cats - CURATED
        assert not bad, f"owner saw non-curated categories: {bad}"


# ---------- 5. Engine-backed tasks endpoints ----------

class TestTasksEndpoints:
    def test_tasks_today(self, admin_session):
        r = requests.get(f"{BASE}/api/tasks/today", headers=_h(admin_session["token"]))
        assert r.status_code == 200
        d = r.json()
        # Should return some grouping or list
        assert isinstance(d, (dict, list))

    def test_tasks_by_category_feed(self, admin_session):
        today = datetime.now(timezone.utc).date()
        start = today.isoformat()
        end = (today + timedelta(days=1)).isoformat()
        r = requests.get(
            f"{BASE}/api/tasks",
            params={"category": "feed", "start": start, "end": end},
            headers=_h(admin_session["token"]),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        if items:
            for t in items:
                assert t.get("category") == "feed"

    def test_tasks_by_category_medication(self, admin_session):
        r = requests.get(
            f"{BASE}/api/tasks",
            params={"category": "medication"},
            headers=_h(admin_session["token"]),
        )
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        for t in items:
            assert t.get("category") == "medication"

    def test_active_medication_templates(self, admin_session):
        r = requests.get(
            f"{BASE}/api/task-templates",
            params={"category": "medication", "active": "true"},
            headers=_h(admin_session["token"]),
        )
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        for t in items:
            assert t.get("category") == "medication"


# ---------- 6. Task completion via engine + timeline visibility ----------

class TestCompletionFlow:
    def test_complete_appears_on_timeline(self, admin_session):
        token = admin_session["token"]
        # Find a horse
        hid = requests.get(f"{BASE}/api/horses", headers=_h(token)).json()[0]["id"]
        # Create a one-off medication task
        cid = str(uuid.uuid4())
        body = {
            "linked_horse_ids": [hid],
            "category": "medication",
            "title": f"TEST_med_{cid[:6]}",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
        }
        rc = requests.post(f"{BASE}/api/tasks", json=body, headers=_h(token))
        assert rc.status_code in (200, 201), rc.text
        rj = rc.json()
        tid = (rj.get("task") or rj).get("id")
        assert tid, f"no task id in {rj}"
        # Complete it
        rcomp = requests.post(
            f"{BASE}/api/tasks/{tid}/complete",
            json={"client_completion_id": cid, "outcome": "done"},
            headers=_h(token),
        )
        assert rcomp.status_code in (200, 201), rcomp.text
        # Verify on full timeline
        rt = requests.get(f"{BASE}/api/horses/{hid}/timeline", headers=_h(token))
        assert rt.status_code == 200
        data = rt.json()
        items = data if isinstance(data, list) else data.get("items", data.get("timeline", []))
        assert any(it.get("task_id") == tid or it.get("title", "").startswith("TEST_med") for it in items), \
            "completed task not surfaced on timeline"


# ---------- 7. Notifications endpoints ----------

class TestNotifications:
    def test_list_notifications(self, admin_session):
        r = requests.get(f"{BASE}/api/notifications", headers=_h(admin_session["token"]))
        assert r.status_code == 200, r.text
        d = r.json()
        assert "items" in d and "unread" in d
        assert isinstance(d["items"], list)
        assert isinstance(d["unread"], int)

    def test_get_prefs_default(self, admin_session):
        r = requests.get(f"{BASE}/api/notifications/preferences", headers=_h(admin_session["token"]))
        assert r.status_code == 200
        p = r.json()
        for k in ("inbox_enabled", "email_enabled", "inbox_rules", "email_rules"):
            assert k in p

    def test_put_prefs(self, admin_session):
        body = {
            "inbox_enabled": True,
            "email_enabled": False,
            "inbox_rules": {"task.completed": ["medication", "vet"]},
            "email_rules": {"task.skipped": ["medication"]},
        }
        r = requests.put(f"{BASE}/api/notifications/preferences", json=body,
                         headers=_h(admin_session["token"]))
        assert r.status_code == 200, r.text
        # GET back and verify
        rg = requests.get(f"{BASE}/api/notifications/preferences", headers=_h(admin_session["token"]))
        d = rg.json()
        assert d["email_enabled"] is False
        assert d["inbox_rules"]["task.completed"] == ["medication", "vet"]

    def test_drain_admin_only(self, admin_session, owner_session):
        # owner forbidden
        ro = requests.post(f"{BASE}/api/notifications/drain", headers=_h(owner_session["token"]))
        assert ro.status_code == 403
        # admin ok
        ra = requests.post(f"{BASE}/api/notifications/drain", headers=_h(admin_session["token"]))
        assert ra.status_code == 200
        assert "drained" in ra.json()

    def test_read_all(self, admin_session):
        r = requests.post(f"{BASE}/api/notifications/read-all", headers=_h(admin_session["token"]))
        assert r.status_code == 200
        # unread should now be 0
        rg = requests.get(f"{BASE}/api/notifications", headers=_h(admin_session["token"]))
        assert rg.json()["unread"] == 0


# ---------- 8. Fan-out: groom completes → admin gets notification ----------

class TestNotificationFanout:
    def test_groom_completes_admin_receives(self, admin_session, groom_session):
        admin_token = admin_session["token"]
        groom_token = groom_session["token"]
        # Reset admin prefs to defaults that include medication completion
        requests.put(
            f"{BASE}/api/notifications/preferences",
            json={"inbox_enabled": True, "email_enabled": False,
                  "inbox_rules": {"task.completed": ["medication", "vet", "farrier", "rehab"]},
                  "email_rules": {}},
            headers=_h(admin_token),
        )
        # Clear unread
        requests.post(f"{BASE}/api/notifications/read-all", headers=_h(admin_token))
        # Find a horse the groom can see
        rh = requests.get(f"{BASE}/api/horses", headers=_h(groom_token))
        if rh.status_code != 200 or not rh.json():
            pytest.skip("groom cannot see horses; skipping fan-out")
        hid = rh.json()[0]["id"]
        # Groom creates and completes a vet task
        cid = str(uuid.uuid4())
        rc = requests.post(
            f"{BASE}/api/tasks",
            json={"linked_horse_ids": [hid], "category": "vet",
                  "title": f"TEST_vet_fanout_{cid[:6]}",
                  "scheduled_at": datetime.now(timezone.utc).isoformat()},
            headers=_h(groom_token),
        )
        if rc.status_code not in (200, 201):
            pytest.skip(f"groom cannot create tasks: {rc.status_code} {rc.text}")
        rj = rc.json()
        tid = (rj.get("task") or rj).get("id")
        rcomp = requests.post(
            f"{BASE}/api/tasks/{tid}/complete",
            json={"client_completion_id": cid, "outcome": "done"},
            headers=_h(groom_token),
        )
        assert rcomp.status_code in (200, 201), rcomp.text
        # Force-drain
        rd = requests.post(f"{BASE}/api/notifications/drain", headers=_h(admin_token))
        assert rd.status_code == 200
        time.sleep(1)
        # Admin should have ≥1 unread now
        rg = requests.get(f"{BASE}/api/notifications", headers=_h(admin_token))
        d = rg.json()
        assert d["unread"] >= 1, f"admin did not receive notification, unread={d['unread']}, items={len(d['items'])}"

    def test_owner_only_curated_notifications(self, admin_session, groom_session, owner_session):
        admin_token = admin_session["token"]
        groom_token = groom_session["token"]
        owner_token = owner_session["token"]
        # Set owner prefs to receive ALL categories on inbox — even so, server must filter
        requests.put(
            f"{BASE}/api/notifications/preferences",
            json={"inbox_enabled": True, "email_enabled": False,
                  "inbox_rules": {"task.completed": ["*"]},
                  "email_rules": {}},
            headers=_h(owner_token),
        )
        requests.post(f"{BASE}/api/notifications/read-all", headers=_h(owner_token))
        # Find a horse owned by the owner
        rh = requests.get(f"{BASE}/api/horses", headers=_h(owner_token))
        if rh.status_code != 200 or not rh.json():
            pytest.skip("owner has no horse; skip")
        hid = rh.json()[0]["id"]
        # Groom completes a stall_clean (non-curated) — owner should NOT see it
        for cat in ("stall_clean", "turnout_in"):
            cid = str(uuid.uuid4())
            rc = requests.post(
                f"{BASE}/api/tasks",
                json={"linked_horse_ids": [hid], "category": cat,
                      "title": f"TEST_{cat}_{cid[:6]}",
                      "scheduled_at": datetime.now(timezone.utc).isoformat()},
                headers=_h(groom_token),
            )
            if rc.status_code in (200, 201):
                rj = rc.json()
                tid = (rj.get("task") or rj).get("id")
                requests.post(
                    f"{BASE}/api/tasks/{tid}/complete",
                    json={"client_completion_id": cid, "outcome": "done"},
                    headers=_h(groom_token),
                )
        requests.post(f"{BASE}/api/notifications/drain", headers=_h(admin_token))
        time.sleep(1)
        rg = requests.get(f"{BASE}/api/notifications", headers=_h(owner_token))
        d = rg.json()
        # Inspect items — none should be stall_clean/turnout categories
        for it in d["items"]:
            cat = it.get("category") or it.get("payload", {}).get("category")
            assert cat in CURATED or cat is None, f"owner got non-curated notification cat={cat}"
