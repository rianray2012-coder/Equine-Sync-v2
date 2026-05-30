"""Unified Task Engine — integration tests (sync, matches repo convention)."""
import os
import uuid
import requests
import pytest
from datetime import datetime, timezone, timedelta

from ._test_creds import ADMIN, OWNER

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://barn-ops-preview.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


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


# ────────────────────────────────────────────────────────────────────────────
# Phase-B: Vet/Farrier completion loop
# ────────────────────────────────────────────────────────────────────────────

def _ad_hoc(H, category, title_prefix, payload=None, follow_up_field=None):
    horse_r = requests.get(f"{API}/horses", headers=H, timeout=30)
    horse_id = horse_r.json()[0]["id"]
    sched = datetime.now(timezone.utc).isoformat()
    body = {
        "category": category,
        "title": f"{title_prefix}-{uuid.uuid4()}",
        "linked_horse_ids": [horse_id],
        "scheduled_at": sched,
    }
    if payload:
        body["payload"] = payload
    r = requests.post(f"{API}/tasks", headers=H, timeout=30, json=body)
    assert r.status_code == 200, r.text
    return r.json()["task"]["id"], horse_id


def test_vet_completion_writes_vet_record(H):
    tid, horse_id = _ad_hoc(H, "vet", "vet")
    ccid = f"vet-{uuid.uuid4()}"
    follow_up = (datetime.now(timezone.utc) + timedelta(days=42)).date().isoformat()
    r = requests.post(f"{API}/tasks/{tid}/complete", headers=H, timeout=30, json={
        "client_completion_id": ccid,
        "outcome": "done",
        "payload_actual": {
            "vet_name": "Dr. Maren",
            "type": "vaccine",
            "cost": 185,
            "notes": "Booster — uneventful",
            "follow_up_due": follow_up,
        },
    })
    assert r.status_code == 200
    # The newly-written vet_record should appear in /vet-records for this horse
    recs = requests.get(f"{API}/vet-records?horse_id={horse_id}",
                        headers=H, timeout=30).json()
    engine_rows = [v for v in recs if v.get("source") == "task_engine" and v.get("linked_task_id") == tid]
    assert engine_rows, f"No vet_record written for task {tid}"
    rec = engine_rows[0]
    assert rec["vet_name"] == "Dr. Maren"
    assert rec["cost"] == 185
    assert rec["follow_up_due"] == follow_up


def test_vet_completion_auto_schedules_follow_up(H):
    tid, horse_id = _ad_hoc(H, "vet", "vetfu")
    follow_up = (datetime.now(timezone.utc) + timedelta(days=21)).date().isoformat()
    r = requests.post(f"{API}/tasks/{tid}/complete", headers=H, timeout=30, json={
        "client_completion_id": f"vetfu-{uuid.uuid4()}",
        "outcome": "done",
        "payload_actual": {
            "vet_name": "Dr. Maren", "cost": 0,
            "follow_up_due": follow_up,
        },
    })
    assert r.status_code == 200
    # Search forward for a follow-up task on that horse within the next 30 days
    start = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=22)).isoformat()
    qs = (f"category=vet&horse_id={horse_id}"
          f"&start={start}&end={end}")
    listing = requests.get(f"{API}/tasks?{qs}", headers=H, timeout=30).json()
    titles = [t["title"] for t in listing["items"]]
    assert any(t.startswith("Follow-up:") for t in titles), f"No follow-up scheduled, got: {titles}"


def test_farrier_completion_writes_history_row(H):
    tid, horse_id = _ad_hoc(H, "farrier", "shoeing")
    ccid = f"far-{uuid.uuid4()}"
    next_visit = (datetime.now(timezone.utc) + timedelta(weeks=6)).date().isoformat()
    r = requests.post(f"{API}/tasks/{tid}/complete", headers=H, timeout=30, json={
        "client_completion_id": ccid,
        "outcome": "done",
        "payload_actual": {
            "farrier_name": "Jordan A.",
            "shoes_on": ["fronts"],
            "trim_notes": "Slight flare on the off fore",
            "cost": 135,
            "next_visit_due": next_visit,
        },
    })
    assert r.status_code == 200
    hist = requests.get(f"{API}/farrier-history?horse_id={horse_id}",
                        headers=H, timeout=30).json()
    rows = [h for h in hist if h.get("linked_task_id") == tid]
    assert rows, "No farrier_history row written"
    row = rows[0]
    assert row["farrier_name"] == "Jordan A."
    assert row["cost"] == 135
    assert "fronts" in (row.get("shoes_on") or [])


def test_event_payload_carries_engine_enrichments(H):
    tid, horse_id = _ad_hoc(H, "vet", "vetev")
    r = requests.post(f"{API}/tasks/{tid}/complete", headers=H, timeout=30, json={
        "client_completion_id": f"vetev-{uuid.uuid4()}",
        "outcome": "done",
        "payload_actual": {"vet_name": "Dr. K", "cost": 90},
    })
    assert r.status_code == 200
    tl = requests.get(f"{API}/horses/{horse_id}/timeline", headers=H, timeout=30).json()
    matches = [ev for ev in tl["items"]
               if ev.get("task_id") == tid and ev.get("event_type") == "task.completed"]
    assert matches, "Expected task.completed event not found in timeline"
    snap = matches[0].get("payload_snapshot") or {}
    assert snap.get("vet_name") == "Dr. K"
    assert snap.get("cost") == 90
    assert snap.get("vet_record_id"), "vet_record_id should ride along on the event"
