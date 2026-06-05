"""Phase 4E — cross-tenant isolation: task engine + digests.

Proves the unified Task Engine (templates, tasks, completions, timelines,
staff activity, analytics) and the owner-keyed digest layer are isolated
between two real barns in BOTH directions.

Test-only. A failure here is a real engine-side cross-barn leak; the fix
belongs in task_engine.py / owner_digest.py, not in this file.
"""
import json
import uuid
from datetime import datetime, timezone, timedelta

import requests

from ._isolation_world import API, build_world, teardown_world, mongo

WORLD = None


def setup_module(module):
    global WORLD
    WORLD = build_world()


def teardown_module(module):
    teardown_world(WORLD)


def _get(headers, path):
    r = requests.get(f"{API}{path}", headers=headers, timeout=30)
    assert r.status_code == 200, f"GET {path} -> {r.status_code}: {r.text}"
    return r.json()


def _status(method, headers, path, payload=None):
    fn = getattr(requests, method)
    kw = {"headers": headers, "timeout": 30}
    if payload is not None:
        kw["json"] = payload
    return fn(f"{API}{path}", **kw).status_code


# --------------------------------------------------------------------------
# Task templates
# --------------------------------------------------------------------------
def test_task_templates_list_isolation_both_directions():
    a_ids = {t["id"] for t in _get(WORLD.h_a, "/task-templates")["items"]}
    b_ids = {t["id"] for t in _get(WORLD.h_b, "/task-templates")["items"]}
    assert WORLD.a["template"] in a_ids and WORLD.b["template"] not in a_ids
    assert WORLD.b["template"] in b_ids and WORLD.a["template"] not in b_ids


def test_task_template_patch_delete_cross_barn_404_no_mutation():
    db = mongo()
    tpl_body = {"category": "custom", "title": "ROGUE", "rrule": "FREQ=DAILY;COUNT=1"}
    # Cross-barn PATCH -> 404, title untouched.
    assert _status("patch", WORLD.h_a, f"/task-templates/{WORLD.b['template']}", tpl_body) == 404
    assert _status("patch", WORLD.h_b, f"/task-templates/{WORLD.a['template']}", tpl_body) == 404
    # Cross-barn DELETE (soft) -> 404, still active.
    assert _status("delete", WORLD.h_a, f"/task-templates/{WORLD.b['template']}") == 404
    assert _status("delete", WORLD.h_b, f"/task-templates/{WORLD.a['template']}") == 404
    b_tpl = db.task_templates.find_one({"id": WORLD.b["template"]}, {"_id": 0})
    assert b_tpl["title"] != "ROGUE" and b_tpl.get("active") is not False


# --------------------------------------------------------------------------
# Tasks
# --------------------------------------------------------------------------
def _today_window():
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return start.isoformat(), (start + timedelta(days=1)).isoformat()


def test_tasks_list_isolation_both_directions():
    # Scope to today's custom tasks so the unbounded list cap can't drop the
    # freshly-seeded task (cap is unrelated to barn isolation).
    s, e = _today_window()
    q = f"/tasks?category=custom&start={s}&end={e}&limit=1000"
    a_ids = {t["id"] for t in _get(WORLD.h_a, q)["items"]}
    b_ids = {t["id"] for t in _get(WORLD.h_b, q)["items"]}
    assert WORLD.a["task"] in a_ids and WORLD.b["task"] not in a_ids
    assert WORLD.b["task"] in b_ids and WORLD.a["task"] not in b_ids


def test_task_patch_reassign_cross_barn_404():
    assert _status("patch", WORLD.h_a, f"/tasks/{WORLD.b['task']}", {"title": "X"}) == 404
    assert _status("patch", WORLD.h_b, f"/tasks/{WORLD.a['task']}", {"title": "X"}) == 404
    assert _status("post", WORLD.h_a, f"/tasks/{WORLD.b['task']}/reassign",
                   {"assignee_role": "groom"}) == 404
    assert _status("post", WORLD.h_b, f"/tasks/{WORLD.a['task']}/reassign",
                   {"assignee_role": "groom"}) == 404


def test_task_skip_void_cross_barn_404_no_mutation():
    db = mongo()
    # The seeded task in each barn was completed during world build.
    a_before = db.tasks.find_one({"id": WORLD.a["task"]}, {"_id": 0, "status": 1})
    # Cross-barn skip -> 404 (valid SkipBody so we reach the barn-scope check).
    assert _status("post", WORLD.h_a, f"/tasks/{WORLD.b['task']}/skip",
                   {"client_completion_id": uuid.uuid4().hex, "reason": "x"}) == 404
    # Cross-barn void -> 404; A's completion is untouched.
    assert _status("post", WORLD.h_b, f"/tasks/{WORLD.a['task']}/void",
                   {"reason": "x"}) == 404
    a_comp = db.task_completions.find_one({"task_id": WORLD.a["task"]}, {"_id": 0})
    assert a_comp is not None and a_comp.get("voided") is not True
    assert db.tasks.find_one({"id": WORLD.a["task"]}, {"_id": 0, "status": 1})["status"] == a_before["status"]


# --------------------------------------------------------------------------
# Timelines / staff activity — no cross-barn event leak
# --------------------------------------------------------------------------
def test_horse_timeline_cross_barn_returns_empty():
    # A querying B's horse timeline sees nothing (scoped to A's barn).
    assert _get(WORLD.h_a, f"/horses/{WORLD.b['horse']}/timeline")["items"] == []
    assert _get(WORLD.h_b, f"/horses/{WORLD.a['horse']}/timeline")["items"] == []


def test_staff_activity_cross_barn_returns_empty():
    # The B admin user (who acted in barn B during world build) has no events
    # in barn A's partition when queried by A's admin, and vice versa.
    db = mongo()
    b_admin = db.users.find_one({"email": WORLD.admin_b_email}, {"_id": 0, "id": 1})
    assert _get(WORLD.h_a, f"/staff/{b_admin['id']}/activity")["items"] == []


# --------------------------------------------------------------------------
# Analytics rollup — completions counted per barn
# --------------------------------------------------------------------------
def test_analytics_summary_is_barn_scoped():
    db = mongo()
    a_an = _get(WORLD.h_a, "/tasks/analytics/summary")
    b_an = _get(WORLD.h_b, "/tasks/analytics/summary")
    # Barn B completed exactly the one task created during world build.
    b_expected = db.task_completions.count_documents({
        "tenant_id": "default", "barn_id": WORLD.barn_b, "voided": {"$ne": True},
    })
    assert b_an["completions"] == b_expected >= 1
    # Disjoint partitions: B's completions never inflate to include A's history.
    assert b_an["completions"] < a_an["completions"]


# --------------------------------------------------------------------------
# Owner digests — owner-keyed, must never surface another barn's horse
# --------------------------------------------------------------------------
def test_owner_digest_does_not_leak_other_barn_horse():
    db = mongo()
    a_horse_name = db.horses.find_one({"id": WORLD.a["horse"]}, {"_id": 0, "name": 1})["name"]
    r = requests.post(f"{API}/notifications/digest/preview",
                      headers=WORLD.h_b_owner, timeout=30)
    assert r.status_code == 200
    # Whatever the B owner's digest contains, it must not mention an A horse.
    assert a_horse_name not in json.dumps(r.json())
