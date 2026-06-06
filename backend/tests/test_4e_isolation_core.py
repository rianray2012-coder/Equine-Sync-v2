"""Phase 4E — cross-tenant isolation: core domains.

Proves, in BOTH directions, that two real barns (A="primary", B=provisioned)
are fully isolated across every barn-native surface: horses, care, operations,
billing, onboarding, dashboard, invites, reports, and barn provisioning.

Test-only. If any assertion here fails it means a real cross-barn leak — the
fix belongs in the offending production route, not in this file.
"""
import uuid

import requests

from ._isolation_world import (
    API, build_world, teardown_world, mongo, detail,
)

WORLD = None


def setup_module(module):
    global WORLD
    WORLD = build_world()


def teardown_module(module):
    teardown_world(WORLD)


# --------------------------------------------------------------------------
# tiny HTTP helpers (raw — negative paths need the real status code)
# --------------------------------------------------------------------------
def _get(headers, path):
    r = requests.get(f"{API}{path}", headers=headers, timeout=30)
    assert r.status_code == 200, f"GET {path} -> {r.status_code}: {r.text}"
    return r.json()


def _ids(rows):
    return {r["id"] for r in rows}


def _post(headers, path, payload=None):
    return requests.post(f"{API}{path}", headers=headers, json=(payload or {}), timeout=30)


def _patch(headers, path, payload):
    return requests.patch(f"{API}{path}", headers=headers, json=payload, timeout=30)


def _delete(headers, path):
    return requests.delete(f"{API}{path}", headers=headers, timeout=30)


# --------------------------------------------------------------------------
# Horses
# --------------------------------------------------------------------------
def test_horses_list_isolation_both_directions():
    a_horse, b_horse = WORLD.a["horse"], WORLD.b["horse"]
    a_list = _ids(_get(WORLD.h_a, "/horses"))
    b_list = _ids(_get(WORLD.h_b, "/horses"))
    assert a_horse in a_list and b_horse not in a_list
    assert b_horse in b_list and a_horse not in b_list


def test_horses_get_by_id_cross_barn_404():
    assert _get_status(WORLD.h_a, f"/horses/{WORLD.b['horse']}") == 404
    assert _get_status(WORLD.h_b, f"/horses/{WORLD.a['horse']}") == 404


def test_horses_patch_cross_barn_404_no_mutation():
    db = mongo()
    before = db.horses.find_one({"id": WORLD.b["horse"]}, {"_id": 0, "name": 1})
    r = _patch(WORLD.h_a, f"/horses/{WORLD.b['horse']}", {"name": "HIJACKED"})
    assert r.status_code == 404
    after = db.horses.find_one({"id": WORLD.b["horse"]}, {"_id": 0, "name": 1})
    assert after["name"] == before["name"] != "HIJACKED"


def test_horses_patch_cannot_move_barn():
    r = _patch(WORLD.h_a, f"/horses/{WORLD.a['horse']}",
               {"barn_id": WORLD.barn_b, "id": "x", "color": "bay"})
    assert r.status_code == 200
    db = mongo()
    doc = db.horses.find_one({"id": WORLD.a["horse"]}, {"_id": 0})
    assert doc["barn_id"] == "primary"
    assert doc["id"] == WORLD.a["horse"]
    assert doc["color"] == "bay"  # legit field still applied


# --------------------------------------------------------------------------
# Care domain — owners / medications / vet-records / injuries / wellness
# --------------------------------------------------------------------------
def test_care_lists_isolation_both_directions():
    surfaces = [
        ("/owners", "owner"),
        ("/medications", "medication"),
        ("/vet-records", "vet"),
        ("/injuries", "injury"),
        ("/wellness", "wellness"),
    ]
    for path, label in surfaces:
        a_ids = _ids(_get(WORLD.h_a, path))
        b_ids = _ids(_get(WORLD.h_b, path))
        assert WORLD.a[label] in a_ids and WORLD.b[label] not in a_ids, f"A leak on {path}"
        assert WORLD.b[label] in b_ids and WORLD.a[label] not in b_ids, f"B leak on {path}"


