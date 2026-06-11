"""Phase 7D-1 — owner-scoped invoice visibility (live integration).

Proves the billing isolation fix:
  * a horse_owner sees ONLY their own invoices (owner_id == their user id)
  * an owner does NOT see another owner's invoice in the same barn
  * staff still see the full barn-scoped invoice list (unchanged)
  * cross-barn isolation holds (other-barn invoice never appears)

Strict teardown by captured ids.
"""
import uuid
from datetime import datetime, timezone

import requests

from ._billing_helpers import API, auth_headers, mongo_db
from ._test_creds import ADMIN, OWNER

ADMIN_H = auth_headers(ADMIN)
OWNER_H = auth_headers(OWNER)
DB = mongo_db()

STATE = {"invoices": [], "other_barn": None}


def _iso():
    return datetime.now(timezone.utc).isoformat()


def _make(owner_id, total):
    r = requests.post(f"{API}/invoices", headers=ADMIN_H, json={
        "owner_id": owner_id, "items": [{"label": "Board", "amount": total}],
        "total": total, "due_date": "2026-07-15", "status": "open",
    }, timeout=30)
    r.raise_for_status()
    iid = r.json()["id"]
    STATE["invoices"].append(iid)
    return iid


def setup_module(module):
    owner = DB.users.find_one({"email": OWNER["email"]}, {"_id": 0, "id": 1})
    assert owner, "owner demo account missing"
    STATE["owner_id"] = owner["id"]
    STATE["mine"] = _make(owner["id"], 111.0)
    STATE["theirs"] = _make("other-owner-" + uuid.uuid4().hex, 222.0)


def teardown_module(module):
    if STATE["invoices"]:
        DB.invoices.delete_many({"id": {"$in": STATE["invoices"]}})
    if STATE["other_barn"]:
        DB.invoices.delete_many({"id": STATE["other_barn"]})


def test_owner_sees_only_their_own_invoices():
    r = requests.get(f"{API}/invoices", headers=OWNER_H, timeout=30)
    assert r.status_code == 200
    items = r.json()
    ids = [i["id"] for i in items]
    assert STATE["mine"] in ids
    assert STATE["theirs"] not in ids
    # every returned invoice belongs to this owner
    assert all(i["owner_id"] == STATE["owner_id"] for i in items)


def test_staff_still_see_full_barn_invoice_list():
    ids = [i["id"] for i in requests.get(f"{API}/invoices", headers=ADMIN_H, timeout=30).json()]
    assert STATE["mine"] in ids and STATE["theirs"] in ids


def test_other_barn_invoice_never_leaks_to_owner():
    oid = "inv_other_barn_" + uuid.uuid4().hex
    DB.invoices.insert_one({
        "id": oid, "barn_id": "other", "owner_id": STATE["owner_id"],
        "items": [{"label": "x", "amount": 5}], "total": 5.0, "due_date": "2026-07-01",
        "status": "open", "created_at": _iso(),
    })
    STATE["other_barn"] = oid
    ids = [i["id"] for i in requests.get(f"{API}/invoices", headers=OWNER_H, timeout=30).json()]
    assert oid not in ids  # different barn, even though owner_id matches
