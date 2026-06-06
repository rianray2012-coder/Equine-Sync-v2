"""Phase 7A — Owner Update model + lifecycle (live integration).

Covers the backend-only foundation of the Owner Trust Layer:
  * staff lifecycle: create draft -> publish -> archive (+ 409 state guards)
  * create input integrity (foreign horse_id -> generic 404)
  * role gates (non-staff cannot create; non-staff/non-owner cannot read)
  * owner-isolated reads (owner sees only their own horses' published,
    owner-facing updates — never drafts, internal notes, or other horses)
  * barn isolation (other-barn update never leaks)
  * high-signal audit (owner_update.published / archived, minimal metadata)

Strict teardown by captured ids (updates, horses, audit rows).
"""
import uuid
from datetime import datetime, timezone

import requests

from ._care_helpers import API, auth_headers, mongo_db
from ._test_creds import ADMIN, GROOM, OWNER

ADMIN_H = auth_headers(ADMIN)
OWNER_H = auth_headers(OWNER)
GROOM_H = auth_headers(GROOM)
DB = mongo_db()

STATE = {"updates": [], "horse_owned": None, "horse_other": None,
         "other_barn_update": None, "audit_ids": []}


def _iso():
    return datetime.now(timezone.utc).isoformat()


def setup_module(module):
    owner = DB.users.find_one({"email": OWNER["email"]}, {"_id": 0, "id": 1})
    assert owner, "owner demo account missing"
    owner_id = owner["id"]

    # A horse genuinely owned by the OWNER user (owner_id == user id), barn primary.
    hid = "ou7a_owned_" + uuid.uuid4().hex
    DB.horses.insert_one({
        "id": hid, "barn_id": "primary", "owner_id": owner_id,
        "name": "OwnedHorse7A", "breed": "T", "age": 8, "created_at": _iso(),
    })
    STATE["horse_owned"] = hid

    # A second barn-primary horse NOT owned by the OWNER user.
    other = requests.post(f"{API}/horses", headers=ADMIN_H,
                          json={"name": "NotOwned7A", "breed": "T", "age": 5}, timeout=30).json()
    STATE["horse_other"] = other["id"]


def teardown_module(module):
    if STATE["updates"]:
        DB.owner_updates.delete_many({"id": {"$in": STATE["updates"]}})
    if STATE["other_barn_update"]:
        DB.owner_updates.delete_many({"id": STATE["other_barn_update"]})
    DB.horses.delete_many({"id": STATE["horse_owned"]})
    DB.horses.delete_many({"id": STATE["horse_other"]})
    DB.audit_log.delete_many({"resource_type": "owner_update",
                              "resource_id": {"$in": STATE["updates"]}})


def _create(headers, horse_id, **kw):
    payload = {"horse_id": horse_id, "body": kw.pop("body", "Routine note."), **kw}
    return requests.post(f"{API}/owner-updates", headers=headers, json=payload, timeout=30)


# --------------------------------------------------------------------------
# Staff lifecycle: draft -> published -> archived + 409 guards
# --------------------------------------------------------------------------
def test_staff_lifecycle_and_state_guards():
    r = _create(ADMIN_H, STATE["horse_owned"], kind="routine", visibility="owner_facing")
    assert r.status_code == 200, r.text
    upd = r.json()
    STATE["updates"].append(upd["id"])
    assert upd["status"] == "draft"
    assert upd["author_user_id"] and upd["barn_id"] == "primary"
    assert upd["published_at"] is None

    # archive before publish -> 409
    a0 = requests.post(f"{API}/owner-updates/{upd['id']}/archive", headers=ADMIN_H, timeout=30)
    assert a0.status_code == 409, a0.text

    # publish (draft -> published)
    p = requests.post(f"{API}/owner-updates/{upd['id']}/publish", headers=ADMIN_H, timeout=30)
    assert p.status_code == 200, p.text
    pub = p.json()
    assert pub["status"] == "published" and pub["published_at"] and pub["published_by"]

    # re-publish -> 409 (only draft can publish)
    p2 = requests.post(f"{API}/owner-updates/{upd['id']}/publish", headers=ADMIN_H, timeout=30)
    assert p2.status_code == 409

    # archive (published -> archived, soft — row still present)
    a = requests.post(f"{API}/owner-updates/{upd['id']}/archive", headers=ADMIN_H, timeout=30)
    assert a.status_code == 200 and a.json()["status"] == "archived"
    assert DB.owner_updates.count_documents({"id": upd["id"]}) == 1  # never hard-deleted


