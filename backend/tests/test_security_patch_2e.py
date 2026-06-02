"""Security Patch 2E regression tests.

Covers three founder-beta security findings:
  1. The destructive public POST /api/seed route is locked down (disabled by
     default; not anonymously destructive).
  2. Public registration cannot create privileged roles (no admin escalation).
  3. Email-verification enforcement gates session issuance on registration.

Mixes pure-function unit tests (no server needed) with live HTTP tests against
REACT_APP_BACKEND_URL.
"""
import os
import pathlib
import time

import asyncio

import pytest
import requests

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from core.config import (
    allow_seed_route,
    auto_seed_enabled,
    evaluate_seed_access,
    user_verification_ok,
)
from routes.auth import (
    should_issue_session_on_register,
    PUBLIC_REGISTRATION_ROLE,
    make_current_user_dependency,
    create_token,
)

from ._test_creds import ADMIN


def _base_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    env = pathlib.Path(__file__).resolve().parents[2] / "frontend" / ".env"
    for line in env.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


BASE = _base_url()
API = f"{BASE}/api"


def _register(role=None, password="origPass123"):
    email = f"sec2e_{time.time_ns()}@example.com"
    payload = {"email": email, "password": password, "full_name": "Sec Test"}
    if role is not None:
        payload["role"] = role
    r = requests.post(f"{API}/auth/register", json=payload, timeout=30)
    return email, r


# ---------------- 1. Seed lockdown ----------------

def test_allow_seed_route_default_false():
    # Pure-function: the guard is OFF unless explicitly enabled.
    assert allow_seed_route({}) is False
    assert allow_seed_route({"ALLOW_SEED_ROUTE": "false"}) is False
    assert allow_seed_route({"ALLOW_SEED_ROUTE": "true"}) is True
    assert allow_seed_route({"ALLOW_SEED_ROUTE": "1"}) is True


def test_seed_route_blocked_by_default():
    # Disabled route presents as not-found (anonymous, no auth).
    r = requests.post(f"{API}/seed", timeout=30)
    assert r.status_code == 404, r.text


def test_seed_not_anonymously_destructive():
    # Calling seed anonymously must not wipe data: demo admin still logs in
    # and the seeded horse roster is intact afterward.
    requests.post(f"{API}/seed", timeout=30)
    login = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    horses = requests.get(
        f"{API}/horses", headers={"Authorization": f"Bearer {token}"}, timeout=30
    )
    assert horses.status_code == 200
    assert len(horses.json()) >= 6


def test_evaluate_seed_access_production_always_blocked():
    # Production is blocked even with the flag on and an admin + confirmation.
    allowed, code, _ = evaluate_seed_access(
        is_prod=True, allow_route=True, authenticated=True, role="admin", confirm_ok=True
    )
    assert allowed is False and code == 404


def test_evaluate_seed_access_branches():
    # Disabled (flag off) → 404
    assert evaluate_seed_access(is_prod=False, allow_route=False, authenticated=True,
                                role="admin", confirm_ok=True)[:2] == (False, 404)
    # Enabled but anonymous → 401
    assert evaluate_seed_access(is_prod=False, allow_route=True, authenticated=False,
                                role=None, confirm_ok=False)[:2] == (False, 401)
    # Enabled, authenticated non-admin → 403
    assert evaluate_seed_access(is_prod=False, allow_route=True, authenticated=True,
                                role="groom", confirm_ok=True)[:2] == (False, 403)
    # Enabled, admin, missing confirmation → 400
    assert evaluate_seed_access(is_prod=False, allow_route=True, authenticated=True,
                                role="admin", confirm_ok=False)[:2] == (False, 400)
    # Enabled, admin, confirmed → allowed
    allowed, code, _ = evaluate_seed_access(is_prod=False, allow_route=True,
                                            authenticated=True, role="admin", confirm_ok=True)
    assert allowed is True and code is None


def test_auto_seed_enabled_policy():
    # Production is a hard no — NOT overridable by ALLOW_AUTO_SEED.
    assert auto_seed_enabled({"APP_ENV": "production"}) is False
    assert auto_seed_enabled({"APP_ENV": "production", "ALLOW_AUTO_SEED": "true"}) is False
    assert auto_seed_enabled({"APP_ENV": "prod", "ALLOW_AUTO_SEED": "1"}) is False
    # On in dev/test by default; explicit off respected.
    assert auto_seed_enabled({"APP_ENV": "development"}) is True
    assert auto_seed_enabled({"APP_ENV": "development", "ALLOW_AUTO_SEED": "false"}) is False


# ---------------- 2. Registration role escalation ----------------

def test_public_registration_defaults_to_safe_role():
    assert PUBLIC_REGISTRATION_ROLE == "horse_owner"
    _, r = _register(role=None)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["role"] == PUBLIC_REGISTRATION_ROLE


@pytest.mark.parametrize("privileged", ["admin", "barn_manager", "trainer", "groom"])
def test_public_registration_ignores_privileged_role(privileged):
    _, r = _register(role=privileged)
    assert r.status_code == 200, r.text
    role = r.json()["user"]["role"]
    assert role == PUBLIC_REGISTRATION_ROLE
    assert role != privileged


