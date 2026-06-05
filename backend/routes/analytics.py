"""routes/analytics.py — Event tracking + onboarding funnel.

Extracted from server.py (Phase 3B). No API behavior change. The shared
internal ``_track`` helper remains in server.py (it is injected into several
routers); these are the public, authenticated analytics endpoints.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.tenancy import resolve_barn_id


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


class EventIn(BaseModel):
    name: str
    props: Optional[Dict[str, Any]] = {}


def build_router(db, get_current_user, require_setup_role) -> APIRouter:
    router = APIRouter(tags=["analytics"])

    @router.post("/events")
    async def track_event(body: EventIn, user=Depends(get_current_user)):
        await db.events.insert_one({
            "id": _new_id(), "name": body.name, "props": body.props or {},
            "user_id": user["id"], "user_role": user.get("role"),
            "barn_id": resolve_barn_id(user), "at": _now_iso(),
        })
        return {"ok": True}

    @router.get("/events/onboarding-funnel")
    async def onboarding_funnel(user=Depends(get_current_user)):
        require_setup_role(user)
        pipeline = [
            {"$match": {"name": {"$regex": "^onboarding\\."},
                        "barn_id": resolve_barn_id(user)}},
            {"$group": {"_id": "$name", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
        rows = await db.events.aggregate(pipeline).to_list(100)
        return [{"event": r["_id"], "count": r["count"]} for r in rows]

    return router
