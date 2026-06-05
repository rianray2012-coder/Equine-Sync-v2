"""Phase 4B-7 — task engine + media reconciliation barn scoping (live integration).

Strategy A: barn_id is added additively; tenant_id stays "default". Proves:
- the startup migration stamped barn_id="primary" on all engine docs;
- engine writes (templates, ad-hoc tasks, completions, events, vet/farrier
  records, follow-ups) stamp barn_id;
- every by-id task/template/action on a cross-barn doc returns 404 with no
  mutation / no completion+event written;
- list/read endpoints exclude other-barn rows;
- dashboard task counts, analytics funnel, and vet/farrier reads are barn-scoped.
"""
import os
import pathlib
import uuid
from datetime import datetime, timezone, timedelta

import pymongo
import requests

from ._test_creds import ADMIN

TENANT = "default"


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


def _mongo():
    url = os.environ.get("MONGO_URL") or _read_env("MONGO_URL", 1, ".env")
    name = os.environ.get("DB_NAME") or _read_env("DB_NAME", 1, ".env")
    return pymongo.MongoClient(url)[name]


def _admin_headers():
    r = requests.post(f"{API}/auth/login",
                      json={"email": ADMIN["email"], "password": ADMIN["password"]}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _iso():
    return datetime.now(timezone.utc).isoformat()


def _today_at(hour=10):
    d = datetime.now(timezone.utc).replace(hour=hour, minute=0, second=0, microsecond=0)
    return d.isoformat()


def _seed_other_task(db, **over):
    doc = {
        "id": "ot_" + uuid.uuid4().hex, "tenant_id": TENANT, "barn_id": "other",
        "template_id": None, "category": "general", "title": "Ghost Task",
        "status": "scheduled", "scheduled_at": _today_at(),
        "window_end": _today_at(23), "linked_horse_ids": [],
        "created_at": _iso(), "updated_at": _iso(),
    }
    doc.update(over)
    db.tasks.insert_one(doc)
    return doc["id"]


# --------------------------------------------------------------------------
# 1. Migration / backfill
# --------------------------------------------------------------------------
def test_migration_stamped_all_engine_docs():
    db = _mongo()
    for coll in ["tasks", "task_templates", "task_completions", "task_events"]:
        missing = db[coll].count_documents({"barn_id": {"$exists": False}})
        assert missing == 0, f"{coll} has {missing} docs missing barn_id after migration"


# --------------------------------------------------------------------------
# 2. Engine write-stamping
# --------------------------------------------------------------------------
def test_create_template_and_task_stamp_primary():
    db = _mongo()
    H = _admin_headers()
    tpl_title = "T_" + uuid.uuid4().hex[:8]
    tr = requests.post(f"{API}/task-templates", headers=H, json={
        "category": "custom", "title": tpl_title,
        "rrule": "FREQ=DAILY;COUNT=2", "dtstart": _today_at(8),
        "window_minutes_before": 30, "window_minutes_after": 120,
    }, timeout=30)
    assert tr.status_code in (200, 201), tr.text
    tpl = tr.json().get("template", tr.json())
    tpl_id = tpl["id"]
    try:
        assert tpl.get("barn_id") == "primary", tpl
        # materialized tasks inherit barn_id
        mt = db.tasks.find_one({"template_id": tpl_id})
        if mt:
            assert mt.get("barn_id") == "primary", mt
    finally:
        db.task_templates.delete_many({"id": tpl_id})
        db.tasks.delete_many({"template_id": tpl_id})

    # ad-hoc task + its event
    cr = requests.post(f"{API}/tasks", headers=H, json={
        "category": "custom", "title": "AdHoc_" + uuid.uuid4().hex[:6],
        "scheduled_at": _today_at(9),
    }, timeout=30)
    assert cr.status_code in (200, 201), cr.text
    task = cr.json().get("task", cr.json())
    tid = task["id"]
    try:
        assert task.get("barn_id") == "primary", task
        ev = db.task_events.find_one({"task_id": tid})
        assert ev is not None and ev.get("barn_id") == "primary", ev
    finally:
        db.tasks.delete_many({"id": tid})
        db.task_events.delete_many({"task_id": tid})


def test_complete_task_stamps_completion_and_event():
    db = _mongo()
    H = _admin_headers()
    cr = requests.post(f"{API}/tasks", headers=H, json={
        "category": "custom", "title": "Complete_" + uuid.uuid4().hex[:6],
        "scheduled_at": _today_at(9),
    }, timeout=30)
    task = cr.json().get("task", cr.json())
    tid = task["id"]
    try:
        comp = requests.post(f"{API}/tasks/{tid}/complete", headers=H, json={
            "client_completion_id": uuid.uuid4().hex, "outcome": "done",
        }, timeout=30)
        assert comp.status_code == 200, comp.text
        c = db.task_completions.find_one({"task_id": tid})
        assert c is not None and c.get("barn_id") == "primary", c
        ev = db.task_events.find_one({"task_id": tid, "event_type": "task.completed"})
        assert ev is not None and ev.get("barn_id") == "primary", ev
    finally:
        db.tasks.delete_many({"id": tid})
        db.task_completions.delete_many({"task_id": tid})
        db.task_events.delete_many({"task_id": tid})


# --------------------------------------------------------------------------
# 3. By-id cross-barn → 404 / no mutation
# --------------------------------------------------------------------------
def test_cross_barn_task_actions_404_no_mutation():
    db = _mongo()
    H = _admin_headers()
    tid = _seed_other_task(db)
    try:
        # PATCH
        r = requests.patch(f"{API}/tasks/{tid}", headers=H, json={"notes": "hacked"}, timeout=30)
        assert r.status_code == 404, r.text
        # complete
        r = requests.post(f"{API}/tasks/{tid}/complete", headers=H,
                          json={"client_completion_id": uuid.uuid4().hex, "outcome": "done"}, timeout=30)
        assert r.status_code == 404, r.text
        # skip
        r = requests.post(f"{API}/tasks/{tid}/skip", headers=H,
                          json={"client_completion_id": uuid.uuid4().hex, "reason": "x"}, timeout=30)
        assert r.status_code == 404, r.text
        # void
        r = requests.post(f"{API}/tasks/{tid}/void", headers=H, json={"reason": "x"}, timeout=30)
        assert r.status_code == 404, r.text
        # reassign
        r = requests.post(f"{API}/tasks/{tid}/reassign", headers=H,
                          json={"assignee_role": "groom"}, timeout=30)
        assert r.status_code == 404, r.text
        # nothing mutated / created
        doc = db.tasks.find_one({"id": tid})
        assert doc["status"] == "scheduled" and "notes" not in doc, "cross-barn task was mutated"
        assert db.task_completions.count_documents({"task_id": tid}) == 0
        assert db.task_events.count_documents({"task_id": tid}) == 0
    finally:
        db.tasks.delete_many({"id": tid})


def test_cross_barn_template_actions_404_no_mutation():
    db = _mongo()
    H = _admin_headers()
    tpl_id = "otpl_" + uuid.uuid4().hex
    db.task_templates.insert_one({
        "id": tpl_id, "tenant_id": TENANT, "barn_id": "other", "active": True,
        "category": "general", "title": "Ghost Template", "rrule": "FREQ=DAILY;COUNT=1",
        "dtstart": _today_at(8), "created_at": _iso(),
    })
    try:
        r = requests.patch(f"{API}/task-templates/{tpl_id}", headers=H, json={
            "category": "custom", "title": "Hacked", "rrule": "FREQ=DAILY;COUNT=1",
            "dtstart": _today_at(8),
        }, timeout=30)
        assert r.status_code == 404, r.text
        r = requests.delete(f"{API}/task-templates/{tpl_id}", headers=H, timeout=30)
        assert r.status_code == 404, r.text
        doc = db.task_templates.find_one({"id": tpl_id})
        assert doc["title"] == "Ghost Template" and doc["active"] is True, "cross-barn template mutated"
    finally:
        db.task_templates.delete_many({"id": tpl_id})


# --------------------------------------------------------------------------
# 4. List/read exclusion
# --------------------------------------------------------------------------
def test_list_endpoints_exclude_other_barn():
    db = _mongo()
    H = _admin_headers()
    tid = _seed_other_task(db, category="feed")
    try:
        # GET /tasks
        r = requests.get(f"{API}/tasks", headers=H, timeout=30)
        assert r.status_code == 200
        assert tid not in [t["id"] for t in r.json().get("items", [])], "other-barn task in GET /tasks"
        # GET /tasks/today
        r = requests.get(f"{API}/tasks/today", headers=H, timeout=30)
        assert r.status_code == 200
        body = r.json()
        all_ids = [t["id"] for t in (body.get("items") or body.get("tasks") or [])]
        assert tid not in all_ids, "other-barn task in /tasks/today"
    finally:
        db.tasks.delete_many({"id": tid})


def test_horse_timeline_excludes_other_barn():
    db = _mongo()
    H = _admin_headers()
    horse_id = "ghosthorse_" + uuid.uuid4().hex[:8]
    ev_id = "oev_" + uuid.uuid4().hex
    db.task_events.insert_one({
        "id": ev_id, "tenant_id": TENANT, "barn_id": "other",
        "event_type": "task.completed", "category": "vet",
        "subject_horse_ids": [horse_id], "occurred_at": _iso(),
    })
    try:
        r = requests.get(f"{API}/horses/{horse_id}/timeline", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        assert ev_id not in [e.get("id") for e in r.json().get("items", [])]
    finally:
        db.task_events.delete_many({"id": ev_id})


# --------------------------------------------------------------------------
# 5. Vet / farrier read scoping (4B-2 deferral closed)
# --------------------------------------------------------------------------
def test_vet_and_farrier_reads_exclude_other_barn():
    db = _mongo()
    H = _admin_headers()
    vid = "ovet_" + uuid.uuid4().hex
    fid = "ofar_" + uuid.uuid4().hex
    db.vet_records.insert_one({"id": vid, "barn_id": "other", "horse_id": "h1",
                               "date": "2026-01-01", "created_at": _iso()})
    db.farrier_history.insert_one({"id": fid, "barn_id": "other", "horse_id": "h1",
                                   "date": "2026-01-01", "created_at": _iso()})
    try:
        rv = requests.get(f"{API}/vet-records", headers=H, timeout=30)
        assert rv.status_code == 200
        assert vid not in [r.get("id") for r in rv.json()], "other-barn vet record leaked"
        rf = requests.get(f"{API}/farrier-history", headers=H, timeout=30)
        assert rf.status_code == 200
        assert fid not in [r.get("id") for r in rf.json()], "other-barn farrier record leaked"
    finally:
        db.vet_records.delete_many({"id": vid})
        db.farrier_history.delete_many({"id": fid})


# --------------------------------------------------------------------------
# 6. Dashboard task counts ignore other-barn engine docs
# --------------------------------------------------------------------------
def test_dashboard_task_counts_exclude_other_barn():
    db = _mongo()
    H = _admin_headers()
    before = requests.get(f"{API}/dashboard/summary", headers=H, timeout=30).json()
    fid = _seed_other_task(db, category="feed")
    mid = _seed_other_task(db, category="medication")
    cid = "ocomp_" + uuid.uuid4().hex
    db.task_completions.insert_one({
        "id": cid, "tenant_id": TENANT, "barn_id": "other", "task_id": "x",
        "voided": False, "outcome": "refused", "completed_at": _iso(),
    })
    try:
        after = requests.get(f"{API}/dashboard/summary", headers=H, timeout=30).json()
        for key in ["feed_tasks_total", "feed_tasks_pending", "meds_due", "meds_missed"]:
            if key in before and key in after:
                assert after[key] == before[key], f"{key} changed by other-barn task ({before[key]}->{after[key]})"
    finally:
        db.tasks.delete_many({"id": {"$in": [fid, mid]}})
        db.task_completions.delete_many({"id": cid})


# --------------------------------------------------------------------------
# 7. Analytics onboarding-funnel barn-scoped
# --------------------------------------------------------------------------
def test_onboarding_funnel_excludes_other_barn():
    db = _mongo()
    H = _admin_headers()
    name = "onboarding.ghoststep_" + uuid.uuid4().hex[:8]
    db.events.insert_one({"id": "oe_" + uuid.uuid4().hex, "name": name,
                          "barn_id": "other", "props": {}, "at": _iso()})
    try:
        r = requests.get(f"{API}/events/onboarding-funnel", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        rows = body if isinstance(body, list) else (body.get("steps") or body.get("funnel") or [])
        names = [str(x.get("_id") or x.get("name") or x) for x in rows]
        assert name not in names, "other-barn onboarding event surfaced in funnel"
    finally:
        db.events.delete_many({"name": name})


# --------------------------------------------------------------------------
# 8. Startup order: backfill BEFORE materialize → no duplicate occurrences
# --------------------------------------------------------------------------
def test_backfill_before_materialize_no_duplicate():
    db = _mongo()
    H = _admin_headers()
    # One-occurrence template in the future (within the 14-day horizon).
    dtstart = (datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
               + timedelta(days=1)).isoformat()
    tr = requests.post(f"{API}/task-templates", headers=H, json={
        "category": "custom", "title": "Legacy_" + uuid.uuid4().hex[:8],
        "rrule": "FREQ=DAILY;COUNT=1", "dtstart": dtstart,
        "window_minutes_before": 30, "window_minutes_after": 120,
    }, timeout=30)
    assert tr.status_code in (200, 201), tr.text
    tpl_id = tr.json().get("template", tr.json())["id"]
    try:
        before = db.tasks.count_documents({"template_id": tpl_id})
        assert before == 1, f"expected 1 materialized task, got {before}"
        # Simulate a legacy DB: strip barn_id off the template + its task.
        db.task_templates.update_one({"id": tpl_id}, {"$unset": {"barn_id": ""}})
        db.tasks.update_many({"template_id": tpl_id}, {"$unset": {"barn_id": ""}})
        # The FIX: additive backfill runs BEFORE materialization at startup.
        db.task_templates.update_many({"id": tpl_id, "barn_id": {"$exists": False}},
                                      {"$set": {"barn_id": "primary"}})
        db.tasks.update_many({"template_id": tpl_id, "barn_id": {"$exists": False}},
                             {"$set": {"barn_id": "primary"}})
        # Now materialize: the barn-scoped dedup sees the (now-stamped) legacy task.
        mr = requests.post(f"{API}/tasks/materialize", headers=H, timeout=30)
        assert mr.status_code == 200, mr.text
        after = db.tasks.count_documents({"template_id": tpl_id})
        assert after == 1, f"duplicate occurrence created ({before} -> {after})"
        legacy = db.tasks.find_one({"template_id": tpl_id})
        assert legacy.get("barn_id") == "primary", "legacy task not re-stamped"
    finally:
        db.task_templates.delete_many({"id": tpl_id})
        db.tasks.delete_many({"template_id": tpl_id})


# --------------------------------------------------------------------------
# 9. Cross-barn collision: same task_id in another barn cannot affect completion
# --------------------------------------------------------------------------
def test_complete_ignores_other_barn_canonical_collision():
    db = _mongo()
    H = _admin_headers()
    cr = requests.post(f"{API}/tasks", headers=H, json={
        "category": "custom", "title": "Collide_" + uuid.uuid4().hex[:6],
        "scheduled_at": _today_at(9),
    }, timeout=30)
    tid = cr.json().get("task", cr.json())["id"]
    other_comp_id = "ocomp_" + uuid.uuid4().hex
    # A colliding "canonical" completion for the SAME task_id in another barn.
    db.task_completions.insert_one({
        "id": other_comp_id, "tenant_id": TENANT, "barn_id": "other",
        "task_id": tid, "voided": False, "outcome": "done",
        "notes": "OTHER", "completed_at": _iso(),
    })
    try:
        r = requests.post(f"{API}/tasks/{tid}/complete", headers=H, json={
            "client_completion_id": uuid.uuid4().hex, "outcome": "done",
        }, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        # Must NOT treat the other-barn completion as canonical.
        assert not body.get("duplicate_note_appended"), body
        prim = db.task_completions.find_one(
            {"task_id": tid, "barn_id": "primary"})
        assert prim is not None and prim.get("voided") is not True, "primary completion wrongly voided"
        # Other-barn completion untouched.
        other = db.task_completions.find_one({"id": other_comp_id})
        assert other["notes"] == "OTHER" and other["voided"] is False, "other-barn completion mutated"
    finally:
        db.tasks.delete_many({"id": tid})
        db.task_completions.delete_many({"task_id": tid})


def test_void_ignores_other_barn_completion_collision():
    db = _mongo()
    H = _admin_headers()
    cr = requests.post(f"{API}/tasks", headers=H, json={
        "category": "custom", "title": "VoidCollide_" + uuid.uuid4().hex[:6],
        "scheduled_at": _today_at(9),
    }, timeout=30)
    tid = cr.json().get("task", cr.json())["id"]
    # Complete it (primary canonical completion now exists).
    requests.post(f"{API}/tasks/{tid}/complete", headers=H, json={
        "client_completion_id": uuid.uuid4().hex, "outcome": "done",
    }, timeout=30)
    other_comp_id = "ocomp_" + uuid.uuid4().hex
    db.task_completions.insert_one({
        "id": other_comp_id, "tenant_id": TENANT, "barn_id": "other",
        "task_id": tid, "voided": False, "outcome": "done", "completed_at": _iso(),
    })
    try:
        r = requests.post(f"{API}/tasks/{tid}/void", headers=H, json={"reason": "test"}, timeout=30)
        assert r.status_code == 200, r.text
        # Other-barn completion must remain un-voided.
        other = db.task_completions.find_one({"id": other_comp_id})
        assert other["voided"] is False, "void mutated other-barn completion"
        prim = db.task_completions.find_one({"task_id": tid, "barn_id": "primary"})
        assert prim.get("voided") is True, "primary completion was not voided"
    finally:
        db.tasks.delete_many({"id": tid})
        db.task_completions.delete_many({"task_id": tid})

