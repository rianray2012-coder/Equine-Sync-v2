"""Phase 9A — invoice line-item integrity & server-computed totals (live integration).

Proves the 9A contract on routes/billing.py create path:
  * server computes subtotal/discount/tax_amount/total and IGNORES client total
  * legacy {label, amount} line items still produce the same totals
  * discount (absolute) + tax_rate (%) math is correct and rounded
  * negative values / amount-less lines / empty items / bad status -> 422
  * the new computed fields are present in the response

Backend-only. Captured-id teardown (cleanup_test_invoices.py covers strays).
"""
import requests

from ._billing_helpers import API, auth_headers, mongo_db

_CREATED = []

H = auth_headers()


def teardown_module(module):
    db = mongo_db()
    if _CREATED:
        db.invoices.delete_many({"id": {"$in": _CREATED}})
    db.invoices.delete_many({"barn_id": "primary", "owner_id": "ownerX"})


def _create(payload, expect=200):
    r = requests.post(f"{API}/invoices", headers=H, json=payload, timeout=30)
    assert r.status_code == expect, r.text
    if expect == 200:
        body = r.json()
        _CREATED.append(body["id"])
        return body
    return r


def _base_payload(**over):
    p = {"owner_id": "ownerX", "items": [{"label": "Board", "amount": 500}],
         "total": 500.0, "due_date": "2026-07-01"}
    p.update(over)
    return p


# ---------------------------------------------------------------- server-computed

def test_server_computes_total_and_ignores_client_total():
    body = _create(_base_payload(
        items=[{"description": "Board", "quantity": 2, "unit_amount": 600}],
        total=99999.0,  # deliberately wrong — must be ignored
    ))
    assert body["subtotal"] == 1200.0
    assert body["discount"] == 0.0
    assert body["tax_rate"] == 0.0
    assert body["tax_amount"] == 0.0
    assert body["total"] == 1200.0  # computed, not the bogus client value
    # line normalized with computed amount
    assert body["items"][0]["amount"] == 1200.0


def test_legacy_label_amount_items_still_work():
    body = _create(_base_payload(
        items=[{"label": "Board", "amount": 1200}, {"label": "Farrier", "amount": 150}],
        total=1350.0,
    ))
    assert body["subtotal"] == 1350.0
    assert body["total"] == 1350.0
    # legacy 'label' preserved AND mirrored to description
    assert body["items"][0]["label"] == "Board"
    assert body["items"][0]["description"] == "Board"


def test_discount_and_tax_rate_math():
    body = _create(_base_payload(
        items=[{"description": "Board", "amount": 1000}],
        discount=100, tax_rate=10, total=0,
    ))
    assert body["subtotal"] == 1000.0
    assert body["discount"] == 100.0
    assert body["tax_rate"] == 10.0
    assert body["tax_amount"] == 90.0   # (1000-100)*10%
    assert body["total"] == 990.0       # 1000-100+90


def test_discount_clamped_to_subtotal():
    body = _create(_base_payload(
        items=[{"description": "Board", "amount": 200}], discount=500, total=0,
    ))
    assert body["discount"] == 200.0    # clamped to subtotal
    assert body["total"] == 0.0


# ---------------------------------------------------------------- response shape

def test_response_includes_new_computed_fields():
    body = _create(_base_payload())
    for k in ("subtotal", "discount", "tax_rate", "tax_amount", "total"):
        assert k in body, f"missing {k}"
    assert body["status"] == "open"
    assert "created_at" in body


def test_overdue_status_accepted():
    body = _create(_base_payload(status="overdue"))
    assert body["status"] == "overdue"


def test_omitted_client_total_succeeds_and_computes():
    # Server is authoritative: a payload with valid items and NO 'total' field
    # must succeed and return the computed total (locks in the 9A contract).
    payload = {"owner_id": "ownerX", "due_date": "2026-07-01",
               "items": [{"description": "Board", "quantity": 3, "unit_amount": 400}]}
    assert "total" not in payload
    body = _create(payload)
    assert body["subtotal"] == 1200.0
    assert body["total"] == 1200.0


# ---------------------------------------------------------------- rejections (422)

def test_invalid_status_rejected():
    _create(_base_payload(status="weird"), expect=422)


def test_negative_amount_rejected():
    _create(_base_payload(items=[{"description": "X", "amount": -5}]), expect=422)


def test_negative_discount_rejected():
    _create(_base_payload(discount=-10), expect=422)


def test_negative_tax_rate_rejected():
    _create(_base_payload(tax_rate=-1), expect=422)


def test_line_without_amount_or_qty_unit_rejected():
    _create(_base_payload(items=[{"description": "No price"}]), expect=422)


def test_empty_items_rejected():
    _create(_base_payload(items=[]), expect=422)
