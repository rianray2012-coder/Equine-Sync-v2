"""Phase 4A — public registration stamps canonical barn_id=primary (live integration).

Also re-asserts Security Patch 2E: a client-supplied privileged role is ignored
and the new account stays low-privilege (`horse_owner`).
"""
import os
import pathlib
import uuid

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


API = f"{_base_url()}/api"


def test_public_registration_gets_primary_barn_and_stays_low_privilege():
    email = f"phase4a_{uuid.uuid4().hex[:10]}@example.com"
    r = requests.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": "demo1234!",
            "full_name": "Phase 4A Tester",
            # Attempt privilege escalation — must be ignored (Security Patch 2E).
            "role": "admin",
        },
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    user = data.get("user") or {}
    # Phase 4A: stored user doc carries canonical barn.
    assert user.get("barn_id") == "primary", data
    # Security Patch 2E: public registration is always low-privilege.
    assert user.get("role") == "horse_owner", data
