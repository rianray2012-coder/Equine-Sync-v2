"""Unified Task Engine — integration tests (sync, matches repo convention)."""
import os
import uuid
import requests
import pytest
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://herd-hub-19.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {
    "email": os.environ.get("TEST_ADMIN_EMAIL", "admin@equinesync.com"),
    "password": os.environ.get("TEST_ADMIN_PASSWORD", "demo1234"),
}
OWNER = {
    "email": os.environ.get("TEST_OWNER_EMAIL", "owner@equinesync.com"),
    "password": os.environ.get("TEST_OWNER_PASSWORD", "demo1234"),
}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def owner_token():
    r = requests.post(f"{API}/auth/login", json=OWNER, timeout=30)
    assert r.status_code == 200
    return r.json()["token"]


def _new_task(H):
    horse_id = requests.get(f"{API}/horses", headers=H, timeout=30).json()[0]["id"]
    sched = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    r = requests.post(f"{API}/tasks", headers=H, timeout=30, json={
        "category": "custom", "title": f"t-{uuid.uuid4()}",
        "linked_horse_ids": [horse_id], "scheduled_at": sched,
    })
    assert r.status_code == 200, r.text
    return r.json()["task"]["id"], horse_id


def test_templates_listed(H):
    r = requests.get(f"{API}/task-templates", headers=H, timeout=30)
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1


def test_today_returns_groups(H):
    r = requests.get(f"{API}/tasks/today", headers=H, timeout=30)
    assert r.status_code == 200
    keys = ["overdue_critical", "due_now", "upcoming_next_4h",
            "later_today", "completed_today", "informational"]
    for k in keys:
        assert k in r.json()["groups"]
        assert k in r.json()["counts"]


def test_complete_idempotent(H):
    tid, _ = _new_task(H)
    ccid = f"ccid-{uuid.uuid4()}"
    r1 = requests.post(f"{API}/tasks/{tid}/complete", headers=H, timeout=30,
                       json={"client_completion_id": ccid, "outcome": "done"})
    assert r1.status_code == 200, r1.text
    assert r1.json()["deduped"] is False
    r2 = requests.post(f"{API}/tasks/{tid}/complete", headers=H, timeout=30,
                       json={"client_completion_id": ccid, "outcome": "done"})
    assert r2.status_code == 200
    assert r2.json()["deduped"] is True


def test_concurrent_completion_appends_note(H):
    tid, _ = _new_task(H)
    requests.post(f"{API}/tasks/{tid}/complete", headers=H, timeout=30,
                  json={"client_completion_id": f"ccid-a-{uuid.uuid4()}", "outcome": "done"})
    r2 = requests.post(f"{API}/tasks/{tid}/complete", headers=H, timeout=30,
                       json={"client_completion_id": f"ccid-b-{uuid.uuid4()}", "outcome": "done"})
    assert r2.status_code == 200
    assert r2.json().get("duplicate_note_appended") is True


def test_bulk_complete(H):
    ids = []
    for _ in range(3):
        tid, _ = _new_task(H)
        ids.append(tid)
    payload = {
        "items": [{"task_id": t, "client_completion_id": f"b-{t[:8]}", "outcome": "done"} for t in ids],
        "shared_note": "bulk test",
    }
    r = requests.post(f"{API}/tasks/bulk-complete", headers=H, timeout=30, json=payload)
    assert r.status_code == 200
    assert r.json()["succeeded"] == 3


def test_skip_and_refuse(H):
    tid, _ = _new_task(H)
    r = requests.post(f"{API}/tasks/{tid}/skip", headers=H, timeout=30,
                     json={"client_completion_id": f"sk-{uuid.uuid4()}",
                           "reason": "weather", "refused": False})
    assert r.status_code == 200
    assert r.json()["completion"]["outcome"] == "skipped"

    tid2, _ = _new_task(H)
    r2 = requests.post(f"{API}/tasks/{tid2}/skip", headers=H, timeout=30,
                      json={"client_completion_id": f"rf-{uuid.uuid4()}", "refused": True})
    assert r2.status_code == 200
    assert r2.json()["completion"]["outcome"] == "refused"


def test_void_completion(H):
    tid, _ = _new_task(H)
    requests.post(f"{API}/tasks/{tid}/complete", headers=H, timeout=30,
                  json={"client_completion_id": f"v-{uuid.uuid4()}", "outcome": "done"})
    r = requests.post(f"{API}/tasks/{tid}/void", headers=H, timeout=30,
                     json={"reason": "test undo"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_horse_timeline(H):
    horses = requests.get(f"{API}/horses", headers=H, timeout=30).json()
    r = requests.get(f"{API}/horses/{horses[0]['id']}/timeline", headers=H, timeout=30)
    assert r.status_code == 200
    assert "items" in r.json()


def test_owner_timeline_visibility(H, owner_token):
    horses = requests.get(f"{API}/horses", headers=H, timeout=30).json()
    hid = horses[0]["id"]
    r = requests.get(f"{API}/horses/{hid}/timeline",
                      headers={"Authorization": f"Bearer {owner_token}"}, timeout=30)
    assert r.status_code == 200
    visible = {"medication", "farrier", "vet", "rehab", "feed"}
    for ev in r.json()["items"]:
        if ev.get("category"):
            assert ev["category"] in visible


def test_template_crud_lifecycle(H):
    r = requests.post(f"{API}/task-templates", headers=H, timeout=30, json={
        "category": "feed", "title": f"crud-{uuid.uuid4()}",
        "rrule": "FREQ=DAILY",
        "dtstart": datetime.now(timezone.utc).isoformat(),
        "priority": "standard",
    })
    assert r.status_code == 200, r.text
    tpl = r.json()["template"]
    assert r.json()["materialized"] >= 1

    r2 = requests.patch(f"{API}/task-templates/{tpl['id']}", headers=H, timeout=30, json={
        "category": "feed", "title": tpl["title"] + " (edited)",
        "rrule": "FREQ=DAILY", "dtstart": tpl["dtstart"], "priority": "critical",
    })
    assert r2.status_code == 200

    r3 = requests.delete(f"{API}/task-templates/{tpl['id']}", headers=H, timeout=30)
    assert r3.status_code == 200


def test_analytics_summary(H):
    r = requests.get(f"{API}/tasks/analytics/summary?days=30", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "completions" in d
    assert "currently_overdue" in d
    assert "by_event_category" in d


def test_invalid_rrule_rejected(H):
    r = requests.post(f"{API}/task-templates", headers=H, timeout=30, json={
        "category": "feed", "title": "bad-rrule",
        "rrule": "NOT;A;VALID;RRULE",
        "dtstart": datetime.now(timezone.utc).isoformat(),
    })
    assert r.status_code in (400, 422)


def test_skip_idempotent(H):
    tid, _ = _new_task(H)
    ccid = f"sk-idem-{uuid.uuid4()}"
    r1 = requests.post(f"{API}/tasks/{tid}/skip", headers=H, timeout=30,
                      json={"client_completion_id": ccid, "reason": "x", "refused": False})
    assert r1.status_code == 200
    r2 = requests.post(f"{API}/tasks/{tid}/skip", headers=H, timeout=30,
                      json={"client_completion_id": ccid, "reason": "x", "refused": False})
    assert r2.status_code == 200
    assert r2.json()["deduped"] is True
