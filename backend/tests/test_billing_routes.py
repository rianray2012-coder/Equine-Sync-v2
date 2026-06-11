"""Phase 3F — routes/billing.py extraction tests (lightweight).

Covers route registration, auth, and the invoice create/list/pay round-trip
(now served by routes/billing.py). Behavior is unchanged from when these lived
in routes/operations.py. No payment-processor behavior exists or is tested.
"""
import pytest
import requests

from ._billing_helpers import API, BASE, auth_headers, mongo_db

_CREATED = []  # invoice ids created by this module — cleaned up in teardown


def teardown_module(module):
    db = mongo_db()
    if _CREATED:
        db.invoices.delete_many({"id": {"$in": _CREATED}})
    # safety sweep of this module's synthetic owner_id in case of interrupted runs
    db.invoices.delete_many({"barn_id": "primary", "owner_id": "owner-test"})


INVOICE_PATHS = ["/api/invoices", "/api/invoices/{invoice_id}/pay"]


def _auth():
    return auth_headers()


def test_invoice_routes_registered():
    spec = None
    for url in ("http://localhost:8001/openapi.json", f"{BASE}/openapi.json"):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200 and "application/json" in r.headers.get("content-type", ""):
                spec = r.json()
                break
        except requests.RequestException:
            continue
    if spec is None:
        pytest.skip("OpenAPI spec not reachable in this environment")
    paths = set(spec.get("paths", {}).keys())
    missing = [p for p in INVOICE_PATHS if p not in paths]
    assert not missing, f"missing registered invoice routes: {missing}"


def test_invoices_require_auth():
    assert requests.get(f"{API}/invoices", timeout=30).status_code == 401
    assert requests.post(f"{API}/invoices", json={}, timeout=30).status_code == 401


def test_invoice_create_list_pay_roundtrip():
    h = _auth()
    # create
    r = requests.post(f"{API}/invoices", headers=h, json={
        "owner_id": "owner-test", "items": [{"label": "Board", "amount": 1200}],
        "total": 1200, "due_date": "2026-07-01",
    }, timeout=30)
    assert r.status_code == 200, r.text
    created = r.json()
    iid = created["id"]
    _CREATED.append(iid)
    assert created["status"] == "open"
    assert "created_at" in created
    assert created["total"] == 1200

    # list includes it (sorted by due_date — just assert presence)
    lst = requests.get(f"{API}/invoices", headers=h, timeout=30)
    assert lst.status_code == 200
    assert any(x["id"] == iid for x in lst.json())

    # pay flips status -> paid and stamps paid_at
    paid = requests.post(f"{API}/invoices/{iid}/pay", headers=h, timeout=30)
    assert paid.status_code == 200, paid.text
    body = paid.json()
    assert body["status"] == "paid"
    assert body.get("paid_at")
