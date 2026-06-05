"""Phase 4C — route-level permission wiring (behavior-identical).

Each swapped inline role check now routes through core.permissions.require().
These tests assert the live endpoints still return the EXACT same 403 message
for denied roles, and that allowed roles pass the gate (non-403).
"""
import os
import pathlib
import uuid

import requests

from ._test_creds import ADMIN, OWNER, GROOM


def _read_env(key, root_index, sub):
    envf = pathlib.Path(__file__).resolve().parents[root_index] / sub
    for line in envf.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _base_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    return _read_env("REACT_APP_BACKEND_URL", 2, "frontend/.env").rstrip("/")


API = f"{_base_url()}/api"


def _headers(creds):
    r = requests.post(f"{API}/auth/login",
                      json={"email": creds["email"], "password": creds["password"]}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _detail(resp):
    try:
        return resp.json().get("detail")
    except Exception:
        return None


# ---------------- admin:access — /admin/tenant-reset ----------------
def test_tenant_reset_admin_only_message():
    # Denied roles: send a valid body — require() runs first, so 403 fires
    # before the confirm-token check (no reset is performed).
    for creds in (GROOM, OWNER):
        r = requests.post(f"{API}/admin/tenant-reset", headers=_headers(creds),
                          json={"scope": "onboarding", "confirm": "RESET"}, timeout=30)
        assert r.status_code == 403, r.text
        assert _detail(r) == "Admin only"
    # admin passes the role gate; a wrong confirm token → 400 (no destructive reset)
    r = requests.post(f"{API}/admin/tenant-reset", headers=_headers(ADMIN),
                      json={"scope": "onboarding", "confirm": "WRONG"}, timeout=30)
    assert r.status_code == 400, r.text  # "Confirmation token required"


# ---------------- service_request:approve / decline ----------------
def test_service_request_approve_role_message():
    fake = f"sr_{uuid.uuid4().hex}"
    for creds in (GROOM, OWNER):
        r = requests.post(f"{API}/service-requests/{fake}/approve",
                          headers=_headers(creds), timeout=30)
        assert r.status_code == 403, r.text
        assert _detail(r) == "Insufficient role to approve service requests"
    # admin passes the gate → 404 (no such SR), not 403
    r = requests.post(f"{API}/service-requests/{fake}/approve",
                      headers=_headers(ADMIN), timeout=30)
    assert r.status_code == 404, r.text


def test_service_request_decline_role_message():
    fake = f"sr_{uuid.uuid4().hex}"
    for creds in (GROOM, OWNER):
        r = requests.post(f"{API}/service-requests/{fake}/decline",
                          headers=_headers(creds), json={"reason": "x"}, timeout=30)
        assert r.status_code == 403, r.text
        assert _detail(r) == "Insufficient role to decline service requests"
    r = requests.post(f"{API}/service-requests/{fake}/decline",
                      headers=_headers(ADMIN), json={"reason": "x"}, timeout=30)
    assert r.status_code == 404, r.text


# ---------------- digest:read_own — owner self-send ----------------
def test_digest_send_me_owner_only_message():
    for creds in (ADMIN, GROOM):
        r = requests.post(f"{API}/notifications/digest/send-me",
                          headers=_headers(creds), timeout=30)
        assert r.status_code == 403, r.text
        assert _detail(r) == "Owner accounts only"
    # owner passes the gate (200, possibly empty result)
    r = requests.post(f"{API}/notifications/digest/send-me",
                      headers=_headers(OWNER), timeout=30)
    assert r.status_code == 200, r.text


def test_weekly_recap_send_me_owner_only_message():
    for creds in (ADMIN, GROOM):
        r = requests.post(f"{API}/notifications/weekly-recap/send-me",
                          headers=_headers(creds), timeout=30)
        assert r.status_code == 403, r.text
        assert _detail(r) == "Owner accounts only"
    r = requests.post(f"{API}/notifications/weekly-recap/send-me",
                      headers=_headers(OWNER), timeout=30)
    assert r.status_code == 200, r.text


# ---------------- digest:admin — admin run-now ----------------
def test_digest_run_now_admin_manager_message():
    for creds in (GROOM, OWNER):
        r = requests.post(f"{API}/admin/digest/run-now", headers=_headers(creds), timeout=30)
        assert r.status_code == 403, r.text
        assert _detail(r) == "Admin/Manager only"
    r = requests.post(f"{API}/admin/digest/run-now", headers=_headers(ADMIN), timeout=30)
    assert r.status_code == 200, r.text


def test_weekly_recap_run_now_admin_manager_message():
    for creds in (GROOM, OWNER):
        r = requests.post(f"{API}/admin/weekly-recap/run-now", headers=_headers(creds), timeout=30)
        assert r.status_code == 403, r.text
        assert _detail(r) == "Admin/Manager only"
    r = requests.post(f"{API}/admin/weekly-recap/run-now", headers=_headers(ADMIN), timeout=30)
    assert r.status_code == 200, r.text


# ---------------- barn:manage — require_setup_role delegation end-to-end ----------------
def test_setup_role_delegation_message():
    # groom denied with the exact legacy message; admin allowed (200).
    r = requests.get(f"{API}/reports/setup-health", headers=_headers(GROOM), timeout=30)
    assert r.status_code == 403, r.text
    assert _detail(r) == "Owner / Barn Manager access required"
    r = requests.get(f"{API}/reports/setup-health", headers=_headers(ADMIN), timeout=30)
    assert r.status_code == 200, r.text
