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
        DB.invoices.delete_many({"recurring_charge_id": {"$in": _CREATED}})
        DB.recurring_charges.delete_many({"id": {"$in": _CREATED}})
    DB.recurring_charges.delete_many({"id": _FOREIGN_ID})
    DB.invoices.delete_many({"recurring_charge_id": _FOREIGN_ID})


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


def test_horse_of_different_owner_rejected():
    # A same-barn horse owned by a DIFFERENT owner must be rejected, and no
    # recurring charge may be created as a side effect.
    other = DB.horses.find_one(
        {"barn_id": "primary", "owner_id": {"$nin": [OWNER_ID, None]}}, {"_id": 0, "id": 1}
    )
    if not other:
        import pytest
        pytest.skip("no second-owner horse in seed data")
    before = DB.recurring_charges.count_documents({})
    _create(_payload(owner_id=OWNER_ID, horse_id=other["id"]), expect=404)
    assert DB.recurring_charges.count_documents({}) == before  # nothing created


def test_create_audit_includes_cadence_and_amount():
    body = _create(_payload(
        items=[{"description": "Board", "amount": 1000}], discount=100, tax_rate=10,
    ))
    entry = DB.audit_log.find_one(
        {"action": "recurring_charge.created", "resource_id": body["id"]}
    )
    assert entry is not None, "audit entry missing"
    md = entry.get("metadata") or {}
    assert md.get("cadence") == "monthly"
    assert md.get("amount") == 990.0  # (1000-100) + (900*10%) = 990


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


# ---------------------------------------------------------------- 9B-2: date validation

def test_create_rejects_end_before_start():
    _create(_payload(start_date="2026-07-01", end_date="2026-06-01"), expect=422)


def test_create_rejects_non_iso_start_date():
    _create(_payload(start_date="07/01/2026"), expect=422)


def test_update_rejects_end_before_start():
    rc = _create(_payload(start_date="2026-07-01", end_date=None))
    r = requests.patch(
        f"{API}/recurring-charges/{rc['id']}", headers=H,
        json={"end_date": "2026-06-01"}, timeout=30,
    )
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------- 9B-2: materializer

def _run(period=None, expect=200):
    body = {} if period is None else {"period": period}
    r = requests.post(f"{API}/admin/recurring-charges/run", headers=H, json=body, timeout=60)
    assert r.status_code == expect, r.text
    return r.json() if expect == 200 else r


def test_materialize_generates_invoice_with_9a_totals():
    rc = _create(_payload(
        start_date="2026-05-01", day_of_month=1, due_days=14, tax_rate=10,
        items=[{"description": "Board", "quantity": 1, "unit_amount": 1200}],
    ))
    res = _run(period="2026-08")
    assert res["period"] == "2026-08"
    assert res["generated_count"] >= 1
    inv = DB.invoices.find_one(
        {"recurring_charge_id": rc["id"], "period_key": "2026-08"}, {"_id": 0}
    )
    assert inv is not None
    assert inv["source"] == "recurring"
    assert inv["subtotal"] == 1200.0
    assert inv["tax_amount"] == 120.0
    assert inv["total"] == 1320.0
    assert inv["status"] == "open"
    assert inv["due_date"] == "2026-08-15"  # day_of_month 1 + 14 due_days
    # last_run_period stamped on the charge
    fresh = requests.get(f"{API}/recurring-charges/{rc['id']}", headers=H, timeout=30).json()
    assert fresh["last_run_period"] == "2026-08"


def test_materialize_is_idempotent_no_duplicate():
    rc = _create(_payload(start_date="2026-05-01", description="Idempotent board"))
    first = _run(period="2026-09")
    assert first["generated_count"] >= 1
    count_after_first = DB.invoices.count_documents(
        {"recurring_charge_id": rc["id"], "period_key": "2026-09"}
    )
    assert count_after_first == 1
    second = _run(period="2026-09")
    # the just-created charge must now be counted as skipped, never re-generated
    count_after_second = DB.invoices.count_documents(
        {"recurring_charge_id": rc["id"], "period_key": "2026-09"}
    )
    assert count_after_second == 1
    assert second["skipped_count"] >= 1


def test_materialize_skips_inactive_charge():
    rc = _create(_payload(start_date="2026-05-01", description="Inactive board"))
    requests.post(f"{API}/recurring-charges/{rc['id']}/deactivate", headers=H, json={}, timeout=30)
    _run(period="2026-10")
    inv = DB.invoices.find_one({"recurring_charge_id": rc["id"], "period_key": "2026-10"})
    assert inv is None  # inactive => skipped, no invoice generated


def test_materialize_skips_not_yet_started_and_ended():
    not_started = _create(_payload(start_date="2027-01-01", description="Future board"))
    ended = _create(_payload(start_date="2025-01-01", end_date="2025-12-31", description="Ended board"))
    _run(period="2026-11")
    assert DB.invoices.find_one({"recurring_charge_id": not_started["id"], "period_key": "2026-11"}) is None
    assert DB.invoices.find_one({"recurring_charge_id": ended["id"], "period_key": "2026-11"}) is None


def test_materialize_within_end_window_generates():
    rc = _create(_payload(start_date="2026-01-01", end_date="2026-12-31", description="Windowed board"))
    _run(period="2026-12")
    assert DB.invoices.find_one({"recurring_charge_id": rc["id"], "period_key": "2026-12"}) is not None


def test_materialize_bad_period_422():
    _run(period="2026-13", expect=422)
    _run(period="not-a-period", expect=422)


def test_materialize_non_manager_403():
    r = requests.post(f"{API}/admin/recurring-charges/run", headers=H_OWNER, json={}, timeout=30)
    assert r.status_code == 403


def test_materialize_audit_event_recorded():
    rc = _create(_payload(start_date="2026-05-01", description="Audit board"))
    _run(period="2027-03")
    entry = DB.audit_log.find_one(
        {"action": "recurring_charges.materialized", "metadata.month": "2027-03"},
        sort=[("ts", -1)],
    )
    assert entry is not None
    md = entry.get("metadata") or {}
    assert "generated_count" in md and "skipped_count" in md
    assert md["month"] == "2027-03"


def test_materialize_does_not_touch_foreign_barn_charge():
    # A recurring charge in another barn must never produce an invoice via the
    # primary-barn admin's run.
    foreign_id = "rc-foreign-9b2-run"
    DB.recurring_charges.insert_one({
        "id": foreign_id, "barn_id": "some-other-barn", "owner_id": "x",
        "description": "foreign", "items": [{"description": "x", "amount": 1}],
        "cadence": "monthly", "active": True, "start_date": "2026-01-01",
        "day_of_month": 1, "due_days": 14, "created_at": "2026-01-01T00:00:00+00:00",
    })
    try:
        _run(period="2026-06")
        assert DB.invoices.find_one({"recurring_charge_id": foreign_id}) is None
    finally:
        DB.recurring_charges.delete_one({"id": foreign_id})
        DB.invoices.delete_many({"recurring_charge_id": foreign_id})
