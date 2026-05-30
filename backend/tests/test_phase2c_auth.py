"""HTTP integration tests for Phase 2C auth flows.

Covers: email verification, password reset, dev-token issuance, no-leak behavior,
the /api/health probe, and that existing users are not locked out.

Runs against the live server (REACT_APP_BACKEND_URL). Uses the dev-only token
returned in non-production responses to complete flows.
"""
import os
import pathlib
import time

import requests


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


def _register(role="trainer", password="origPass123"):
    email = f"phase2c_{time.time_ns()}@example.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "password": password, "full_name": "Test User", "role": role,
    }, timeout=30)
    assert r.status_code == 200, r.text
    return email, r.json()


def test_register_creates_unverified_user_with_dev_token():
    _, data = _register()
    assert data["user"]["email_verified"] is False
    assert data.get("dev_verification_token")
    # auto-login on register is preserved
    assert data.get("token") and data.get("refresh_token")


def test_email_verification_flow():
    _, data = _register()
    tok = data["dev_verification_token"]
    r = requests.post(f"{API}/auth/verify-email", json={"token": tok}, timeout=30)
    assert r.status_code == 200 and r.json()["ok"] is True
    # reused token is rejected
    r2 = requests.post(f"{API}/auth/verify-email", json={"token": tok}, timeout=30)
    assert r2.status_code == 400


def test_verify_email_invalid_token():
    r = requests.post(f"{API}/auth/verify-email", json={"token": "bogus-token"}, timeout=30)
    assert r.status_code == 400


def test_password_reset_flow():
    email, _ = _register(password="origPass123")
    fp = requests.post(f"{API}/auth/forgot-password", json={"email": email}, timeout=30)
    assert fp.status_code == 200
    tok = fp.json().get("dev_token")
    assert tok
    rp = requests.post(f"{API}/auth/reset-password", json={
        "token": tok, "new_password": "newPass456",
    }, timeout=30)
    assert rp.status_code == 200 and rp.json()["ok"] is True
    # old password no longer works
    old = requests.post(f"{API}/auth/login", json={"email": email, "password": "origPass123"}, timeout=30)
    assert old.status_code == 401
    # new password works
    new = requests.post(f"{API}/auth/login", json={"email": email, "password": "newPass456"}, timeout=30)
    assert new.status_code == 200


def test_reset_with_invalid_token():
    r = requests.post(f"{API}/auth/reset-password", json={
        "token": "bogus", "new_password": "whatever123",
    }, timeout=30)
    assert r.status_code == 400


def test_reset_rejects_short_password():
    email, _ = _register()
    tok = requests.post(f"{API}/auth/forgot-password", json={"email": email}, timeout=30).json()["dev_token"]
    r = requests.post(f"{API}/auth/reset-password", json={"token": tok, "new_password": "short"}, timeout=30)
    assert r.status_code == 400


def test_forgot_password_unknown_email_does_not_leak():
    r = requests.post(f"{API}/auth/forgot-password", json={
        "email": f"nonexistent_{time.time_ns()}@example.com",
    }, timeout=30)
    assert r.status_code == 200
    # no token issued for a non-existent account
    assert "dev_token" not in r.json()


def test_health_endpoint():
    r = requests.get(f"{API}/health", timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert body["config"]["jwt_configured"] is True
    # never leaks secret values
    assert "JWT_SECRET" not in r.text and "change-me" not in r.text


def test_existing_user_not_locked_out():
    # A freshly registered (unverified) user can still log in (enforcement OFF by default).
    email, data = _register(password="loginPass123")
    assert data["user"]["email_verified"] is False
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": "loginPass123"}, timeout=30)
    assert r.status_code == 200
