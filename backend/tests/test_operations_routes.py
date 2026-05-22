"""Regression: routes/operations.py extraction (Phase-F final).

Verifies the operational endpoints (lessons, training, invoices, messages,
service-requests, incidents) respond identically after extraction from
server.py to routes/operations.py. Also validates role gating + 409 guard
on service-request approve / decline.
"""
import os
import uuid

import pytest
import requests

from ._test_creds import DEMO_PASSWORD, ADMIN, OWNER, GROOM

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {
    "admin":   (ADMIN["email"],   DEMO_PASSWORD),
    "trainer": ("trainer@equinesync.com", DEMO_PASSWORD),
    "groom":   (GROOM["email"],   DEMO_PASSWORD),
    "owner":   (OWNER["email"],   DEMO_PASSWORD),
}


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def tokens():
    return {role: _login(email, pw) for role, (email, pw) in CREDS.items()}


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_h(tokens):
    return _h(tokens["admin"])


@pytest.fixture(scope="module")
def trainer_h(tokens):
    return _h(tokens["trainer"])


@pytest.fixture(scope="module")
def groom_h(tokens):
    return _h(tokens["groom"])


@pytest.fixture(scope="module")
def horse_id(admin_h):
    r = requests.get(f"{API}/horses", headers=admin_h, timeout=20)
    assert r.status_code == 200
    horses = r.json()
    assert horses, "no seeded horses"
    return horses[0]["id"]


# ---------------- Auth gate ----------------

def test_lessons_requires_auth():
    r = requests.get(f"{API}/lessons", timeout=20)
    assert r.status_code in (401, 403)


# ---------------- Lessons ----------------

def test_lessons_list_and_create(admin_h):
    g = requests.get(f"{API}/lessons", headers=admin_h, timeout=20)
    assert g.status_code == 200
    assert isinstance(g.json(), list)

    payload = {
        "rider_id": f"TEST_rider_{uuid.uuid4().hex[:6]}",
        "start_time": "2026-03-01T10:00:00Z",
        "duration_min": 45,
        "focus": "TEST_dressage",
    }
    c = requests.post(f"{API}/lessons", headers=admin_h, json=payload, timeout=20)
    assert c.status_code == 200, c.text
    body = c.json()
    assert body["focus"] == "TEST_dressage"
    assert body["duration_min"] == 45
    assert "id" in body and "created_at" in body
    assert "_id" not in body


# ---------------- Training ----------------

def test_training_list_create_and_filter(admin_h, horse_id):
    payload = {
        "horse_id": horse_id,
        "date": "2026-03-02T08:00:00Z",
        "discipline": "TEST_jumping",
        "rating": 4,
    }
    c = requests.post(f"{API}/training", headers=admin_h, json=payload, timeout=20)
    assert c.status_code == 200, c.text
    assert c.json()["horse_id"] == horse_id

    f = requests.get(f"{API}/training", headers=admin_h,
                     params={"horse_id": horse_id}, timeout=20)
    assert f.status_code == 200
    rows = f.json()
    assert all(r["horse_id"] == horse_id for r in rows)
    assert any(r.get("discipline") == "TEST_jumping" for r in rows)


# ---------------- Invoices ----------------

def test_invoices_create_list_and_pay(admin_h):
    payload = {
        "owner_id": f"TEST_owner_{uuid.uuid4().hex[:6]}",
        "items": [{"label": "TEST_board", "amount": 500}],
        "total": 500.0,
        "due_date": "2026-04-01",
    }
    c = requests.post(f"{API}/invoices", headers=admin_h, json=payload, timeout=20)
    assert c.status_code == 200, c.text
    inv = c.json()
    assert inv["status"] == "open"
    inv_id = inv["id"]

    g = requests.get(f"{API}/invoices", headers=admin_h, timeout=20)
    assert g.status_code == 200
    assert any(i["id"] == inv_id for i in g.json())

    p = requests.post(f"{API}/invoices/{inv_id}/pay", headers=admin_h, timeout=20)
    assert p.status_code == 200, p.text
    assert p.json()["status"] == "paid"
    assert "paid_at" in p.json()


# ---------------- Messages ----------------

