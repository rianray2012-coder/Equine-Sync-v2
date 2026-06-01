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

import pytest
import requests

from core.config import allow_seed_route
from routes.auth import should_issue_session_on_register, PUBLIC_REGISTRATION_ROLE

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
    assert r.status_code in (403, 404), r.text


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


def test_registration_returns_unverified_user():
    # Regardless of enforcement, a fresh account is created unverified.
    _, r = _register()
    assert r.status_code == 200, r.text
    assert r.json()["user"]["email_verified"] is False


@pytest.mark.skipif(
    os.environ.get("ENFORCE_EMAIL_VERIFICATION", "false").strip().lower()
    not in ("1", "true", "yes", "on"),
    reason="ENFORCE_EMAIL_VERIFICATION is off in this environment",
)
def test_registration_withholds_session_when_enforced():
    # When enforcement is ON, registration must not return usable tokens.
    _, r = _register()
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("pending_verification") is True
    assert "token" not in body and "refresh_token" not in body
