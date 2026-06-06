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
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core.tenancy import barn_filter, stamp_barn
from core import audit


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class InvoiceIn(BaseModel):
    owner_id: str
    horse_id: Optional[str] = None
    items: List[Dict[str, Any]]
    total: float
    due_date: str
    status: str = "open"  # open, paid, overdue
    notes: Optional[str] = None


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
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
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
