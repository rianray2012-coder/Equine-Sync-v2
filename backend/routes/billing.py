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

from fastapi import APIRouter, Depends
from pydantic import BaseModel


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
        return await list_collection("invoices", sort_field="due_date")

    @router.post("/invoices")
    async def create_invoice(body: InvoiceIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        await db.invoices.insert_one(doc)
        return clean(doc)

    @router.post("/invoices/{invoice_id}/pay")
    async def pay_invoice(invoice_id: str, user=Depends(get_current_user)):
        await db.invoices.update_one(
            {"id": invoice_id},
            {"$set": {"status": "paid", "paid_at": _iso(_now_utc())}},
        )
        return await db.invoices.find_one({"id": invoice_id}, {"_id": 0})

    return router
