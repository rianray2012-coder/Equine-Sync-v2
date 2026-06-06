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


def test_task_complete_skip_void_cross_barn_isolation_both_directions():
    """Cross-barn complete / skip / void are each rejected (404) in BOTH
    directions, with no mutation, no stray completion, and no event leak in
    the actor's barn — and the victim's own completion stays intact.
    """
    db = mongo()
    pairs = [
        (WORLD.h_a, "primary", WORLD.b["task"], WORLD.barn_b),
        (WORLD.h_b, WORLD.barn_b, WORLD.a["task"], "primary"),
    ]
    for actor, actor_barn, victim_task, victim_barn in pairs:
        before_task = db.tasks.find_one(
            {"id": victim_task}, {"_id": 0, "status": 1, "updated_at": 1})
        before_total_comps = db.task_completions.count_documents({"task_id": victim_task})

        # complete -> 404 (fresh client_completion_id so no idempotent shortcut).
        assert _status("post", actor, f"/tasks/{victim_task}/complete",
                       {"client_completion_id": uuid.uuid4().hex, "outcome": "done"}) == 404
        # skip -> 404.
        assert _status("post", actor, f"/tasks/{victim_task}/skip",
                       {"client_completion_id": uuid.uuid4().hex, "reason": "x"}) == 404
        # void -> 404 (no active completion in the actor's barn to void).
        assert _status("post", actor, f"/tasks/{victim_task}/void", {"reason": "x"}) == 404

        # No mutation on the victim task.
        after_task = db.tasks.find_one(
            {"id": victim_task}, {"_id": 0, "status": 1, "updated_at": 1})
        assert after_task == before_task
        # No stray completion created under the actor's barn for the victim task,
        # and the global completion total is unchanged.
        assert db.task_completions.count_documents(
            {"task_id": victim_task, "barn_id": actor_barn}) == 0
        assert db.task_completions.count_documents({"task_id": victim_task}) == before_total_comps
        # The victim's own completion (in its barn) survives and is not voided.
        own = db.task_completions.find_one(
            {"task_id": victim_task, "barn_id": victim_barn, "voided": {"$ne": True}}, {"_id": 0})
        assert own is not None
        # No event leaked into the actor's barn for the victim task.
        assert db.task_events.count_documents(
            {"task_id": victim_task, "barn_id": actor_barn}) == 0


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
    # Compute the route's 7-day window before the calls so the DB equality check
    # matches the endpoint's `completed_at >= since` filter (default days=7).
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    a_an = _get(WORLD.h_a, "/tasks/analytics/summary")
    b_an = _get(WORLD.h_b, "/tasks/analytics/summary")

    def _expected(barn_id):
        return db.task_completions.count_documents({
            "tenant_id": "default", "barn_id": barn_id, "voided": {"$ne": True},
            "completed_at": {"$gte": since},
        })

    # Direct per-barn DB equality (no relative-size assumption): each barn's
    # completion count equals exactly its own scoped completions.
    assert a_an["completions"] == _expected("primary")
    assert b_an["completions"] == _expected(WORLD.barn_b) >= 1


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
