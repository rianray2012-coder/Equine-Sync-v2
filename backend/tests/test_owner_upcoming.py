"""Phase 7D-2 — owner-scoped upcoming visibility (live integration).

Proves GET /api/owner/upcoming:
  * owner sees only their own horses' upcoming vet/farrier/rehab within 14 days,
    soonest first
  * excludes: other horses, past tasks, completed/cancelled tasks, non-appointment
    categories (medication/feed/turnout), and tasks beyond the window
  * other-barn task never leaks
  * staff (non-owner) get 403

Seeds tasks directly into db.tasks; strict id teardown.
"""
import uuid
from datetime import datetime, timezone, timedelta

import requests

from ._owner_helpers import API, auth_headers, mongo_db
from ._test_creds import ADMIN, OWNER

OWNER_H = auth_headers(OWNER)
ADMIN_H = auth_headers(ADMIN)
DB = mongo_db()

STATE = {"tasks": [], "owned_horse": None, "other_horse": None}


def _iso(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _task(horse_id, category, days, status="scheduled", barn="primary", title=None):
    tid = "t7d2_" + uuid.uuid4().hex
    DB.tasks.insert_one({
        "id": tid, "barn_id": barn, "linked_horse_ids": [horse_id],
        "category": category, "status": status, "scheduled_at": _iso(days),
        "title": title or f"{category} visit",
    })
    STATE["tasks"].append(tid)
    return tid


def setup_module(module):
    owner = DB.users.find_one({"email": OWNER["email"]}, {"_id": 0, "id": 1})
    assert owner
    oid = owner["id"]
    STATE["owner_id"] = oid

    owned = "h7d2_owned_" + uuid.uuid4().hex
    DB.horses.insert_one({"id": owned, "barn_id": "primary", "owner_id": oid,
                          "name": "Upcoming7D2", "created_at": _iso(0)})
    STATE["owned_horse"] = owned
    other = "h7d2_other_" + uuid.uuid4().hex
    DB.horses.insert_one({"id": other, "barn_id": "primary", "owner_id": "someone-else",
                          "name": "NotOwned7D2", "created_at": _iso(0)})
    STATE["other_horse"] = other

    # Included (owned, appointment-like, within window, active):
    STATE["rehab1"] = _task(owned, "rehab", 1)
    STATE["vet3"] = _task(owned, "vet", 3)
    STATE["farrier10"] = _task(owned, "farrier", 10)
    # Excluded:
    _task(owned, "medication", 2)            # non-appointment category
    _task(owned, "vet", 20)                  # beyond window
    _task(owned, "vet", -1)                  # past
    _task(owned, "vet", 5, status="completed")  # inactive
    _task(other, "vet", 3)                   # not owned by this owner
    _task(owned, "vet", 3, barn="other")     # other barn


def teardown_module(module):
    if STATE["tasks"]:
        DB.tasks.delete_many({"id": {"$in": STATE["tasks"]}})
    DB.horses.delete_many({"id": {"$in": [STATE["owned_horse"], STATE["other_horse"]]}})


def test_owner_upcoming_scoped_sorted_and_filtered():
    r = requests.get(f"{API}/owner/upcoming", headers=OWNER_H, timeout=30)
    assert r.status_code == 200, r.text
    items = r.json()
    ids = [i["id"] for i in items]
    mine = (STATE["rehab1"], STATE["vet3"], STATE["farrier10"])
    # all three included; soonest-first relative order holds (the owner may own
    # other horses with their own upcoming tasks interleaved — that's expected).
    assert [i for i in ids if i in mine] == list(mine)
    # owner-safe whitelist — only expected keys; horse name resolved for mine
    mine_items = [i for i in items if i["id"] in mine]
    for it in mine_items:
        assert set(it.keys()) == {"id", "category", "title", "scheduled_at", "horse_id", "horse_name"}
        assert it["horse_id"] == STATE["owned_horse"]
    # every returned item is an appointment-like category
    assert all(i["category"] in ("vet", "farrier", "rehab") for i in items)


def test_owner_upcoming_excludes_other_and_past():
    ids = [i["id"] for i in requests.get(f"{API}/owner/upcoming", headers=OWNER_H, timeout=30).json()]
    # none of the excluded categories/horses/barn/past/completed appear
    for tid in STATE["tasks"]:
        if tid not in (STATE["rehab1"], STATE["vet3"], STATE["farrier10"]):
            assert tid not in ids


def test_staff_cannot_use_owner_upcoming():
    r = requests.get(f"{API}/owner/upcoming", headers=ADMIN_H, timeout=30)
    assert r.status_code == 403
    assert r.json()["detail"] == "This view is for horse owners"
