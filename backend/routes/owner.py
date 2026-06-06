"""routes/owner.py — Phase 7D-2: owner self-service reads (Owner Trust Layer).

Small, focused home for owner-facing, read-only views. First endpoint:
`GET /api/owner/upcoming` — a calm "Looking ahead" list of the owner's own
horses' upcoming appointment-like care (vet / farrier / rehab) in the next
14 days.

Strictly read-only over the existing `tasks` collection (same query shape the
owner digest/recap already use) — NO task-engine changes, NO email/digest changes.
Owner-only, barn-scoped, owned-horse scoped, with an owner-safe field whitelist
(no assignees, internal notes, or staffing fields leak).
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException

from core.tenancy import barn_filter

# Tunable look-ahead window (days) — kept here so it can be adjusted later.
UPCOMING_WINDOW_DAYS = 14
# Appointment-like, owner-safe categories only (no routine medication/feed/turnout).
UPCOMING_CATEGORIES = ["vet", "farrier", "rehab"]
_INACTIVE = ["completed", "skipped", "cancelled"]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def build_router(*, db, get_current_user) -> APIRouter:
    router = APIRouter(tags=["owner"])

    @router.get("/owner/upcoming")
    async def owner_upcoming(user=Depends(get_current_user)):
        if user.get("role") != "horse_owner":
            raise HTTPException(403, "This view is for horse owners")

        horses = await db.horses.find(
            barn_filter(user, {"owner_id": user["id"]}), {"_id": 0, "id": 1, "name": 1},
        ).to_list(500)
        if not horses:
            return []
        name_by_id = {h["id"]: h.get("name") for h in horses}

        now = datetime.now(timezone.utc)
        until = now + timedelta(days=UPCOMING_WINDOW_DAYS)
        query = barn_filter(user, {
            "linked_horse_ids": {"$in": list(name_by_id.keys())},
            "category": {"$in": UPCOMING_CATEGORIES},
            "status": {"$nin": _INACTIVE},
            "scheduled_at": {"$gte": _iso(now), "$lte": _iso(until)},
        })
        tasks = await db.tasks.find(query, {"_id": 0}).sort("scheduled_at", 1).to_list(100)

        # Owner-safe whitelist — never echo internal task fields.
        out = []
        for t in tasks:
            owned = [hid for hid in (t.get("linked_horse_ids") or []) if hid in name_by_id]
            hid = owned[0] if owned else None
            out.append({
                "id": t.get("id"),
                "category": t.get("category"),
                "title": t.get("title"),
                "scheduled_at": t.get("scheduled_at"),
                "horse_id": hid,
                "horse_name": name_by_id.get(hid),
            })
        return out

    return router
