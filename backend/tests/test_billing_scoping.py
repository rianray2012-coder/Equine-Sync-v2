"""Phase 4B-4 — billing/invoices barn scoping (live integration).

Proves per-barn isolation for routes/billing.py:
- an other-barn invoice is excluded from GET /invoices;
- POST /invoices stamps barn_id="primary";
- POST /invoices/{id}/pay on a cross-barn invoice returns 404 with no mutation;
- the same-barn pay happy path still works end to end.
"""
import uuid
from datetime import datetime, timezone

import requests

from ._billing_helpers import API, auth_headers, mongo_db


def _mongo():
    return mongo_db()


def _admin_headers():
    return auth_headers()


def _iso():
    return datetime.now(timezone.utc).isoformat()


def teardown_module(module):
    # Per-test teardown already deletes created invoices; this is a safety sweep
    # of this module's synthetic owner_id in case of an interrupted run.
    _mongo().invoices.delete_many({"barn_id": "primary", "owner_id": "ownerX"})


def _invoice_payload():
    return {
        "owner_id": "ownerX",
        "horse_id": "horseX",
        "items": [{"label": "Board", "amount": 500}],
        "total": 500.0,
        "due_date": "2026-02-01",
    }


def test_other_barn_invoice_excluded_from_list():
    db = _mongo()
    H = _admin_headers()
    inv_id = "otherinv_" + uuid.uuid4().hex
    db.invoices.insert_one({
        "id": inv_id, "barn_id": "other", "owner_id": "o", "total": 100.0,
        "status": "open", "due_date": "2026-02-01", "created_at": _iso(),
    })
    try:
        r = requests.get(f"{API}/invoices", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        ids = [d.get("id") for d in r.json()]
        assert inv_id not in ids, "other-barn invoice leaked into list"
    finally:
        db.invoices.delete_many({"id": inv_id})


def test_create_invoice_stamps_primary_barn():
    db = _mongo()
    H = _admin_headers()
    r = requests.post(f"{API}/invoices", headers=H, json=_invoice_payload(), timeout=30)
    assert r.status_code == 200, r.text
    doc = r.json()
    try:
        assert doc.get("barn_id") == "primary", doc
    finally:
        db.invoices.delete_many({"id": doc.get("id")})


def test_pay_cross_barn_invoice_404_no_mutation():
    db = _mongo()
    H = _admin_headers()
    inv_id = "otherinv_" + uuid.uuid4().hex
    db.invoices.insert_one({
        "id": inv_id, "barn_id": "other", "owner_id": "o", "total": 100.0,
        "status": "open", "due_date": "2026-02-01", "created_at": _iso(),
    })
    try:
        r = requests.post(f"{API}/invoices/{inv_id}/pay", headers=H, timeout=30)
        assert r.status_code == 404, r.text
        doc = db.invoices.find_one({"id": inv_id})
        assert doc["status"] == "open"
        assert "paid_at" not in doc
    finally:
        db.invoices.delete_many({"id": inv_id})


def test_same_barn_pay_happy_path():
    db = _mongo()
    H = _admin_headers()
    cr = requests.post(f"{API}/invoices", headers=H, json=_invoice_payload(), timeout=30)
    assert cr.status_code == 200, cr.text
    created = cr.json()
    inv_id = created["id"]
    try:
        assert created.get("barn_id") == "primary", created
        pr = requests.post(f"{API}/invoices/{inv_id}/pay", headers=H, timeout=30)
        assert pr.status_code == 200, pr.text
        paid = pr.json()
        assert paid["id"] == inv_id
        assert paid["status"] == "paid"
        assert paid.get("paid_at"), paid
        assert paid.get("barn_id") == "primary", paid
    finally:
        db.invoices.delete_many({"id": inv_id})
