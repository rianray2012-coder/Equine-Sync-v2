"""Phase 9B-1 — recurring charge CRUD (live integration).

Covers: create + get, owner/horse reference validation, cadence + template
validation, list filtering, update, deactivate, permission gating (non-manager
=> 403), and barn isolation. NO materialization here (that's 9B-2).

Captured-id teardown. Backend-only.
"""
import os
import pathlib

import pymongo
import requests

from ._test_creds import ADMIN, OWNER

_CREATED = []
_FOREIGN_ID = "rc-foreign-9b1-test"


def _read_env(key, root_index, sub):
    envf = pathlib.Path(__file__).resolve().parents[root_index] / sub
    for line in envf.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


API = f"{(os.environ.get('REACT_APP_BACKEND_URL') or _read_env('REACT_APP_BACKEND_URL', 2, 'frontend/.env')).rstrip('/')}/api"


def _mongo():
    url = os.environ.get("MONGO_URL") or _read_env("MONGO_URL", 1, ".env")
    name = os.environ.get("DB_NAME") or _read_env("DB_NAME", 1, ".env")
    return pymongo.MongoClient(url)[name]


def _token(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    r.raise_for_status()
    return r.json()["token"]


DB = _mongo()
H = {"Authorization": f"Bearer {_token(ADMIN)}"}
H_OWNER = {"Authorization": f"Bearer {_token(OWNER)}"}

# Real owner/horse ids in the primary barn (for ref validation).
_owner = DB.users.find_one({"role": "horse_owner", "barn_id": "primary"}, {"_id": 0, "id": 1})
_horse = DB.horses.find_one({"barn_id": "primary"}, {"_id": 0, "id": 1})
OWNER_ID = _owner["id"] if _owner else None
HORSE_ID = _horse["id"] if _horse else None


def teardown_module(module):
    if _CREATED:
        DB.recurring_charges.delete_many({"id": {"$in": _CREATED}})
    DB.recurring_charges.delete_many({"id": _FOREIGN_ID})


def _payload(**over):
    p = {
        "owner_id": OWNER_ID,
        "horse_id": HORSE_ID,
        "description": "Monthly board",
        "items": [{"description": "Board", "quantity": 1, "unit_amount": 1200}],
        "discount": 0,
        "tax_rate": 0,
        "cadence": "monthly",
        "day_of_month": 1,
        "start_date": "2026-07-01",
        "due_days": 14,
    }
    p.update(over)
    return p


def _create(payload, headers=H, expect=200):
    r = requests.post(f"{API}/recurring-charges", headers=headers, json=payload, timeout=30)
    assert r.status_code == expect, r.text
    if expect == 200:
        body = r.json()
        _CREATED.append(body["id"])
        return body
    return r


# ---------------------------------------------------------------- create + get

def test_create_and_get():
    body = _create(_payload())
    assert body["active"] is True
    assert body["cadence"] == "monthly"
    assert body["last_run_period"] is None
    assert body["items"][0]["amount"] == 1200.0  # template line normalized
    got = requests.get(f"{API}/recurring-charges/{body['id']}", headers=H, timeout=30)
    assert got.status_code == 200
    assert got.json()["id"] == body["id"]


def test_horse_optional():
    body = _create(_payload(horse_id=None))
    assert body["horse_id"] is None


# ---------------------------------------------------------------- ref validation

def test_bad_owner_ref_404():
    _create(_payload(owner_id="nope-not-an-owner"), expect=404)


def test_bad_horse_ref_404():
    _create(_payload(horse_id="nope-not-a-horse"), expect=404)


# ---------------------------------------------------------------- template/cadence validation

def test_bad_cadence_422():
    _create(_payload(cadence="weekly"), expect=422)


def test_empty_items_422():
    _create(_payload(items=[]), expect=422)


def test_negative_line_amount_422():
    _create(_payload(items=[{"description": "X", "amount": -1}]), expect=422)


def test_bad_day_of_month_422():
    _create(_payload(day_of_month=31), expect=422)


def test_negative_discount_422():
    _create(_payload(discount=-5), expect=422)


# ---------------------------------------------------------------- list filtering

def test_list_active_filter_excludes_deactivated():
    rc = _create(_payload(description="To deactivate"))
    requests.post(f"{API}/recurring-charges/{rc['id']}/deactivate", headers=H, json={}, timeout=30)
    active = requests.get(f"{API}/recurring-charges?active=true", headers=H, timeout=30).json()
    ids = {x["id"] for x in active}
    assert rc["id"] not in ids
    inactive = requests.get(f"{API}/recurring-charges?active=false", headers=H, timeout=30).json()
    assert rc["id"] in {x["id"] for x in inactive}


# ---------------------------------------------------------------- update

def test_update_fields():
    rc = _create(_payload())
    r = requests.patch(
        f"{API}/recurring-charges/{rc['id']}", headers=H,
        json={"description": "Updated board", "items": [{"description": "Board", "amount": 1300}]},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["description"] == "Updated board"
    assert body["items"][0]["amount"] == 1300.0
    assert body["updated_at"] >= rc["updated_at"]


def test_update_rejects_bad_cadence():
    rc = _create(_payload())
    r = requests.patch(f"{API}/recurring-charges/{rc['id']}", headers=H, json={"cadence": "daily"}, timeout=30)
    assert r.status_code == 422


def test_update_unknown_404():
    r = requests.patch(f"{API}/recurring-charges/does-not-exist", headers=H, json={"description": "x"}, timeout=30)
    assert r.status_code == 404


# ---------------------------------------------------------------- deactivate

def test_deactivate_idempotent():
    rc = _create(_payload())
    r1 = requests.post(f"{API}/recurring-charges/{rc['id']}/deactivate", headers=H, json={"reason": "owner left"}, timeout=30)
    assert r1.status_code == 200 and r1.json()["active"] is False
    r2 = requests.post(f"{API}/recurring-charges/{rc['id']}/deactivate", headers=H, json={}, timeout=30)
    assert r2.status_code == 200 and r2.json()["active"] is False


# ---------------------------------------------------------------- permissions

def test_non_manager_cannot_create():
    _create(_payload(), headers=H_OWNER, expect=403)


def test_non_manager_cannot_list():
    r = requests.get(f"{API}/recurring-charges", headers=H_OWNER, timeout=30)
    assert r.status_code == 403


# ---------------------------------------------------------------- barn isolation

def test_barn_isolation_hides_foreign_barn_doc():
    # Insert a recurring charge in a DIFFERENT barn directly, then confirm the
    # primary-barn admin can neither list nor fetch it.
    DB.recurring_charges.insert_one({
        "id": _FOREIGN_ID, "barn_id": "some-other-barn", "owner_id": "x",
        "description": "foreign", "items": [{"description": "x", "amount": 1}],
        "cadence": "monthly", "active": True, "created_at": "2026-01-01T00:00:00+00:00",
    })
    listed = requests.get(f"{API}/recurring-charges", headers=H, timeout=30).json()
    assert _FOREIGN_ID not in {x["id"] for x in listed}
    got = requests.get(f"{API}/recurring-charges/{_FOREIGN_ID}", headers=H, timeout=30)
    assert got.status_code == 404
