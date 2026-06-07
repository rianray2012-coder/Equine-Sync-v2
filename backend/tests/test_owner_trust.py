"""Phase-C: Owner Trust Loop tests."""
import uuid
import requests
import pytest
from datetime import datetime, timezone, timedelta

from ._owner_helpers import API, auth_headers
from ._test_creds import ADMIN, OWNER


@pytest.fixture(scope="module")
def admin_h():
    return auth_headers(ADMIN)


@pytest.fixture(scope="module")
def owner_h():
    return auth_headers(OWNER)


# ─────────────────────────────────────────────────────────────────────────────
# Pure composition tests (no network)
# ─────────────────────────────────────────────────────────────────────────────

def test_vet_phrase_with_name():
    from owner_digest import _vet_phrase
    ev = [{"event_type": "task.completed", "category": "vet",
           "payload_snapshot": {"vet_name": "Dr. Hale", "title": "Spring Booster"}}]
    out = _vet_phrase(ev, "Mercury")
    assert out and "Mercury" in out and "Dr. Hale" in out


def test_medication_phrase_completed_all():
    from owner_digest import _medication_phrase
    events = [{"event_type": "task.completed", "category": "medication",
               "payload_snapshot": {"title": f"Dose-{i}"}} for i in range(3)]
    out = _medication_phrase(events, "Halo", window_label="this week")
    assert out == "Halo completed all scheduled medications this week."


def test_medication_phrase_refused_softens():
    from owner_digest import _medication_phrase
    events = [{"event_type": "task.skipped", "category": "medication",
               "payload_snapshot": {"outcome": "refused", "title": "Bute"}}]
    out = _medication_phrase(events, "Halo")
    assert out and "declined" in out and "note for the vet" in out


def test_upcoming_phrase_vet_uses_date():
    from owner_digest import _upcoming_phrase
    soon = datetime.now(timezone.utc) + timedelta(days=3)
    tasks = [{"category": "vet", "scheduled_at": soon.isoformat(),
              "title": "Spring vaccines", "payload": {}}]
    out = _upcoming_phrase(tasks, "Mercury")
    assert out and "Spring vaccines" in out and "scheduled for" in out


def test_compose_returns_none_when_no_meaningful_updates():
    from owner_digest import compose_horse_section
    horse = {"id": "h1", "name": "Quiet"}
    assert compose_horse_section(horse, [], [], []) is None


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end (DB + endpoints)
# ─────────────────────────────────────────────────────────────────────────────

def test_digest_preview_endpoint_returns_payload_or_empty(owner_h):
    r = requests.post(f"{API}/notifications/digest/preview", headers=owner_h, timeout=30)
    assert r.status_code == 200
    body = r.json()
    if body.get("empty"):
        assert body["reason"] == "no_updates_today"
    else:
        assert "payload" in body and "html" in body and "text" in body
        assert "EquineSync" in body["html"] or "Today" in body["text"]


def test_digest_admin_run_now(admin_h):
    r = requests.post(f"{API}/admin/digest/run-now", headers=admin_h, timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert "sent" in body and "skipped" in body and "for_date" in body


def test_service_request_decline(owner_h, admin_h):
    # Create a service request as owner
    horses = requests.get(f"{API}/horses", headers=admin_h, timeout=30).json()
    horse_id = horses[0]["id"]
    create = requests.post(f"{API}/service-requests", headers=owner_h, timeout=30, json={
        "horse_id": horse_id, "type": "hand_walk", "details": "Decline test",
    })
    assert create.status_code == 200, create.text
    sr_id = create.json()["id"]
    # Decline as admin
    r = requests.post(f"{API}/service-requests/{sr_id}/decline", headers=admin_h, timeout=30,
                      json={"reason": "Trainer unavailable Tue"})
    assert r.status_code == 200, r.text
    sr = r.json()
    assert sr["status"] == "declined"
    assert sr["decline_reason"] == "Trainer unavailable Tue"
    assert sr.get("declined_at")


def test_prefs_include_digest_toggle(owner_h):
    g = requests.get(f"{API}/notifications/preferences", headers=owner_h, timeout=30)
    assert g.status_code == 200
    assert "digest_enabled" in g.json()
    # Owners can opt out
    p = requests.put(f"{API}/notifications/preferences", headers=owner_h, timeout=30, json={
        "inbox_enabled": True, "email_enabled": True, "push_enabled": False,
        "digest_enabled": False, "inbox_rules": {}, "email_rules": {},
    })
    assert p.status_code == 200
    assert p.json()["digest_enabled"] is False
    # Restore default for downstream tests
    requests.put(f"{API}/notifications/preferences", headers=owner_h, timeout=30, json={
        "inbox_enabled": True, "email_enabled": True, "push_enabled": False,
        "digest_enabled": True, "inbox_rules": {}, "email_rules": {},
    })
