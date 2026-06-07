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

from ._owner_helpers import API, auth_headers, mongo_db
from ._test_creds import ADMIN, GROOM, OWNER

TRAINER = {"email": "trainer@equinesync.com", "password": "demo1234"}

ADMIN_H = auth_headers(ADMIN)
OWNER_H = auth_headers(OWNER)
GROOM_H = auth_headers(GROOM)
TRAINER_H = auth_headers(TRAINER)
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
    # every visible row is published + owner_facing (the owner may also own other
    # horses — e.g. a demo-linked horse — whose published updates appear too)
    for u in lst.json():
        assert u["status"] == "published" and u["visibility"] == "owner_facing"
    # the specific update we published is attributed to our owned test horse
    v_row = next(u for u in lst.json() if u["id"] == v["id"])
    assert v_row["horse_id"] == STATE["horse_owned"]

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


def _audit_actions(update_id):
    return {r["action"]: r for r in DB.audit_log.find(
        {"resource_type": "owner_update", "resource_id": update_id}, {"_id": 0})}


# --------------------------------------------------------------------------
# Phase 7B — sensitive-update approval flow
# --------------------------------------------------------------------------
def test_7b_sensitive_review_happy_path_with_four_eyes():
    trainer = DB.users.find_one({"email": TRAINER["email"]}, {"_id": 0, "id": 1})
    assert trainer, "trainer demo account missing"

    upd = _create(ADMIN_H, STATE["horse_owned"], kind="incident",
                  visibility="owner_facing", sensitive=True).json()
    STATE["updates"].append(upd["id"])
    uid = upd["id"]

    # sensitive cannot be published directly (still 409 from 7A)
    assert requests.post(f"{API}/owner-updates/{uid}/publish", headers=ADMIN_H, timeout=30).status_code == 409

    # submit (author, create cap) -> pending_review
    s = requests.post(f"{API}/owner-updates/{uid}/submit", headers=ADMIN_H, timeout=30)
    assert s.status_code == 200 and s.json()["status"] == "pending_review"

    # owner cannot see a pending_review update
    ids = [u["id"] for u in requests.get(f"{API}/owner-updates", headers=OWNER_H, timeout=30).json()]
    assert uid not in ids
    assert requests.get(f"{API}/owner-updates/{uid}", headers=OWNER_H, timeout=30).status_code == 404

    # four-eyes: the author cannot approve their own sensitive update
    fe = requests.post(f"{API}/owner-updates/{uid}/approve", headers=ADMIN_H, timeout=30)
    assert fe.status_code == 403 and fe.json()["detail"] == "Author cannot approve their own sensitive update"
    assert DB.owner_updates.find_one({"id": uid}, {"_id": 0})["status"] == "pending_review"

    # a different reviewer (trainer) approves -> published
    ap = requests.post(f"{API}/owner-updates/{uid}/approve", headers=TRAINER_H, timeout=30)
    assert ap.status_code == 200
    body = ap.json()
    assert body["status"] == "published" and body["reviewed_by"] == trainer["id"]
    assert body["published_by"] == trainer["id"] and body["published_at"]

    # owner now sees it
    ids2 = [u["id"] for u in requests.get(f"{API}/owner-updates", headers=OWNER_H, timeout=30).json()]
    assert uid in ids2

    # audit: submitted + approved, minimal metadata only
    actions = _audit_actions(uid)
    assert "owner_update.submitted" in actions and "owner_update.approved" in actions
    for a in actions.values():
        assert a["metadata"] == {"kind": "incident", "visibility": "owner_facing"}
        assert "review_note" not in a["metadata"] and "body" not in a["metadata"]


def test_7b_request_changes_stores_note_and_audits_without_it():
    upd = _create(ADMIN_H, STATE["horse_owned"], kind="wellness",
                  visibility="owner_facing", sensitive=True).json()
    STATE["updates"].append(upd["id"])
    uid = upd["id"]
    requests.post(f"{API}/owner-updates/{uid}/submit", headers=ADMIN_H, timeout=30)

    rc = requests.post(f"{API}/owner-updates/{uid}/request-changes", headers=TRAINER_H,
                       json={"review_note": "Please add the vet contact."}, timeout=30)
    assert rc.status_code == 200
    back = rc.json()
    assert back["status"] == "draft"
    assert back["review_note"] == "Please add the vet contact."
    assert back["reviewed_by"] == DB.users.find_one({"email": TRAINER["email"]}, {"id": 1})["id"]

    # the review note is stored on the update but NEVER in the audit metadata
    cr = _audit_actions(uid).get("owner_update.changes_requested")
    assert cr is not None
    assert cr["metadata"] == {"kind": "wellness", "visibility": "owner_facing"}
    assert "review_note" not in cr["metadata"]


def test_7b_state_guards_and_role_gates():
    # approve / request-changes only valid from pending_review
    d = _create(ADMIN_H, STATE["horse_owned"]).json()
    STATE["updates"].append(d["id"])
    assert requests.post(f"{API}/owner-updates/{d['id']}/approve", headers=TRAINER_H, timeout=30).status_code == 409
    assert requests.post(f"{API}/owner-updates/{d['id']}/request-changes", headers=TRAINER_H,
                         json={}, timeout=30).status_code == 409

    # submit only valid from draft
    requests.post(f"{API}/owner-updates/{d['id']}/submit", headers=ADMIN_H, timeout=30)
    assert requests.post(f"{API}/owner-updates/{d['id']}/submit", headers=ADMIN_H, timeout=30).status_code == 409

    # role gates: groom can't submit (no create cap); owner can't review
    g = _create(ADMIN_H, STATE["horse_owned"]).json()
    STATE["updates"].append(g["id"])
    assert requests.post(f"{API}/owner-updates/{g['id']}/submit", headers=GROOM_H, timeout=30).status_code == 403
    requests.post(f"{API}/owner-updates/{g['id']}/submit", headers=ADMIN_H, timeout=30)
    ow = requests.post(f"{API}/owner-updates/{g['id']}/approve", headers=OWNER_H, timeout=30)
    assert ow.status_code == 403 and "review owner updates" in ow.json()["detail"]


def test_7b_non_sensitive_can_be_submitted_and_self_approved():
    # any draft may be submitted; four-eyes is enforced for SENSITIVE only,
    # so the author may approve their own NON-sensitive submission.
    upd = _create(ADMIN_H, STATE["horse_owned"], sensitive=False).json()
    STATE["updates"].append(upd["id"])
    uid = upd["id"]
    assert requests.post(f"{API}/owner-updates/{uid}/submit", headers=ADMIN_H, timeout=30).status_code == 200
    ap = requests.post(f"{API}/owner-updates/{uid}/approve", headers=ADMIN_H, timeout=30)
    assert ap.status_code == 200 and ap.json()["status"] == "published"


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
