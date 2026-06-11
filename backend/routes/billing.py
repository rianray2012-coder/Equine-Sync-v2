"""routes/billing.py — invoice bookkeeping.

Extracted from routes/operations.py (Phase 3F). Invoice list/create + a
mark-as-paid status flip. Behavior is identical to the previous inline handlers
(pure lift-and-shift).

Scope note: billing is intentionally **invoice bookkeeping only** — there is NO
payment processor (no Stripe/charges/subscriptions). `/invoices/{id}/pay` simply
sets the invoice status to "paid". A real payments integration would be a
separate, explicitly-scoped feature (not part of Phase 3 modularization).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from core.tenancy import barn_filter, stamp_barn
from core import audit


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class LineItem(BaseModel):
    # extra="allow" preserves any legacy keys (e.g. a bare {"label","amount"})
    model_config = ConfigDict(extra="allow")
    description: Optional[str] = None
    label: Optional[str] = None        # legacy alias for description
    quantity: Optional[float] = None
    unit_amount: Optional[float] = None
    amount: Optional[float] = None


class InvoiceIn(BaseModel):
    owner_id: str
    horse_id: Optional[str] = None
    items: List[LineItem]
    # Accepted for backward-compatibility but IGNORED — the server computes the
    # authoritative total from the line items (Phase 9A).
    total: Optional[float] = None
    due_date: str
    status: str = "open"  # open, paid, overdue
    notes: Optional[str] = None
    discount: float = 0.0   # absolute amount, clamped to 0..subtotal
    tax_rate: float = 0.0   # percentage applied to (subtotal - discount)


_VALID_STATUS = {"open", "paid", "overdue"}


def _money(x) -> float:
    return round(float(x) + 0.0, 2)


def _line_amount(li: LineItem) -> float:
    """Resolve a single line's amount; legacy {amount} wins, else quantity×unit_amount."""
    for name, val in (("quantity", li.quantity), ("unit_amount", li.unit_amount), ("amount", li.amount)):
        if val is not None and float(val) < 0:
            raise HTTPException(422, f"Line item {name} cannot be negative")
    if li.amount is not None:
        amt = float(li.amount)
    elif li.quantity is not None and li.unit_amount is not None:
        amt = float(li.quantity) * float(li.unit_amount)
    else:
        raise HTTPException(422, "Each line item needs 'amount', or both 'quantity' and 'unit_amount'")
    return _money(amt)


def _normalize_line(li: LineItem) -> dict:
    d = li.model_dump(exclude_none=True)  # keeps legacy/extra keys
    d["amount"] = _line_amount(li)
    if d.get("description") is None and d.get("label") is not None:
        d["description"] = d["label"]  # mirror for clarity; original key preserved
    return d


def _compute_invoice(body: InvoiceIn):
    """Server-authoritative totals. Returns (items, subtotal, discount, tax_rate, tax_amount, total)."""
    items = [_normalize_line(li) for li in body.items]
    if not items:
        raise HTTPException(422, "An invoice needs at least one line item")
    if body.discount < 0:
        raise HTTPException(422, "Discount cannot be negative")
    if body.tax_rate < 0:
        raise HTTPException(422, "Tax rate cannot be negative")
    subtotal = _money(sum(li["amount"] for li in items))
    discount = _money(min(float(body.discount), subtotal))  # clamp 0..subtotal
    tax_rate = float(body.tax_rate)
    tax_amount = _money((subtotal - discount) * tax_rate / 100.0)
    total = _money(subtotal - discount + tax_amount)
    return items, subtotal, discount, tax_rate, tax_amount, total


def build_router(*, db, get_current_user, list_collection, clean, new_id) -> APIRouter:
    router = APIRouter(tags=["billing"])

    # ---------------- Invoices ----------------

    @router.get("/invoices")
    async def list_invoices(user=Depends(get_current_user)):
        # Phase 7D-1: owner-scope — a horse_owner sees ONLY their own invoices
        # (still barn-scoped). Staff keep the full barn-scoped list (unchanged).
        extra = {"owner_id": user["id"]} if user.get("role") == "horse_owner" else {}
        return await list_collection("invoices", barn_filter(user, extra), sort_field="due_date")

    @router.post("/invoices")
    async def create_invoice(body: InvoiceIn, user=Depends(get_current_user)):
        if body.status not in _VALID_STATUS:
            raise HTTPException(422, f"Invalid status; must be one of {sorted(_VALID_STATUS)}")
        items, subtotal, discount, tax_rate, tax_amount, total = _compute_invoice(body)
        doc = {
            "id": new_id(),
            "owner_id": body.owner_id,
            "horse_id": body.horse_id,
            "items": items,
            "subtotal": subtotal,
            "discount": discount,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "total": total,  # server-computed; client-supplied total ignored
            "due_date": body.due_date,
            "status": body.status,
            "notes": body.notes,
            "created_at": _iso(_now_utc()),
        }
        stamp_barn(user, doc)
        await db.invoices.insert_one(doc)
        return clean(doc)

    @router.post("/invoices/{invoice_id}/pay")
    async def pay_invoice(invoice_id: str, request: Request, user=Depends(get_current_user)):
        # Phase 4B-4: scope by id + barn so a cross-barn invoice 404s (no
        # existence leak / no mutation). Idempotent "set status=paid" preserved.
        scope = barn_filter(user, {"id": invoice_id})
        existing = await db.invoices.find_one(scope, {"_id": 0, "total": 1})
        if not existing:
            raise HTTPException(404, "Invoice not found")
        await db.invoices.update_one(
            scope,
            {"$set": {"status": "paid", "paid_at": _iso(_now_utc())}},
        )
        await audit.record(
            action="invoice.paid", user=user, request=request,
            resource_type="invoice", resource_id=invoice_id,
            metadata={"amount": existing.get("total")},
        )
        return await db.invoices.find_one(scope, {"_id": 0})

    return router