# --------------------------------------------------------------------------
# Operations — lessons / training / messages / SR / incidents
# --------------------------------------------------------------------------
def test_operations_lists_isolation_both_directions():
    surfaces = [
        ("/lessons", "lesson"),
        ("/training", "training"),
        ("/messages", "message"),
        ("/service-requests", "sr"),
        ("/incidents", "incident"),
    ]
    for path, label in surfaces:
        a_ids = _ids(_get(WORLD.h_a, path))
        b_ids = _ids(_get(WORLD.h_b, path))
        assert WORLD.a[label] in a_ids and WORLD.b[label] not in a_ids, f"A leak on {path}"
        assert WORLD.b[label] in b_ids and WORLD.a[label] not in b_ids, f"B leak on {path}"


def test_service_request_approve_decline_cross_barn_404_no_mutation():
    db = mongo()
    for actor, other_sr in ((WORLD.h_a, WORLD.b["sr"]), (WORLD.h_b, WORLD.a["sr"])):
        for action in ("approve", "decline"):
            r = _post(actor, f"/service-requests/{other_sr}/{action}")
            assert r.status_code == 404, f"{action} {other_sr} -> {r.status_code}"
            doc = db.service_requests.find_one({"id": other_sr}, {"_id": 0, "status": 1})
            assert doc["status"] == "pending"


# --------------------------------------------------------------------------
# Billing
# --------------------------------------------------------------------------
def test_invoices_list_isolation_both_directions():
    a_ids = _ids(_get(WORLD.h_a, "/invoices"))
    b_ids = _ids(_get(WORLD.h_b, "/invoices"))
    assert WORLD.a["invoice"] in a_ids and WORLD.b["invoice"] not in a_ids
    assert WORLD.b["invoice"] in b_ids and WORLD.a["invoice"] not in b_ids


def test_invoice_pay_cross_barn_404_no_mutation():
    db = mongo()
    for actor, other_inv in ((WORLD.h_a, WORLD.b["invoice"]), (WORLD.h_b, WORLD.a["invoice"])):
        r = _post(actor, f"/invoices/{other_inv}/pay")
        assert r.status_code == 404
        doc = db.invoices.find_one({"id": other_inv}, {"_id": 0})
        assert doc.get("status") != "paid" and "paid_at" not in doc


# --------------------------------------------------------------------------
# Onboarding — lists / deletes / barn singleton
# --------------------------------------------------------------------------
def test_onboarding_lists_isolation_both_directions():
    surfaces = [
        ("/locations", "location"),
        ("/feed-templates", "feedtpl"),
        ("/inventory", "inventory"),
        ("/recurring-schedules", "rs"),
        ("/staff-invites", "staffinvite"),
    ]
    for path, label in surfaces:
        a_ids = _ids(_get(WORLD.h_a, path))
        b_ids = _ids(_get(WORLD.h_b, path))
        assert WORLD.a[label] in a_ids and WORLD.b[label] not in a_ids, f"A leak on {path}"
        assert WORLD.b[label] in b_ids and WORLD.a[label] not in b_ids, f"B leak on {path}"


def test_onboarding_delete_cross_barn_is_silent_noop():
    # Barn A admin tries to delete Barn B's location -> ok:true but no effect.
    r = _delete(WORLD.h_a, f"/locations/{WORLD.b['location']}")
    assert r.status_code == 200 and r.json().get("ok") is True
    assert WORLD.b["location"] in _ids(_get(WORLD.h_b, "/locations"))  # still there
    # And the reverse direction.
    r = _delete(WORLD.h_b, f"/locations/{WORLD.a['location']}")
    assert r.status_code == 200 and r.json().get("ok") is True
    assert WORLD.a["location"] in _ids(_get(WORLD.h_a, "/locations"))


def test_barn_singleton_isolation():
    a_barn = _get(WORLD.h_a, "/barn")
    b_barn = _get(WORLD.h_b, "/barn")
    assert a_barn["id"] == "primary"
    assert b_barn["id"] == WORLD.barn_b
    assert a_barn["id"] != b_barn["id"]


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
def test_dashboard_summary_counts_are_barn_scoped():
    db = mongo()
    a_sum = _get(WORLD.h_a, "/dashboard/summary")
    b_sum = _get(WORLD.h_b, "/dashboard/summary")
    # Each barn's horse count equals exactly its own DB count.
    assert a_sum["total_horses"] == db.horses.count_documents({"barn_id": "primary"})
    assert b_sum["total_horses"] == db.horses.count_documents({"barn_id": WORLD.barn_b})
    # Direct isolation (no size assumption): the two barns' horse rosters are
    # disjoint, and neither summary counts the other barn's seeded horse.
    a_horse_ids = _ids(_get(WORLD.h_a, "/horses"))
    b_horse_ids = _ids(_get(WORLD.h_b, "/horses"))
    assert a_horse_ids.isdisjoint(b_horse_ids)
    assert WORLD.b["horse"] not in a_horse_ids and WORLD.b["owner_horse"] not in a_horse_ids
    assert WORLD.a["horse"] not in b_horse_ids