def test_edit_only_when_draft():
    r = _create(ADMIN_H, STATE["horse_owned"], body="first")
    upd = r.json()
    STATE["updates"].append(upd["id"])
    e = requests.patch(f"{API}/owner-updates/{upd['id']}", headers=ADMIN_H,
                       json={"body": "edited"}, timeout=30)
    assert e.status_code == 200 and e.json()["body"] == "edited"

    requests.post(f"{API}/owner-updates/{upd['id']}/publish", headers=ADMIN_H, timeout=30)
    e2 = requests.patch(f"{API}/owner-updates/{upd['id']}", headers=ADMIN_H,
                        json={"body": "nope"}, timeout=30)
    assert e2.status_code == 409  # only draft can be edited


def test_create_foreign_horse_404_and_empty_body_422():
    r = _create(ADMIN_H, "does-not-exist-" + uuid.uuid4().hex)
    assert r.status_code == 404 and r.json()["detail"] == "Horse not found"
    bad = requests.post(f"{API}/owner-updates", headers=ADMIN_H,
                        json={"horse_id": STATE["horse_owned"], "body": ""}, timeout=30)
    assert bad.status_code == 422


# --------------------------------------------------------------------------
# Role gates
# --------------------------------------------------------------------------
def test_owner_and_groom_cannot_create():
    ro = _create(OWNER_H, STATE["horse_owned"])
    assert ro.status_code == 403 and "manage owner updates" in ro.json()["detail"]
    rg = _create(GROOM_H, STATE["horse_owned"])
    assert rg.status_code == 403


def test_groom_cannot_read_list():
    r = requests.get(f"{API}/owner-updates", headers=GROOM_H, timeout=30)
    assert r.status_code == 403 and "view owner updates" in r.json()["detail"]


# --------------------------------------------------------------------------
# Owner-isolated reads
# --------------------------------------------------------------------------
def test_owner_sees_only_published_owner_facing_for_own_horses():
    # published owner-facing on OWNED horse -> visible
    v = _create(ADMIN_H, STATE["horse_owned"], visibility="owner_facing").json()
    STATE["updates"].append(v["id"])
    requests.post(f"{API}/owner-updates/{v['id']}/publish", headers=ADMIN_H, timeout=30)

    # draft on owned horse -> hidden
    d = _create(ADMIN_H, STATE["horse_owned"]).json()
    STATE["updates"].append(d["id"])

    # internal published on owned horse -> hidden
    i = _create(ADMIN_H, STATE["horse_owned"], visibility="internal").json()
    STATE["updates"].append(i["id"])
    requests.post(f"{API}/owner-updates/{i['id']}/publish", headers=ADMIN_H, timeout=30)

    # published owner-facing on a NOT-owned horse -> hidden
    n = _create(ADMIN_H, STATE["horse_other"], visibility="owner_facing").json()
    STATE["updates"].append(n["id"])
    requests.post(f"{API}/owner-updates/{n['id']}/publish", headers=ADMIN_H, timeout=30)

    lst = requests.get(f"{API}/owner-updates", headers=OWNER_H, timeout=30)
    assert lst.status_code == 200
    ids = [u["id"] for u in lst.json()]
    assert v["id"] in ids
    assert d["id"] not in ids and i["id"] not in ids and n["id"] not in ids
    # every visible row is published + owner_facing + an owned horse
    for u in lst.json():
        assert u["status"] == "published" and u["visibility"] == "owner_facing"
        assert u["horse_id"] == STATE["horse_owned"]

    # GET-one: owner can fetch the visible one, but not a draft/internal/foreign (404)
    assert requests.get(f"{API}/owner-updates/{v['id']}", headers=OWNER_H, timeout=30).status_code == 200
    for hidden in (d["id"], i["id"], n["id"]):
        assert requests.get(f"{API}/owner-updates/{hidden}", headers=OWNER_H, timeout=30).status_code == 404