def test_escalated_registrant_cannot_reach_admin_endpoints():
    # A user who tried to register as admin gets a horse_owner session and is
    # rejected from an admin-only endpoint.
    _, r = _register(role="admin")
    assert r.status_code == 200, r.text
    token = r.json().get("token")
    assert token  # enforcement off by default → session issued
    h = {"Authorization": f"Bearer {token}"}
    # tenant-reset is admin-only; escalated registrant must be forbidden.
    res = requests.post(
        f"{API}/admin/tenant-reset",
        json={"scope": "onboarding", "confirm": "RESET"},
        headers=h,
        timeout=30,
    )
    assert res.status_code == 403, res.text


# ---------------- 3. Email-verification enforcement gate ----------------

def test_should_issue_session_helper_logic():
    # Enforcement OFF → always issue (preserves auto-login).
    assert should_issue_session_on_register(email_verified=False, enforce=False) is True
    assert should_issue_session_on_register(email_verified=True, enforce=False) is True
    # Enforcement ON → only a verified user gets a session.
    assert should_issue_session_on_register(email_verified=True, enforce=True) is True
    assert should_issue_session_on_register(email_verified=False, enforce=True) is False


def test_user_verification_ok_policy():
    # Enforcement OFF → everyone passes regardless of flag.
    off = {"ENFORCE_EMAIL_VERIFICATION": "false"}
    assert user_verification_ok({"email_verified": False}, off) is True
    # Enforcement ON → unverified blocked, verified allowed, missing => verified.
    on = {"ENFORCE_EMAIL_VERIFICATION": "true"}
    assert user_verification_ok({"email_verified": False}, on) is False
    assert user_verification_ok({"email_verified": True}, on) is True
    assert user_verification_ok({}, on) is True  # legacy/backfilled user not locked out


def test_registration_returns_unverified_user():
    # Regardless of enforcement, a fresh account is created unverified.
    _, r = _register()
    assert r.status_code == 200, r.text
    assert r.json()["user"]["email_verified"] is False


_ENFORCEMENT_ON = os.environ.get("ENFORCE_EMAIL_VERIFICATION", "false").strip().lower() in (
    "1", "true", "yes", "on",
)


@pytest.mark.skipif(not _ENFORCEMENT_ON, reason="ENFORCE_EMAIL_VERIFICATION is off in this environment")
def test_registration_withholds_session_when_enforced():
    # When enforcement is ON, registration must not return usable tokens.
    _, r = _register()
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("pending_verification") is True
    assert "token" not in body and "refresh_token" not in body


@pytest.mark.skipif(not _ENFORCEMENT_ON, reason="ENFORCE_EMAIL_VERIFICATION is off in this environment")
def test_unverified_token_blocked_then_verified_succeeds():
    # Issue a token while we can, then prove an unverified holder is blocked
    # from a protected route until they verify.
    email = f"sec2e_enf_{time.time_ns()}@example.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "password": "origPass123", "full_name": "Enf",
    }, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    # Under enforcement, register returns no token — so this path proves the
    # blocking. (A pre-issued token scenario is proven manually in the patch.)
    assert body.get("pending_verification") is True
    vtok = body.get("dev_verification_token")
    assert vtok
    # Login is blocked until verified.
    login = requests.post(f"{API}/auth/login", json={"email": email, "password": "origPass123"}, timeout=30)
    assert login.status_code == 403
    # Verify, then login succeeds and /auth/me works.
    v = requests.post(f"{API}/auth/verify-email", json={"token": vtok}, timeout=30)
    assert v.status_code == 200
    login2 = requests.post(f"{API}/auth/login", json={"email": email, "password": "origPass123"}, timeout=30)
    assert login2.status_code == 200
    token = login2.json()["token"]
    me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    assert me.status_code == 200


# ---------------- Pre-issued-token rejection (dependency-level, no server) ----------------

class _FakeUsers:
    def __init__(self, user):
        self._user = user

    async def find_one(self, query, projection=None):
        return self._user


class _FakeDB:
    def __init__(self, user):
        self.users = _FakeUsers(user)


def _resolve(user, token):
    dep = make_current_user_dependency(_FakeDB(user))
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    return asyncio.run(dep(creds))


def test_pre_issued_token_rejected_when_unverified_and_enforced(monkeypatch):
    """An OTHERWISE-VALID token for an unverified user must be rejected by the
    protected current-user dependency once enforcement is on — proving the
    defense-in-depth gate, independent of register/login issuance behavior."""
    monkeypatch.setenv("ENFORCE_EMAIL_VERIFICATION", "true")
    uid = "u-2e-test"
    token = create_token(uid, "horse_owner")  # validly signed, not expired

    # Unverified holder → 403.
    with pytest.raises(HTTPException) as ei:
        _resolve({"id": uid, "role": "horse_owner", "email_verified": False}, token)
    assert ei.value.status_code == 403

    # Verified holder → allowed.
    ok = _resolve({"id": uid, "role": "horse_owner", "email_verified": True}, token)
    assert ok["email_verified"] is True

    # Legacy user missing the field → treated as verified (not locked out).
    legacy = _resolve({"id": uid, "role": "horse_owner"}, token)
    assert legacy["id"] == uid


def test_pre_issued_token_allowed_when_enforcement_off(monkeypatch):
    # With enforcement off (default), an unverified holder is NOT blocked.
    monkeypatch.setenv("ENFORCE_EMAIL_VERIFICATION", "false")
    uid = "u-2e-test-off"
    token = create_token(uid, "horse_owner")
    user = _resolve({"id": uid, "role": "horse_owner", "email_verified": False}, token)
    assert user["id"] == uid
