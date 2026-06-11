"""routes/recurring_charges.py — Phase 9B-1: recurring charge definitions (CRUD).

A *recurring charge* is a per-owner (optionally per-horse) billing template that
the 9B-2 materializer will turn into invoices on a monthly cadence using the
**9A line-item structure + server-computed totals**. 9B-1 is the data contract
only: create / list / get / update / deactivate. **No invoice generation here.**

Backend-only. Management is gated to {admin, barn_manager} via the additive
`recurring_charge:manage` capability. All reads/writes are barn-scoped
(stamp_barn / barn_filter) and owner/horse references are validated against the
caller's barn. Emits light, non-sensitive Phase 5 audit events (fail-open).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core.tenancy import barn_filter, stamp_barn
from core.permissions import require
from core import audit
from routes.billing import LineItem, _normalize_line, _money  # reuse 9A line-item shape + math


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


_VALID_CADENCE = {"monthly"}


class RecurringChargeIn(BaseModel):
    owner_id: str
    horse_id: Optional[str] = None
    description: str
    items: List[LineItem]
    discount: float = 0.0
    tax_rate: float = 0.0
    cadence: str = "monthly"
    day_of_month: int = 1
    start_date: str
    end_date: Optional[str] = None
    due_days: int = 14


class RecurringChargeUpdate(BaseModel):
    description: Optional[str] = None
    items: Optional[List[LineItem]] = None
    discount: Optional[float] = None
    tax_rate: Optional[float] = None
    cadence: Optional[str] = None
    day_of_month: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    due_days: Optional[int] = None
    active: Optional[bool] = None


class DeactivateIn(BaseModel):
    reason: Optional[str] = None


def _validate_cadence(cadence):
    if cadence is not None and cadence not in _VALID_CADENCE:
        raise HTTPException(422, f"Unsupported cadence; only {sorted(_VALID_CADENCE)} supported")


def _validate_scalars(discount, tax_rate, day_of_month, due_days):
    if discount is not None and discount < 0:
        raise HTTPException(422, "Discount cannot be negative")
    if tax_rate is not None and tax_rate < 0:
        raise HTTPException(422, "Tax rate cannot be negative")
    if day_of_month is not None and not (1 <= day_of_month <= 28):
        raise HTTPException(422, "day_of_month must be between 1 and 28")
    if due_days is not None and due_days < 0:
        raise HTTPException(422, "due_days cannot be negative")


def _validate_items(items):
    """Normalize + validate template line items (rejects negatives / amount-less lines)."""
    if not items:
        raise HTTPException(422, "A recurring charge needs at least one line item")
    return [_normalize_line(li) for li in items]


def _template_total(items, discount, tax_rate):
    """Charge total after discount/tax using the same normalized 9A item math.
    Non-sensitive scalar — safe for audit metadata. (9B-2 will reuse this.)"""
    subtotal = _money(sum(float(li["amount"]) for li in items))
    disc = _money(min(float(discount or 0), subtotal))
    tax_amt = _money((subtotal - disc) * float(tax_rate or 0) / 100.0)
    return _money(subtotal - disc + tax_amt)


def build_router(*, db, get_current_user, clean, new_id) -> APIRouter:
    router = APIRouter(tags=["billing"])

    async def _validate_refs(user, owner_id, horse_id):
        owner = await db.users.find_one(
            barn_filter(user, {"id": owner_id, "role": "horse_owner"}), {"_id": 0, "id": 1}
        )
        if not owner:
            raise HTTPException(404, "Owner not found in this barn")
        if horse_id:
            # Bind the horse to the selected owner — a same-barn horse owned by a
            # different owner must be rejected (generic 404, no existence leak).
            horse = await db.horses.find_one(
                barn_filter(user, {"id": horse_id, "owner_id": owner_id}), {"_id": 0, "id": 1}
            )
            if not horse:
                raise HTTPException(404, "Horse not found in this barn")

    @router.post("/recurring-charges")
    async def create_recurring_charge(body: RecurringChargeIn, request: Request, user=Depends(get_current_user)):
        require(user, "recurring_charge:manage")
        _validate_cadence(body.cadence)
        _validate_scalars(body.discount, body.tax_rate, body.day_of_month, body.due_days)
        items = _validate_items(body.items)
        await _validate_refs(user, body.owner_id, body.horse_id)
        now = _iso(_now_utc())
        doc = {
            "id": new_id(),
            "owner_id": body.owner_id,
            "horse_id": body.horse_id,
            "description": body.description,
            "items": items,
            "discount": float(body.discount),
            "tax_rate": float(body.tax_rate),
            "cadence": body.cadence,
            "day_of_month": body.day_of_month,
            "start_date": body.start_date,
            "end_date": body.end_date,
            "due_days": body.due_days,
            "active": True,
            "last_run_period": None,  # set by 9B-2 materializer
            "created_by": user["id"],
            "created_at": now,
            "updated_at": now,
        }
        stamp_barn(user, doc)
        await db.recurring_charges.insert_one(doc)
        await audit.record(
            action="recurring_charge.created", user=user, request=request,
            resource_type="recurring_charge", resource_id=doc["id"],
            metadata={"cadence": doc["cadence"], "amount": _template_total(items, body.discount, body.tax_rate)},
        )
        return clean(doc)

    @router.get("/recurring-charges")
    async def list_recurring_charges(
        active: Optional[bool] = None, owner_id: Optional[str] = None, user=Depends(get_current_user)
    ):
        require(user, "recurring_charge:manage")
        extra = {}
        if active is not None:
            extra["active"] = active
        if owner_id:
            extra["owner_id"] = owner_id
        cur = db.recurring_charges.find(barn_filter(user, extra), {"_id": 0}).sort("created_at", 1)
        return [doc async for doc in cur]

    @router.get("/recurring-charges/{rc_id}")
    async def get_recurring_charge(rc_id: str, user=Depends(get_current_user)):
        require(user, "recurring_charge:manage")
        doc = await db.recurring_charges.find_one(barn_filter(user, {"id": rc_id}), {"_id": 0})
        if not doc:
            raise HTTPException(404, "Recurring charge not found")
        return doc

    @router.patch("/recurring-charges/{rc_id}")
    async def update_recurring_charge(
        rc_id: str, body: RecurringChargeUpdate, request: Request, user=Depends(get_current_user)
    ):
        require(user, "recurring_charge:manage")
        scope = barn_filter(user, {"id": rc_id})
        existing = await db.recurring_charges.find_one(scope, {"_id": 0, "id": 1})
        if not existing:
            raise HTTPException(404, "Recurring charge not found")

        fields = body.model_dump(exclude_unset=True)
        if not fields:
            raise HTTPException(422, "No fields to update")
        _validate_cadence(fields.get("cadence"))
        _validate_scalars(
            fields.get("discount"), fields.get("tax_rate"),
            fields.get("day_of_month"), fields.get("due_days"),
        )
        updates = dict(fields)
        if "items" in fields:
            updates["items"] = _validate_items(body.items)
        updates["updated_at"] = _iso(_now_utc())
        await db.recurring_charges.update_one(scope, {"$set": updates})
        await audit.record(
            action="recurring_charge.updated", user=user, request=request,
            resource_type="recurring_charge", resource_id=rc_id,
            metadata={"updated_fields": sorted(fields.keys())},  # keys only, no values
        )
        return await db.recurring_charges.find_one(scope, {"_id": 0})

    @router.post("/recurring-charges/{rc_id}/deactivate")
    async def deactivate_recurring_charge(
        rc_id: str, body: DeactivateIn, request: Request, user=Depends(get_current_user)
    ):
        require(user, "recurring_charge:manage")
        scope = barn_filter(user, {"id": rc_id})
        existing = await db.recurring_charges.find_one(scope, {"_id": 0, "id": 1})
        if not existing:
            raise HTTPException(404, "Recurring charge not found")
        await db.recurring_charges.update_one(
            scope, {"$set": {"active": False, "updated_at": _iso(_now_utc())}}
        )
        await audit.record(
            action="recurring_charge.deactivated", user=user, request=request,
            resource_type="recurring_charge", resource_id=rc_id,
            metadata={"reason_provided": bool(body.reason)},  # no free-text reason stored in audit
        )
        return await db.recurring_charges.find_one(scope, {"_id": 0})

    return router