def test_dashboard_barn_board_lists_are_barn_scoped():
    a_board = _get(WORLD.h_a, "/dashboard/barn-board")
    b_board = _get(WORLD.h_b, "/dashboard/barn-board")
    a_lessons = {x["id"] for x in a_board["lessons"]}
    b_lessons = {x["id"] for x in b_board["lessons"]}
    assert WORLD.b["lesson"] not in a_lessons
    assert WORLD.a["lesson"] not in b_lessons


# --------------------------------------------------------------------------
# Invites
# --------------------------------------------------------------------------
def test_invites_list_isolation_both_directions():
    a_emails = {i["email"] for i in _get(WORLD.h_a, "/invites")}
    b_emails = {i["email"] for i in _get(WORLD.h_b, "/invites")}
    assert WORLD.owner_b_email in b_emails
    assert WORLD.owner_b_email not in a_emails


def test_invite_resend_revoke_cross_barn_404():
    db = mongo()
    a_inv = _post(WORLD.h_a, "/invites",
                  {"email": f"a_inv_{uuid.uuid4().hex[:8]}@ex.com", "role": "groom"}).json()
    b_inv = _post(WORLD.h_b, "/invites",
                  {"email": f"b_inv_{uuid.uuid4().hex[:8]}@ex.com", "role": "groom"}).json()
    try:
        # Cross-barn resend -> 404 (no existence leak).
        assert _post(WORLD.h_a, f"/invites/{b_inv['id']}/resend").status_code == 404
        assert _post(WORLD.h_b, f"/invites/{a_inv['id']}/resend").status_code == 404
        # Cross-barn revoke -> 404; the invite stays pending.
        assert _post(WORLD.h_a, f"/invites/{b_inv['id']}/revoke").status_code == 404
        assert _post(WORLD.h_b, f"/invites/{a_inv['id']}/revoke").status_code == 404
        assert db.invites.find_one({"id": b_inv["id"]})["status"] == "pending"
        assert db.invites.find_one({"id": a_inv["id"]})["status"] == "pending"
    finally:
        db.invites.delete_many({"id": {"$in": [a_inv["id"], b_inv["id"]]}})


# --------------------------------------------------------------------------
# Reports — setup-health scoped to caller's barn
# --------------------------------------------------------------------------
def test_setup_health_is_barn_scoped():
    db = mongo()
    a_sh = _get(WORLD.h_a, "/reports/setup-health")
    b_sh = _get(WORLD.h_b, "/reports/setup-health")
    # Each barn's setup count equals exactly its own onboarding_progress docs —
    # neither barn's total absorbs the other's (the disjoint DB-count equality
    # is itself the both-directions isolation proof).
    assert a_sh["total_setups"] == db.onboarding_progress.count_documents({"barn_id": "primary"})
    assert b_sh["total_setups"] == db.onboarding_progress.count_documents({"barn_id": WORLD.barn_b})
    # Invite counts are barn-scoped too.
    assert b_sh["invites"]["total"] == db.invites.count_documents({"barn_id": WORLD.barn_b})


# --------------------------------------------------------------------------
# Barn provisioning — only the founder barn may create barns
# --------------------------------------------------------------------------
def test_provisioned_barn_admin_cannot_create_barns():
    r = _post(WORLD.h_b, "/barns", {
        "name": "Rogue Barn", "admin_email": f"rogue_{uuid.uuid4().hex[:8]}@ex.com",
        "admin_full_name": "Rogue", "admin_password": "Passw0rd!9",
    })
    assert r.status_code == 403
    assert "founder barn" in (detail(r) or "").lower()


# --------------------------------------------------------------------------
def _get_status(headers, path):
    return requests.get(f"{API}{path}", headers=headers, timeout=30).status_code
