"""Phase 3B — routes/admin.py extraction tests.

Re-asserts the 2E-hardened seed contract from the new module path and the
admin tenant-reset gating. (The config-level branch coverage for
evaluate_seed_access / auto_seed_enabled lives in test_security_patch_2e.py.)
"""
import os
import pathlib

import requests

from ._test_creds import ADMIN, GROOM


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


def _token(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


# ---------------- seed route (2E protections, new module path) ----------------

def test_seed_disabled_by_default_returns_404():
    r = requests.post(f"{API}/seed", timeout=30)
    assert r.status_code == 404, r.text


def test_seed_anonymous_not_destructive():
    requests.post(f"{API}/seed", timeout=30)
    token = _token(ADMIN)
    horses = requests.get(f"{API}/horses", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    assert horses.status_code == 200
    assert len(horses.json()) >= 6


# ---------------- tenant-reset gating ----------------

def test_tenant_reset_requires_admin():
    token = _token(GROOM)
    r = requests.post(
        f"{API}/admin/tenant-reset",
        json={"scope": "onboarding", "confirm": "RESET"},
        headers={"Authorization": f"Bearer {token}"}, timeout=30,
    )
    assert r.status_code == 403, r.text


def test_tenant_reset_requires_confirmation():
    token = _token(ADMIN)
    r = requests.post(
        f"{API}/admin/tenant-reset",
        json={"scope": "onboarding", "confirm": "NOPE"},
        headers={"Authorization": f"Bearer {token}"}, timeout=30,
    )
    assert r.status_code == 400, r.text


def test_tenant_reset_unknown_scope():
    token = _token(ADMIN)
    r = requests.post(
        f"{API}/admin/tenant-reset",
        json={"scope": "bogus", "confirm": "RESET"},
        headers={"Authorization": f"Bearer {token}"}, timeout=30,
    )
    assert r.status_code == 400, r.text


def test_tenant_reset_onboarding_scope_ok():
    token = _token(ADMIN)
    r = requests.post(
        f"{API}/admin/tenant-reset",
        json={"scope": "onboarding", "confirm": "RESET"},
        headers={"Authorization": f"Bearer {token}"}, timeout=30,
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert "onboarding_progress" in r.json()["cleared"]
