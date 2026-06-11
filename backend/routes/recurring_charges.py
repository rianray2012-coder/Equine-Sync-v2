"""routes/recurring_charges.py — Phase 9B: recurring billing.

A *recurring charge* is a per-owner (optionally per-horse) billing template. 9B-1
defines the data contract (create / list / get / update / deactivate). **9B-2**
adds a manual, idempotent materializer (`POST /admin/recurring-charges/run`) that
turns eligible charges into invoices on a monthly cadence using the **9A
line-item structure + server-computed totals**. No scheduler, no payment
processor.

Backend-only. Management is gated to {admin, barn_manager} via the additive
`recurring_charge:manage` capability. All reads/writes are barn-scoped
(stamp_barn / barn_filter) and owner/horse references are validated against the
caller's barn. Emits light, non-sensitive Phase 5 audit events (fail-open).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

from core.tenancy import barn_filter, stamp_barn
from core.permissions import require
from core import audit
from routes.billing import LineItem, _normalize_line, compute_money  # reuse 9A line-item shape + math


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


class MaterializeIn(BaseModel):
    # Optional explicit billing period; defaults to the current UTC month.
    period: Optional[str] = None  # YYYY-MM


def _parse_iso_date(value, field):
    # Strict YYYY-MM-DD only (date.fromisoformat accepts other ISO forms).
    if not isinstance(value, str) or not _ISO_DATE_RE.match(value):
        raise HTTPException(422, f"{field} must be an ISO date (YYYY-MM-DD)")
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise HTTPException(422, f"{field} must be an ISO date (YYYY-MM-DD)")


def _validate_date_window(start_date, end_date):
    """Tighten 9B-1 dates: ISO `YYYY-MM-DD`, and `end_date >= start_date`."""
    sd = _parse_iso_date(start_date, "start_date")
    if end_date is not None:
        ed = _parse_iso_date(end_date, "end_date")
        if ed < sd:
            raise HTTPException(422, "end_date must be on or after start_date")


def _current_period() -> str:
    now = _now_utc()
    return f"{now.year:04d}-{now.month:02d}"


def _parse_period(period_key):
    m = re.fullmatch(r"(\d{4})-(\d{2})", period_key or "")
    if not m:
        raise HTTPException(422, "period must be in YYYY-MM format")
    year, month = int(m.group(1)), int(m.group(2))
    if not (1 <= month <= 12):
        raise HTTPException(422, "period month must be 01-12")
    return year, month


def _safe_iso(value):
    """Strict YYYY-MM-DD parse → date, or None (for defensive materialization skips)."""
    if not isinstance(value, str) or not _ISO_DATE_RE.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _eligible_for_period(rc, year, month) -> bool:
    """A recurring charge is eligible for `year-month` iff it is active, monthly,
    has valid ISO dates, has started on/before the period, and has not ended
    before it. Anything else is skipped *defensively* (never fails the run)."""
    if not rc.get("active"):
        return False
    if rc.get("cadence") != "monthly":
        return False
    sd = _safe_iso(rc.get("start_date"))
    if sd is None:
        return False  # invalid/legacy start_date — skip defensively
    period_first = date(year, month, 1)
    if date(sd.year, sd.month, 1) > period_first:
        return False  # not yet started
    end_raw = rc.get("end_date")
    if end_raw is not None:
        ed = _safe_iso(end_raw)
        if ed is None:
            return False  # invalid/legacy end_date — skip defensively
        if date(ed.year, ed.month, 1) < period_first:
            return False  # already ended
    return True


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
    """Charge total after discount/tax using the same shared 9A money math.
    Non-sensitive scalar — safe for audit metadata."""
    _, _, _, _, total = compute_money(items, discount, tax_rate)
    return total


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
        _validate_date_window(body.start_date, body.end_date)
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
        existing = await db.recurring_charges.find_one(scope, {"_id": 0, "id": 1, "start_date": 1, "end_date": 1})
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
        if "start_date" in fields or "end_date" in fields:
            eff_start = fields.get("start_date", existing.get("start_date"))
            eff_end = fields.get("end_date", existing.get("end_date"))
            _validate_date_window(eff_start, eff_end)
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

    @router.post("/admin/recurring-charges/run")
    async def run_materializer(body: MaterializeIn, request: Request, user=Depends(get_current_user)):
        """Phase 9B-2 — manual, idempotent materializer (no scheduler).

        Scans every recurring charge in the caller's barn and, for the target
        month, generates a 9A-structured invoice for each *eligible* charge that
        does not already have one for that period. Everything else (inactive,
        non-monthly, not-yet-started, ended, invalid legacy dates, or already
        generated) is skipped defensively and counted in `skipped_count` —
        never a run failure.
        """
        require(user, "recurring_charge:manage")
        period_key = body.period or _current_period()
        year, month = _parse_period(period_key)

        generated = 0
        skipped = 0
        generated_invoice_ids = []
        cur = db.recurring_charges.find(barn_filter(user, {}), {"_id": 0})
        async for rc in cur:
            if not _eligible_for_period(rc, year, month):
                skipped += 1
                continue
            # Dedup: one invoice per (barn, recurring_charge, period). Skip — never update.
            existing_inv = await db.invoices.find_one(
                barn_filter(user, {
                    "recurring_charge_id": rc["id"], "period_key": period_key, "source": "recurring",
                }),
                {"_id": 0, "id": 1},
            )
            if existing_inv:
                skipped += 1
                continue

            items = rc.get("items") or []
            subtotal, disc, rate, tax_amount, total = compute_money(
                items, rc.get("discount"), rc.get("tax_rate")
            )
            issue = date(year, month, int(rc.get("day_of_month") or 1))
            due = issue + timedelta(days=int(rc.get("due_days") or 0))
            doc = {
                "id": new_id(),
                "owner_id": rc["owner_id"],
                "horse_id": rc.get("horse_id"),
                "items": items,
                "subtotal": subtotal,
                "discount": disc,
                "tax_rate": rate,
                "tax_amount": tax_amount,
                "total": total,
                "due_date": due.isoformat(),
                "status": "open",
                "notes": rc.get("description"),
                "recurring_charge_id": rc["id"],
                "period_key": period_key,
                "source": "recurring",
                "created_at": _iso(_now_utc()),
            }
            stamp_barn(user, doc)
            try:
                await db.invoices.insert_one(doc)
            except DuplicateKeyError:
                # Lost a race against a concurrent run — treat as skipped.
                skipped += 1
                continue
            # Advance last_run_period monotonically — an older backfill run
            # (e.g. "2026-08" after "2026-10") must never regress it. Period keys
            # are zero-padded YYYY-MM, so lexical max == chronological max.
            new_last = max(rc.get("last_run_period") or "", period_key)
            await db.recurring_charges.update_one(
                barn_filter(user, {"id": rc["id"]}),
                {"$set": {"last_run_period": new_last}},
            )
            generated += 1
            generated_invoice_ids.append(doc["id"])

        await audit.record(
            action="recurring_charges.materialized", user=user, request=request,
            resource_type="billing_run", resource_id=period_key,
            metadata={"month": period_key, "generated_count": generated, "skipped_count": skipped},
        )
        return {
            "period": period_key,
            "generated_count": generated,
            "skipped_count": skipped,
            "generated_invoice_ids": generated_invoice_ids,
        }

    return router