# --------------------------------------------------------------------------
# Barn isolation
# --------------------------------------------------------------------------
def test_other_barn_update_never_leaks():
    oid = "ou7a_other_" + uuid.uuid4().hex
    DB.owner_updates.insert_one({
        "id": oid, "barn_id": "other", "horse_id": "x", "author_user_id": "x",
        "kind": "routine", "visibility": "owner_facing", "status": "published",
        "body": "secret", "created_at": _iso(), "published_at": _iso(),
    })
    STATE["other_barn_update"] = oid
    ids = [u["id"] for u in requests.get(f"{API}/owner-updates", headers=ADMIN_H, timeout=30).json()]
    assert oid not in ids
    assert requests.get(f"{API}/owner-updates/{oid}", headers=ADMIN_H, timeout=30).status_code == 404


# --------------------------------------------------------------------------
# Sensitive drafts are publish-blocked in 7A (review gate lands in 7B)
# --------------------------------------------------------------------------
def test_sensitive_draft_cannot_be_published_in_7a():
    upd = _create(ADMIN_H, STATE["horse_owned"], kind="incident",
                  visibility="owner_facing", sensitive=True).json()
    STATE["updates"].append(upd["id"])
    assert upd["sensitive"] is True and upd["status"] == "draft"

    p = requests.post(f"{API}/owner-updates/{upd['id']}/publish", headers=ADMIN_H, timeout=30)
    assert p.status_code == 409
    assert p.json()["detail"] == "Sensitive updates require review"

    # status unchanged in DB
    row = DB.owner_updates.find_one({"id": upd["id"]}, {"_id": 0})
    assert row["status"] == "draft" and row["published_at"] is None

    # still invisible to the owner (draft)
    ids = [u["id"] for u in requests.get(f"{API}/owner-updates", headers=OWNER_H, timeout=30).json()]
    assert upd["id"] not in ids
    assert requests.get(f"{API}/owner-updates/{upd['id']}", headers=OWNER_H, timeout=30).status_code == 404

    # no published audit row was written
    assert DB.audit_log.count_documents({
        "resource_type": "owner_update", "resource_id": upd["id"],
        "action": "owner_update.published"}) == 0


# --------------------------------------------------------------------------
# Audit — high-signal lifecycle events, minimal non-PII metadata
# --------------------------------------------------------------------------
def test_publish_and_archive_emit_minimal_audit():
    upd = _create(ADMIN_H, STATE["horse_owned"], kind="training", visibility="owner_facing").json()
    STATE["updates"].append(upd["id"])
    requests.post(f"{API}/owner-updates/{upd['id']}/publish", headers=ADMIN_H, timeout=30)
    requests.post(f"{API}/owner-updates/{upd['id']}/archive", headers=ADMIN_H, timeout=30)

    rows = list(DB.audit_log.find(
        {"resource_type": "owner_update", "resource_id": upd["id"]}, {"_id": 0}))
    actions = {r["action"]: r for r in rows}
    assert "owner_update.published" in actions and "owner_update.archived" in actions
    for r in rows:
        assert r["barn_id"] == "primary"
        assert r["metadata"] == {"kind": "training", "visibility": "owner_facing"}
        # never store body/title/owner/horse text in audit metadata
        assert "body" not in r["metadata"] and "horse_id" not in r["metadata"]
