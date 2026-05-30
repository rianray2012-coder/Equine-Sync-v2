"""Phase-C+: Weekly recap tests — calm, lightweight, idempotent."""
import os
import requests
import pytest
from datetime import datetime, timezone

from owner_digest import (
    _weekly_compose_section,
    _iso_week_key,
    render_weekly_recap_html,
    render_weekly_recap_text,
)

from ._test_creds import ADMIN, OWNER, GROOM


BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://barn-ops-preview.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def owner_h():
    r = requests.post(f"{API}/auth/login", json=OWNER, timeout=30)
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def admin_h():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


# -------- Pure composition (no DB) --------

def test_weekly_compose_returns_none_when_empty():
    horse = {"id": "h1", "name": "Halo"}
    assert _weekly_compose_section(horse, [], []) is None


def test_weekly_compose_completed_all_meds():
    horse = {"id": "h1", "name": "Halo"}
    events = [
        {"category": "medication", "event_type": "task.completed", "payload_snapshot": {}},
        {"category": "medication", "event_type": "task.completed", "payload_snapshot": {}},
    ]
    sec = _weekly_compose_section(horse, events, [])
    assert sec is not None
    assert any("completed all scheduled medications" in line for line in sec["lines"])
    assert len(sec["lines"]) <= 3


def test_weekly_compose_skipped_meds_framed_softly():
    horse = {"id": "h1", "name": "Mercury"}
    events = [
        {"category": "medication", "event_type": "task.skipped", "payload_snapshot": {}},
    ]
    sec = _weekly_compose_section(horse, events, [])
    assert sec is not None
    text = " ".join(sec["lines"]).lower()
    assert "rescheduled" in text
    # No operational guilt language
    assert "missed" not in text
    assert "failed" not in text


def test_weekly_compose_farrier_with_name():
    horse = {"id": "h1", "name": "Mercury"}
    events = [{
        "category": "farrier",
        "event_type": "task.completed",
        "payload_snapshot": {"farrier_name": "James K."},
    }]
    sec = _weekly_compose_section(horse, events, [])
    assert sec is not None
    assert any("successful farrier" in line and "James K." in line for line in sec["lines"])


def test_weekly_compose_caps_at_three_lines():
    horse = {"id": "h1", "name": "Halo"}
    events = [
        {"category": "medication", "event_type": "task.completed", "payload_snapshot": {}},
        {"category": "farrier", "event_type": "task.completed",
         "payload_snapshot": {"farrier_name": "K."}},
        {"category": "vet", "event_type": "task.completed",
         "payload_snapshot": {"title": "Routine check"}},
        {"category": "rehab", "event_type": "task.completed", "payload_snapshot": {}},
    ]
    sec = _weekly_compose_section(horse, events, [])
    assert sec is not None
    assert len(sec["lines"]) <= 3


def test_iso_week_key_format():
    dt = datetime(2026, 2, 22, 18, 0, tzinfo=timezone.utc)  # Sunday
    key = _iso_week_key(dt)
    assert key.startswith("2026-W")
    assert len(key) == len("2026-W08")


def test_render_weekly_html_contains_calm_eyebrow_and_section():
    payload = {
        "kind": "weekly",
        "sections": [{"horse_id": "h1", "horse_name": "Halo",
                      "lines": ["Halo completed all scheduled medications this week."]}],
        "upcoming_count": 2,
        "updates_count": 2,
    }
    html = render_weekly_recap_html(payload)
    assert "Weekly Recap" in html
    assert "This week at the barn" in html
    assert "Halo" in html
    assert "Looking ahead" in html
    assert "2 upcoming care appointments" in html


def test_render_weekly_text_is_scannable():
    payload = {
        "kind": "weekly",
        "sections": [{"horse_id": "h1", "horse_name": "Halo",
                      "lines": ["Halo had a successful farrier follow-up."]}],
        "upcoming_count": 0,
        "updates_count": 1,
    }
    text = render_weekly_recap_text(payload)
    assert "This week at the barn" in text
    assert "HALO" in text
    assert "successful farrier" in text


# -------- API endpoints (live) --------

def test_weekly_preview_endpoint_returns_payload_or_empty(owner_h):
    r = requests.post(f"{API}/notifications/weekly-recap/preview", headers=owner_h, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "empty" in data
    if not data["empty"]:
        assert data["payload"]["kind"] == "weekly"
        assert "for_week" in data["payload"]
        assert isinstance(data["payload"]["sections"], list)
        # All composed lines should be short and calm
        for sec in data["payload"]["sections"]:
            assert len(sec["lines"]) <= 3


def test_weekly_send_me_owner_ok(owner_h):
    r = requests.post(f"{API}/notifications/weekly-recap/send-me", headers=owner_h, timeout=30)
    assert r.status_code == 200
    # Either sent or no_updates — both are acceptable, never 5xx
    data = r.json()
    assert "sent" in data


def test_weekly_send_me_non_owner_forbidden():
    r = requests.post(f"{API}/auth/login", json=GROOM, timeout=30)
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    r2 = requests.post(f"{API}/notifications/weekly-recap/send-me", headers=h, timeout=30)
    assert r2.status_code == 403


def test_weekly_admin_run_now(admin_h):
    r = requests.post(f"{API}/admin/weekly-recap/run-now", headers=admin_h, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data.get("kind") == "weekly"
    assert "for_week" in data
    assert "sent" in data and "skipped" in data
