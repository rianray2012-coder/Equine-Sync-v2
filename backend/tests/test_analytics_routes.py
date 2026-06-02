"""Phase 3B — routes/analytics.py extraction tests.

Covers POST /api/events (auth required) and GET /api/events/onboarding-funnel
(setup-role gated).
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


def test_events_requires_auth():
    r = requests.post(f"{API}/events", json={"name": "x"}, timeout=30)
    assert r.status_code == 401


def test_events_records_with_auth():
    token = _token(ADMIN)
    r = requests.post(
        f"{API}/events",
        json={"name": "test.phase3b_analytics", "props": {"k": 1}},
        headers={"Authorization": f"Bearer {token}"}, timeout=30,
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


def test_onboarding_funnel_admin_ok():
    token = _token(ADMIN)
    r = requests.get(
        f"{API}/events/onboarding-funnel",
        headers={"Authorization": f"Bearer {token}"}, timeout=30,
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_onboarding_funnel_requires_setup_role():
    token = _token(GROOM)
    r = requests.get(
        f"{API}/events/onboarding-funnel",
        headers={"Authorization": f"Bearer {token}"}, timeout=30,
    )
    assert r.status_code == 403