def test_messages_create_stamps_sender(admin_h):
    payload = {
        "subject": "TEST_subject",
        "body": "TEST_body",
        "to_role": "groom",
    }
    c = requests.post(f"{API}/messages", headers=admin_h, json=payload, timeout=20)
    assert c.status_code == 200, c.text
    m = c.json()
    assert m["subject"] == "TEST_subject"
    assert m["read"] is False
    assert m.get("from_user_id")
    assert m.get("from_name")


# ---------------- Service Requests ----------------

def _create_sr(headers, horse_id, suffix=""):
    payload = {"horse_id": horse_id, "type": f"TEST_farrier{suffix}",
               "details": "TEST_details"}
    r = requests.post(f"{API}/service-requests", headers=headers, json=payload, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "pending"
    return body["id"]


def test_sr_approve_happy_path(admin_h, trainer_h, horse_id):
    sr_id = _create_sr(admin_h, horse_id, "_approve")
    a = requests.post(f"{API}/service-requests/{sr_id}/approve", headers=trainer_h, timeout=20)
    assert a.status_code == 200, a.text
    assert a.json()["status"] == "approved"
    assert "approved_at" in a.json()


def test_sr_approve_409_when_already_decided(admin_h, horse_id):
    sr_id = _create_sr(admin_h, horse_id, "_dup")
    a1 = requests.post(f"{API}/service-requests/{sr_id}/approve", headers=admin_h, timeout=20)
    assert a1.status_code == 200
    a2 = requests.post(f"{API}/service-requests/{sr_id}/approve", headers=admin_h, timeout=20)
    assert a2.status_code == 409, a2.text


def test_sr_approve_403_for_groom(admin_h, groom_h, horse_id):
    sr_id = _create_sr(admin_h, horse_id, "_groom")
    r = requests.post(f"{API}/service-requests/{sr_id}/approve", headers=groom_h, timeout=20)
    assert r.status_code == 403, r.text


def test_sr_decline_with_reason_and_409_guard(admin_h, horse_id):
    sr_id = _create_sr(admin_h, horse_id, "_decline")
    long_reason = "x" * 700
    d = requests.post(f"{API}/service-requests/{sr_id}/decline",
                      headers=admin_h, json={"reason": long_reason}, timeout=20)
    assert d.status_code == 200, d.text
    body = d.json()
    assert body["status"] == "declined"
    # cap at 500 chars
    assert len(body["decline_reason"]) == 500

    # second decline -> 409
    d2 = requests.post(f"{API}/service-requests/{sr_id}/decline",
                       headers=admin_h, json={"reason": "again"}, timeout=20)
    assert d2.status_code == 409


def test_sr_decline_403_for_groom(admin_h, groom_h, horse_id):
    sr_id = _create_sr(admin_h, horse_id, "_decline_groom")
    r = requests.post(f"{API}/service-requests/{sr_id}/decline",
                      headers=groom_h, json={"reason": "no"}, timeout=20)
    assert r.status_code == 403


def test_sr_decline_404_unknown(admin_h):
    r = requests.post(f"{API}/service-requests/nonexistent_id/decline",
                      headers=admin_h, json={"reason": "x"}, timeout=20)
    assert r.status_code == 404


def test_sr_list(admin_h):
    g = requests.get(f"{API}/service-requests", headers=admin_h, timeout=20)
    assert g.status_code == 200
    assert isinstance(g.json(), list)


# ---------------- Incidents ----------------

def test_incidents_create_and_list(admin_h, horse_id):
    payload = {
        "horse_id": horse_id,
        "type": "TEST_minor",
        "title": "TEST_title",
        "description": "TEST_desc",
        "severity": "low",
        "occurred_at": "2026-03-05T15:00:00Z",
    }
    c = requests.post(f"{API}/incidents", headers=admin_h, json=payload, timeout=20)
    assert c.status_code == 200, c.text
    inc = c.json()
    assert inc["title"] == "TEST_title"
    assert inc.get("reported_by")  # stamped from user.full_name

    g = requests.get(f"{API}/incidents", headers=admin_h, timeout=20)
    assert g.status_code == 200
    assert any(i["id"] == inc["id"] for i in g.json())
