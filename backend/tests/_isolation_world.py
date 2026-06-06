"""Phase 4E — shared two-barn world for cross-tenant isolation tests.

Builds a fully-populated second barn (Barn B) alongside the founder barn
(Barn A = "primary") and seeds parallel domain data in BOTH barns via the real
API (as the respective barn admin), with direct DB inserts only for engine
follow-ups. Strict teardown removes every Barn B document by ``barn_id`` and
every tracked Barn A test id.

Usage (module-scoped):

    from ._isolation_world import build_world, teardown_world

    WORLD = None
    def setup_module(module):
        global WORLD
        WORLD = build_world()
    def teardown_module(module):
        teardown_world(WORLD)
"""
import os
import pathlib
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import pymongo
import requests

from ._test_creds import ADMIN

PW = "Passw0rd!9"

# Every collection that may hold a Barn B document — teardown sweeps all of them.
_B_COLLECTIONS = [
    "horses", "owners", "riders", "medications", "medication_logs", "vet_records",
    "farrier_history", "injuries", "wellness", "lessons", "training", "messages",
    "service_requests", "incidents", "invoices", "locations", "feed_templates",
    "inventory", "recurring_schedules", "staff_invites", "invites",
    "onboarding_progress", "tasks", "task_templates", "task_completions",
    "task_events", "events", "users",
]


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


def mongo():
    url = os.environ.get("MONGO_URL") or _read_env("MONGO_URL", 1, ".env")
    name = os.environ.get("DB_NAME") or _read_env("DB_NAME", 1, ".env")
    return pymongo.MongoClient(url)[name]


def login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _today_at(hour):
    return datetime.now(timezone.utc).replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()


def detail(resp):
    try:
        return resp.json().get("detail")
    except Exception:
        return None


class World:
    def __init__(self):
        self.barn_a = "primary"
        self.barn_b = None
        self.h_a = None                # founder/primary admin headers
        self.h_b = None                # barn B admin headers
        self.h_b_owner = None          # barn B horse_owner headers
        self.admin_b_email = None
        self.owner_b_email = None
        self.b_owner_user_id = None
        self.a = {}                    # label -> id (Barn A seeded entities)
        self.b = {}                    # label -> id (Barn B seeded entities)
        self._a_registry = defaultdict(list)   # collection -> [ids] (primary cleanup)


def _post(headers, path, payload):
    r = requests.post(f"{API}{path}", headers=headers, json=payload, timeout=30)
    assert r.status_code in (200, 201), f"POST {path} -> {r.status_code}: {r.text}"
    return r.json()


def _seed_barn(world, headers, label):
    """Seed a parallel set of domain entities for one barn. Returns {label: id}."""
    reg = world._a_registry if label == "a" else None
    ids = {}

    def track(coll, _id):
        if reg is not None:
            reg[coll].append(_id)
        return _id

    suffix = uuid.uuid4().hex[:8]
    horse = _post(headers, "/horses", {"name": f"{label}-Horse-{suffix}"})
    ids["horse"] = track("horses", horse["id"])

    owner = _post(headers, "/owners", {"full_name": f"{label}-Owner-{suffix}",
                                       "email": f"{label}owner_{suffix}@ex.com"})
    ids["owner"] = track("owners", owner["id"])

    med = _post(headers, "/medications", {"horse_id": ids["horse"], "name": "Bute",
                                          "dosage": "1g", "frequency": "daily"})
    ids["medication"] = track("medications", med["id"])

    vet = _post(headers, "/vet-records", {"horse_id": ids["horse"], "type": "exam",
                                          "title": "Annual", "date": "2026-01-15"})
    ids["vet"] = track("vet_records", vet["id"])

    inj = _post(headers, "/injuries", {"horse_id": ids["horse"], "title": "Strain"})
    ids["injury"] = track("injuries", inj["id"])

    well = _post(headers, "/wellness", {"horse_id": ids["horse"]})
    ids["wellness"] = track("wellness", well["id"])

    lesson = _post(headers, "/lessons", {"rider_id": "none", "horse_id": ids["horse"],
                                         "start_time": _today_at(10)})
    ids["lesson"] = track("lessons", lesson["id"])

    training = _post(headers, "/training", {"horse_id": ids["horse"], "date": "2026-02-01"})
    ids["training"] = track("training", training["id"])

    msg = _post(headers, "/messages", {"subject": "Hi", "body": "msg"})
    ids["message"] = track("messages", msg["id"])

    sr = _post(headers, "/service-requests", {"horse_id": ids["horse"], "type": "vet",
                                              "details": "check"})
    ids["sr"] = track("service_requests", sr["id"])

    inc = _post(headers, "/incidents", {"horse_id": ids["horse"], "type": "fall",
                                        "title": "Slip", "description": "minor",
                                        "occurred_at": _today_at(8)})
    ids["incident"] = track("incidents", inc["id"])

    inv = _post(headers, "/invoices", {"owner_id": ids["owner"], "horse_id": ids["horse"],
                                       "items": [{"label": "board", "amount": 100}],
                                       "total": 100.0, "due_date": "2026-03-01"})
    ids["invoice"] = track("invoices", inv["id"])

    loc = _post(headers, "/locations", {"type": "stall", "name": f"{label}-Stall-{suffix}"})
    ids["location"] = track("locations", loc["id"])

    ftpl = _post(headers, "/feed-templates", {"meal": "AM", "hay_type": "timothy"})
    ids["feedtpl"] = track("feed_templates", ftpl["id"])

    invn = _post(headers, "/inventory", {"category": "feed", "name": f"{label}-Grain", "unit": "lbs"})
    ids["inventory"] = track("inventory", invn["id"])

    rs = _post(headers, "/recurring-schedules", {"type": "feed", "name": f"{label}-Sched"})
    ids["rs"] = track("recurring_schedules", rs["id"])

    si = _post(headers, "/staff-invites", {"email": f"{label}staff_{suffix}@ex.com",
                                           "role": "groom"})
    ids["staffinvite"] = track("staff_invites", si["id"])

    # Task engine — template + ad-hoc task; complete the task → completion + events.
    tpl = _post(headers, "/task-templates", {
        "category": "custom", "title": f"{label}-Tpl-{suffix}",
        "rrule": "FREQ=DAILY;COUNT=1", "dtstart": _today_at(7),
        "window_minutes_before": 30, "window_minutes_after": 120,
    })
    tpl_doc = tpl.get("template", tpl)
    ids["template"] = track("task_templates", tpl_doc["id"])

    task = _post(headers, "/tasks", {"category": "custom", "title": f"{label}-Task-{suffix}",
                                     "scheduled_at": _today_at(9)})
    task_doc = task.get("task", task)
    ids["task"] = track("tasks", task_doc["id"])
    _post(headers, f"/tasks/{ids['task']}/complete",
          {"client_completion_id": uuid.uuid4().hex, "outcome": "done"})

    return ids


