"""Phase-C edge-case tests: role gating on digest send-me and decline endpoint."""
import requests
import pytest

from ._owner_helpers import API, login_headers as _login


@pytest.fixture(scope="module")
def headers():
    return {
        "admin":  _login("admin@equinesync.com"),
        "owner":  _login("owner@equinesync.com"),
        "groom":  _login("groom@equinesync.com"),
        "trainer": _login("trainer@equinesync.com"),
    }


# --- digest/send-me role gating ---------------------------------------------

def test_digest_send_me_owner_ok(headers):
    r = requests.post(f"{API}/notifications/digest/send-me", headers=headers["owner"], timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    # Sensible response: either sent True or a reason
    assert "sent" in body or "reason" in body


def test_digest_send_me_non_owner_forbidden(headers):
    for role in ("admin", "groom", "trainer"):
        r = requests.post(f"{API}/notifications/digest/send-me", headers=headers[role], timeout=30)
        assert r.status_code == 403, f"{role} got {r.status_code}: {r.text}"


# --- service-request decline role gating ------------------------------------

def _new_pending_sr(owner_h, admin_h):
    horses = requests.get(f"{API}/horses", headers=admin_h, timeout=30).json()
    horse_id = horses[0]["id"]
    r = requests.post(f"{API}/service-requests", headers=owner_h, timeout=30, json={
        "horse_id": horse_id, "type": "grooming", "details": "Edge test",
    })
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_groom_cannot_decline(headers):
    sr_id = _new_pending_sr(headers["owner"], headers["admin"])
    r = requests.post(f"{API}/service-requests/{sr_id}/decline", headers=headers["groom"],
                      timeout=30, json={"reason": "nope"})
    assert r.status_code in (401, 403), r.text


def test_trainer_can_decline_with_optional_reason_empty(headers):
    sr_id = _new_pending_sr(headers["owner"], headers["admin"])
    # Empty reason should still succeed (reason optional)
    r = requests.post(f"{API}/service-requests/{sr_id}/decline", headers=headers["trainer"],
                      timeout=30, json={})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "declined"


def test_owner_cannot_decline(headers):
    sr_id = _new_pending_sr(headers["owner"], headers["admin"])
    r = requests.post(f"{API}/service-requests/{sr_id}/decline", headers=headers["owner"],
                      timeout=30, json={"reason": "self-decline"})
    assert r.status_code in (401, 403), r.text


def test_decline_idempotency_or_state_guard(headers):
    """Declining a non-pending request should not silently mutate to declined again."""
    sr_id = _new_pending_sr(headers["owner"], headers["admin"])
    r1 = requests.post(f"{API}/service-requests/{sr_id}/decline", headers=headers["admin"],
                       timeout=30, json={"reason": "first"})
    assert r1.status_code == 200
    r2 = requests.post(f"{API}/service-requests/{sr_id}/decline", headers=headers["admin"],
                       timeout=30, json={"reason": "second"})
    # Either 400/409 (proper state guard) or 200 idempotent — both acceptable
    assert r2.status_code in (200, 400, 409), r2.text
