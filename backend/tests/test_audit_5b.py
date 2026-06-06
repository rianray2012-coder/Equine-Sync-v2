"""Phase 5B — audit instrumentation integration tests (auth/session + admin
/destructive + permission.denied).

Live API + Mongo. Each audited action is driven through the real endpoint and
the resulting `audit_log` row is asserted. Every poll is bounded by this run's
start timestamp so an assertion can only pass on a row created by THIS run
(never a stale row). Teardown deletes audit rows by the exact ids captured
during the run (covers the anonymous `admin.seed.attempt` row and the shared
`groom` `permission.denied` row precisely), plus a unique-throwaway-email
backstop for the high-volume lockout failure rows.

Guardrails proven here:
  * response bodies / status codes / error messages are unchanged
  * no raw tokens / reset URLs / passwords ever land in audit metadata
"""
import os
import pathlib
import time
import uuid
from datetime import datetime, timezone

import pymongo
import requests

from ._test_creds import ADMIN, GROOM

PW = "Passw0rd!9"


def _read_env(key, parents, sub):
    envf = pathlib.Path(__file__).resolve().parents[parents] / sub
    for line in envf.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or _read_env("REACT_APP_BACKEND_URL", 2, "frontend/.env")).rstrip("/")
API = f"{BASE_URL}/api"


def mongo():
    url = os.environ.get("MONGO_URL") or _read_env("MONGO_URL", 1, ".env")
    name = os.environ.get("DB_NAME") or _read_env("DB_NAME", 1, ".env")
    return pymongo.MongoClient(url)[name]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


# Run-scoped state so teardown can purge exactly what this run created.
STATE = {"emails": set(), "barn_ids": set(), "audit_ids": set(), "start_ts": None}


def setup_module(module):
    # Real run start: every audit assertion is bounded by ts >= start_ts so it
    # can only match rows created by this run.
    STATE["start_ts"] = datetime.now(timezone.utc).isoformat()


def teardown_module(module):
    db = mongo()
    # Primary, precise cleanup: delete by the exact ids captured this run.
    ids = list(STATE["audit_ids"])
    if ids:
        db.audit_log.delete_many({"id": {"$in": ids}})
    emails = list(STATE["emails"])
    if emails:
        db.users.delete_many({"email": {"$in": emails}})
        db.login_attempts.delete_many({"email": {"$in": emails}})
        # Backstop for high-volume rows not individually captured (lockout
        # failures). Safe: these emails are unique to this test run.
        db.audit_log.delete_many({"actor_email": {"$in": emails}, "ts": {"$gte": STATE["start_ts"]}})
    for bid in STATE["barn_ids"]:
        db.barn.delete_many({"id": bid})
        db.users.delete_many({"barn_id": bid})
        db.onboarding_progress.delete_many({"barn_id": bid})


def _capture(query, timeout=6.0):
    """Poll for a fresh audit row (ts >= run start), record its id for teardown."""
    q = dict(query)
    q["ts"] = {"$gte": STATE["start_ts"]}
    db = mongo()
    deadline = time.time() + timeout
    while time.time() < deadline:
        doc = db.audit_log.find_one(q, sort=[("ts", -1)])
        if doc:
            STATE["audit_ids"].add(doc["id"])
            return doc
        time.sleep(0.2)
    return None


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    out = r.json()
    # Capture the success row this login produced (covers shared admin/groom
    # logins too, so they're deleted by id in teardown).
    _capture({"action": "auth.login.success", "actor_email": email.lower()})
    return out


def _register_throwaway():
    email = f"audit5b_{uuid.uuid4().hex[:10]}@ex.com"
    STATE["emails"].add(email)
    r = requests.post(f"{API}/auth/register",
                      json={"email": email, "password": PW, "full_name": "Audit 5B"}, timeout=30)
    assert r.status_code == 200, r.text
    return email, r.json()


# --------------------------------------------------------------------------
# Auth / session
# --------------------------------------------------------------------------
def test_login_success_and_failure_are_audited():
    email, reg = _register_throwaway()

    out = _login(email, PW)
    assert "token" in out
    row = _capture({"action": "auth.login.success", "actor_email": email})
    assert row and row["outcome"] == "success"
    assert row["resource_type"] == "session" and row["actor_user_id"] == out["user"]["id"]
    assert "password" not in str(row["metadata"]).lower()

    # failure — response/status unchanged (401 + "Invalid credentials")
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": "wrong-pass"}, timeout=30)
    assert r.status_code == 401 and r.json()["detail"] == "Invalid credentials"
    frow = _capture({"action": "auth.login.failure", "actor_email": email})
    assert frow and frow["outcome"] == "failure" and frow["status_code"] == 401
    assert frow["metadata"] == {"reason": "invalid_credentials"}


