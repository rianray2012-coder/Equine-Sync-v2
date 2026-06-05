"""routes/operations.py — operational records: lessons, training,
messages, service requests, incidents.

Phase-F final extraction (Feb 20 2026). Trivial CRUD over MongoDB
collections, sharing list_collection/clean/new_id helpers. The
service-request approve/decline flows carry their own role gating
(admin/barn_manager/trainer) plus a pending-state guard so re-mutation
returns 409.

Note: invoice/billing routes were extracted to `routes/billing.py` in Phase 3F.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.permissions import require
from core.tenancy import barn_filter, stamp_barn


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ---------------- Models ----------------

class LessonIn(BaseModel):
    rider_id: str
    horse_id: Optional[str] = None
    trainer_id: Optional[str] = None
    start_time: str
    duration_min: int = 60
    focus: Optional[str] = None
    notes: Optional[str] = None
    completed: bool = False


class TrainingSessionIn(BaseModel):
    horse_id: str
    trainer_id: Optional[str] = None
    date: str
    discipline: Optional[str] = None
    exercises: Optional[str] = None
    notes: Optional[str] = None
    rating: Optional[int] = None
    homework: Optional[str] = None


class MessageIn(BaseModel):
    to_role: Optional[str] = None
    to_user_id: Optional[str] = None
    subject: str
    body: str
    visibility: str = "staff_only"


class ServiceRequestIn(BaseModel):
    horse_id: str
    type: str
    details: Optional[str] = None
    requested_date: Optional[str] = None


class DeclineSRBody(BaseModel):
    reason: Optional[str] = None


class IncidentIn(BaseModel):
    horse_id: Optional[str] = None
    type: str
    title: str
    description: str
    severity: str = "moderate"
    occurred_at: str
    follow_up: Optional[str] = None


def build_router(*, db, get_current_user, list_collection, clean, new_id) -> APIRouter:
    router = APIRouter(tags=["operations"])

    # ---------------- Lessons ----------------

    @router.get("/lessons")
    async def list_lessons(user=Depends(get_current_user)):
        return await list_collection("lessons", barn_filter(user), sort_field="start_time")

    @router.post("/lessons")
    async def create_lesson(body: LessonIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        # Best-effort name resolution so list views render without an extra
        # lookup hop. Missing references are tolerated (operationally a
        # rider record may be added later, after the lesson is sketched in).
        # Phase 4B-3: all enrichment lookups are barn-scoped so a cross-barn id
        # resolves to None (no cross-barn name leak); tolerate-missing preserved.
        rider = await db.riders.find_one(barn_filter(user, {"id": body.rider_id}), {"_id": 0, "full_name": 1})
        doc["rider_name"] = rider["full_name"] if rider else None
        if body.horse_id:
            horse = await db.horses.find_one(barn_filter(user, {"id": body.horse_id}), {"_id": 0, "name": 1})
            doc["horse_name"] = horse["name"] if horse else None
        if body.trainer_id:
            trainer = await db.users.find_one(barn_filter(user, {"id": body.trainer_id}), {"_id": 0, "full_name": 1})
            doc["trainer_name"] = trainer["full_name"] if trainer else None
        else:
            doc["trainer_name"] = user.get("full_name")
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        stamp_barn(user, doc)
        await db.lessons.insert_one(doc)
        return clean(doc)

    # ---------------- Training ----------------

    @router.get("/training")
    async def list_training(horse_id: Optional[str] = None, user=Depends(get_current_user)):
        extra = {"horse_id": horse_id} if horse_id else {}
        return await list_collection("training", barn_filter(user, extra), sort_field="date")

    @router.post("/training")
    async def create_training(body: TrainingSessionIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        horse = await db.horses.find_one(barn_filter(user, {"id": body.horse_id}), {"_id": 0, "name": 1})
        doc["horse_name"] = horse["name"] if horse else None
        if body.trainer_id:
            trainer = await db.users.find_one(barn_filter(user, {"id": body.trainer_id}), {"_id": 0, "full_name": 1})
            doc["trainer_name"] = trainer["full_name"] if trainer else None
        else:
            doc["trainer_name"] = user.get("full_name")
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        stamp_barn(user, doc)
        await db.training.insert_one(doc)
        return clean(doc)

    # ---------------- Messages ----------------

    @router.get("/messages")
    async def list_messages(user=Depends(get_current_user)):
        return await list_collection("messages", barn_filter(user), sort_field="created_at")

    @router.post("/messages")
    async def create_message(body: MessageIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        doc.update({
            "id": new_id(),
            "from_user_id": user["id"],
            "from_name": user["full_name"],
            "created_at": _iso(_now_utc()),
            "read": False,
        })
        stamp_barn(user, doc)
        await db.messages.insert_one(doc)
        return clean(doc)

    # ---------------- Service Requests ----------------

    @router.get("/service-requests")
    async def list_sr(user=Depends(get_current_user)):
        return await list_collection("service_requests", barn_filter(user), sort_field="created_at")

    @router.post("/service-requests")
    async def create_sr(body: ServiceRequestIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        doc.update({
            "id": new_id(),
            "requested_by": user["id"],
            "requester_name": user["full_name"],
            "status": "pending",
            "created_at": _iso(_now_utc()),
        })
        stamp_barn(user, doc)
        await db.service_requests.insert_one(doc)
        return clean(doc)

    @router.post("/service-requests/{sr_id}/approve")
    async def approve_sr(sr_id: str, user=Depends(get_current_user)):
        require(user, "service_request:approve")
        scope = barn_filter(user, {"id": sr_id})
        existing = await db.service_requests.find_one(scope, {"_id": 0, "status": 1})
        if not existing:
            raise HTTPException(404, "Service request not found")
        if existing.get("status") != "pending":
            raise HTTPException(409, f"Request is already {existing.get('status')}")
        await db.service_requests.update_one(
            scope,
            {"$set": {"status": "approved",
                      "approved_at": _iso(_now_utc()),
                      "approved_by_user_id": user["id"]}},
        )
        return await db.service_requests.find_one(scope, {"_id": 0})

    @router.post("/service-requests/{sr_id}/decline")
    async def decline_sr(sr_id: str, body: Optional[DeclineSRBody] = None,
                          user=Depends(get_current_user)):
        require(user, "service_request:decline")
        scope = barn_filter(user, {"id": sr_id})
        existing = await db.service_requests.find_one(scope, {"_id": 0, "status": 1})
        if not existing:
            raise HTTPException(404, "Service request not found")
        if existing.get("status") != "pending":
            raise HTTPException(409, f"Request is already {existing.get('status')}")
        reason = (body.reason if body else None) or "Request declined."
        await db.service_requests.update_one(
            scope,
            {"$set": {
                "status": "declined",
                "declined_at": _iso(_now_utc()),
                "declined_by_user_id": user["id"],
                "decline_reason": reason[:500],
            }},
        )
        return await db.service_requests.find_one(scope, {"_id": 0})

    # ---------------- Incidents ----------------

    @router.get("/incidents")
    async def list_incidents(user=Depends(get_current_user)):
        return await list_collection("incidents", barn_filter(user), sort_field="occurred_at")

    @router.post("/incidents")
    async def create_incident(body: IncidentIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        if body.horse_id:
            horse = await db.horses.find_one(barn_filter(user, {"id": body.horse_id}), {"_id": 0, "name": 1})
            doc["horse_name"] = horse["name"] if horse else None
        else:
            doc["horse_name"] = None
        doc.update({"id": new_id(),
                    "status": "open",
                    "reported_by": user["full_name"],
                    "created_at": _iso(_now_utc())})
        stamp_barn(user, doc)
        await db.incidents.insert_one(doc)
        return clean(doc)

    return router
