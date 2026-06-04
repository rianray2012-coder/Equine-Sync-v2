"""routes/horses.py — core horse-profile CRUD.

Extracted from routes/care.py (Phase 3C). Horse-profile create/read/update/list
only. Behavior is identical to the previous care.py handlers (pure lift-and-shift;
no new validation or permission logic).

Intentional exception: ``GET /api/horses/{horse_id}/timeline`` remains in
``task_engine.py`` because it is a task-event projection/aggregation, not
horse-profile CRUD.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.tenancy import barn_filter, stamp_barn


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class HorseIn(BaseModel):
    name: str
    barn_name: Optional[str] = None
    breed: Optional[str] = None
    age: Optional[int] = None
    color: Optional[str] = None
    height_hands: Optional[float] = None
    discipline: Optional[str] = None
    owner_id: Optional[str] = None
    rider_id: Optional[str] = None
    trainer_id: Optional[str] = None
    stall: Optional[str] = None
    photo_url: Optional[str] = None
    allergies: Optional[List[str]] = []
    emergency_notes: Optional[str] = None
    insurance: Optional[str] = None
    wellness_score: Optional[int] = 85
    status: Optional[str] = "active"
    training_goals: Optional[str] = None
    feed_plan: Optional[str] = None
    turnout_group: Optional[str] = None
    behavior_flags: Optional[List[str]] = []


def build_router(*, db, get_current_user, list_collection, clean, new_id) -> APIRouter:
    router = APIRouter(tags=["horses"])

    @router.get("/horses")
    async def list_horses(user=Depends(get_current_user)):
        # Phase 4B-1: scope list reads to the caller's barn.
        return await list_collection("horses", barn_filter(user))

    @router.post("/horses")
    async def create_horse(body: HorseIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        # Phase 4B-1: stamp the caller's barn at write time.
        stamp_barn(user, doc)
        await db.horses.insert_one(doc)
        return clean(doc)

    @router.get("/horses/{horse_id}")
    async def get_horse(horse_id: str, user=Depends(get_current_user)):
        # Phase 4B-1: scope by id + barn; a cross-barn id 404s (no existence leak).
        h = await db.horses.find_one(barn_filter(user, {"id": horse_id}), {"_id": 0})
        if not h:
            raise HTTPException(404, "Horse not found")
        return h

    @router.patch("/horses/{horse_id}")
    async def update_horse(horse_id: str, body: Dict[str, Any], user=Depends(get_current_user)):
        scope = barn_filter(user, {"id": horse_id})
        existing = await db.horses.find_one(scope, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Horse not found")
        # Phase 4B-1: never allow a client to move a horse between barns
        # (or rewrite its id) via the free-form PATCH body.
        updates = {k: v for k, v in body.items() if k not in ("barn_id", "id")}
        if updates:
            await db.horses.update_one(scope, {"$set": updates})
        return await db.horses.find_one(scope, {"_id": 0})

    return router