def test_login_locked_is_audited():
    email, _ = _register_throwaway()
    locked = False
    for _ in range(12):
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": "wrong"}, timeout=30)
        if r.status_code == 423:
            locked = True
            assert "temporarily locked" in r.json()["detail"]
            break
        assert r.status_code == 401 and r.json()["detail"] == "Invalid credentials"
    assert locked, "account did not lock within the attempt budget"
    row = _capture({"action": "auth.login.locked", "actor_email": email})
    assert row and row["outcome"] == "denied" and row["status_code"] == 423
    assert row["metadata"]["reason"] == "account_locked"
    assert "retry_after_minutes" in row["metadata"]


def test_refresh_and_logout_are_audited():
    email, _ = _register_throwaway()
    out = _login(email, PW)
    rr = requests.post(f"{API}/auth/refresh", json={"refresh_token": out["refresh_token"]}, timeout=30)
    assert rr.status_code == 200
    assert _capture({"action": "auth.token.refreshed", "actor_email": email})
    new = rr.json()
    lo = requests.post(f"{API}/auth/logout", json={"refresh_token": new["refresh_token"]},
                       headers=_headers(new["token"]), timeout=30)
    assert lo.status_code == 200 and lo.json() == {"ok": True}
    assert _capture({"action": "auth.logout", "actor_email": email})


def test_logout_all_is_audited():
    email, _ = _register_throwaway()
    out = _login(email, PW)
    r = requests.post(f"{API}/auth/logout-all", headers=_headers(out["token"]), timeout=30)
    assert r.status_code == 200 and r.json() == {"ok": True}
    row = _capture({"action": "auth.logout_all", "actor_email": email})
    assert row and row["resource_type"] == "session"
    assert row["metadata"] == {"scope": "all_sessions"}


def test_password_reset_request_complete_and_email_verify_audited():
    email, reg = _register_throwaway()

    fr = requests.post(f"{API}/auth/forgot-password", json={"email": email}, timeout=30)
    assert fr.status_code == 200
    req_row = _capture({"action": "auth.password_reset.requested", "actor_email": email})
    assert req_row and req_row["metadata"] == {"email_dispatched": True}
    dev_token = fr.json().get("dev_token")
    assert dev_token

    rp = requests.post(f"{API}/auth/reset-password",
                       json={"token": dev_token, "new_password": "NewPassw0rd!"}, timeout=30)
    assert rp.status_code == 200
    comp = _capture({"action": "auth.password_reset.completed", "actor_email": email})
    assert comp and comp["metadata"] == {"sessions_revoked": True}
    blob = str(comp).lower()
    assert dev_token.lower() not in blob and "new_password" not in blob

    raw_verify = reg.get("dev_verification_token")
    assert raw_verify
    ve = requests.post(f"{API}/auth/verify-email", json={"token": raw_verify}, timeout=30)
    assert ve.status_code == 200
    assert _capture({"action": "auth.email.verified", "actor_email": email})


# --------------------------------------------------------------------------
# Admin / destructive + permission.denied
# --------------------------------------------------------------------------
def test_seed_attempt_denied_is_audited():
    r = requests.post(f"{API}/seed", timeout=30)
    assert r.status_code in (403, 404)
    row = _capture({"action": "admin.seed.attempt", "resource_id": "seed", "outcome": "denied"})
    assert row and row["status_code"] in (403, 404)
    assert "confirm_ok" in row["metadata"]  # flag present, no token/secret stored


def test_permission_denied_on_tenant_reset_gate_is_audited():
    groom = _login(GROOM["email"], GROOM["password"])
    r = requests.post(f"{API}/admin/tenant-reset",
                      json={"scope": "onboarding", "confirm": "RESET"},
                      headers=_headers(groom["token"]), timeout=30)
    assert r.status_code == 403 and r.json()["detail"] == "Admin only"
    row = _capture({"action": "permission.denied", "actor_email": GROOM["email"],
                    "resource_id": "admin:access"})
    assert row and row["outcome"] == "denied" and row["status_code"] == 403
    assert row["metadata"]["capability"] == "admin:access"


def test_barn_created_is_audited():
    admin = _login(ADMIN["email"], ADMIN["password"])
    admin_email = f"audit5b_barn_{uuid.uuid4().hex[:10]}@ex.com"
    STATE["emails"].add(admin_email)
    r = requests.post(f"{API}/barns", json={
        "name": "Audit5B Barn " + uuid.uuid4().hex[:6],
        "admin_email": admin_email, "admin_full_name": "Audit5B Admin",
        "admin_password": PW,
    }, headers=_headers(admin["token"]), timeout=30)
    assert r.status_code in (200, 201), r.text
    barn_id = r.json()["barn"]["id"]
    STATE["barn_ids"].add(barn_id)
    row = _capture({"action": "barn.created", "resource_id": barn_id})
    assert row and row["resource_type"] == "barn"
    assert row["metadata"]["new_admin_user_id"] and "admin_password" not in str(row["metadata"]).lower()