def build_world() -> World:
    w = World()
    w.h_a = login(ADMIN["email"], ADMIN["password"])

    # 1. Founder provisions Barn B + its admin.
    w.admin_b_email = f"barnb_admin_{uuid.uuid4().hex[:10]}@ex.com"
    barn_resp = _post(w.h_a, "/barns", {
        "name": "Isolation Barn B " + uuid.uuid4().hex[:6],
        "admin_email": w.admin_b_email, "admin_full_name": "Barn B Admin",
        "admin_password": PW,
    })
    w.barn_b = barn_resp["barn"]["id"]
    w.h_b = login(w.admin_b_email, PW)

    # 2. Barn B admin invites a horse_owner into B (for digest assertions).
    w.owner_b_email = f"barnb_owner_{uuid.uuid4().hex[:10]}@ex.com"
    inv = _post(w.h_b, "/invites", {"email": w.owner_b_email, "role": "horse_owner",
                                    "full_name": "Barn B Owner"})
    token = (inv.get("dev_accept_url") or "").split("token=")[-1]
    assert token, f"no dev accept token: {inv}"
    accept = _post(None_headers(), "/invites/accept", {"token": token, "password": PW})
    w.b_owner_user_id = accept["user"]["id"]
    w.h_b_owner = {"Authorization": f"Bearer {accept['token']}"}

    # A B-owned horse linked to the B owner (digest is owner-keyed by owner_id).
    owner_horse = _post(w.h_b, "/horses", {"name": "B-OwnerHorse-" + uuid.uuid4().hex[:6],
                                           "owner_id": w.b_owner_user_id})
    w.b["owner_horse"] = owner_horse["id"]

    # 3. Seed parallel domain data in both barns.
    w.a = _seed_barn(w, w.h_a, "a")
    w.b.update(_seed_barn(w, w.h_b, "b"))
    return w


def None_headers():
    # accept is unauthenticated (token-based) — no Authorization header.
    return {}


def teardown_world(w: World):
    if w is None:
        return
    db = mongo()
    # Barn B: sweep every collection by barn_id, plus the barn doc + B users.
    if w.barn_b:
        for coll in _B_COLLECTIONS:
            db[coll].delete_many({"barn_id": w.barn_b})
        db.barn.delete_many({"id": w.barn_b})
        db.users.delete_many({"barn_id": w.barn_b})
        db.invites.delete_many({"barn_id": w.barn_b})
    # B-side engine completions/events are keyed by barn_id (already swept). Also
    # remove B users by email in case any lacked barn_id.
    for email in [w.admin_b_email, w.owner_b_email]:
        if email:
            db.users.delete_many({"email": email})
    # Barn A (primary) test entities — delete each tracked id from its collection.
    for coll, ids in w._a_registry.items():
        if ids:
            db[coll].delete_many({"id": {"$in": ids}})
    # A-side completions + events for the A task we completed.
    a_task = w.a.get("task")
    if a_task:
        db.task_completions.delete_many({"task_id": a_task})
        db.task_events.delete_many({"task_id": a_task})
    # A-side TEMPLATE fan-out: the API-created A template materialized future
    # tasks (and emitted task_events). Deleting only the template row above would
    # leave those orphaned in the primary barn — strict teardown removes them too.
    a_tpl_ids = w._a_registry.get("task_templates", [])
    if a_tpl_ids:
        mat_ids = [t["id"] for t in db.tasks.find(
            {"template_id": {"$in": a_tpl_ids}, "barn_id": w.barn_a}, {"_id": 0, "id": 1},
        )]
        if mat_ids:
            db.task_events.delete_many({"task_id": {"$in": mat_ids}})
            db.task_completions.delete_many({"task_id": {"$in": mat_ids}})
        db.tasks.delete_many({"template_id": {"$in": a_tpl_ids}, "barn_id": w.barn_a})
