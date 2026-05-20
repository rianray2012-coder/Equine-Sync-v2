"""routes/care.py — care records: horses, owners, riders, medications,
vet, farrier, injuries, wellness.

Phase-F final sweep extraction (Feb 20 2026). All handlers are trivial
CRUD over MongoDB collections; they share the `list_collection`, `clean`
and `new_id` helpers from server.py. Models live here too because they
are not shared with any other route module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ---------------- Models ----------------

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


class OwnerIn(BaseModel):
    full_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    horses: Optional[List[str]] = []
    photo_url: Optional[str] = None


class RiderIn(BaseModel):
    full_name: str
    age: Optional[int] = None
    skill_level: str = "beginner"
    goals: Optional[str] = None
    trainer_id: Optional[str] = None
    emergency_contact: Optional[str] = None
    photo_url: Optional[str] = None


class MedicationIn(BaseModel):
    horse_id: str
    name: str
    dosage: str
    route: Optional[str] = "oral"
    frequency: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    prescribing_vet: Optional[str] = None
    notes: Optional[str] = None
    times: Optional[List[str]] = []


class MedLogIn(BaseModel):
    medication_id: str
    scheduled_time: str
    status: str
    notes: Optional[str] = None


class VetRecordIn(BaseModel):
    horse_id: str
    type: str
    title: str
    date: str
    vet_name: Optional[str] = None
    notes: Optional[str] = None
    document_url: Optional[str] = None
    cost: Optional[float] = 0


class InjuryIn(BaseModel):
    horse_id: str
    title: str
    description: Optional[str] = None
    status: str = "active"
    severity: str = "mild"
    start_date: Optional[str] = None
    rehab_plan: Optional[str] = None


class WellnessIn(BaseModel):
    horse_id: str
    appetite: int = 5
    water_intake: int = 5
    energy: int = 5
    body_condition: float = 5.0
    coat_quality: int = 5
    notes: Optional[str] = None
    status: str = "normal"


class FeedTaskIn(BaseModel):
    horse_id: str
    meal: str
    ration: str
    instructions: Optional[str] = None
    completed: bool = False
    completed_by: Optional[str] = None


def build_router(*, db, get_current_user, list_collection, clean, new_id) -> APIRouter:
    router = APIRouter(tags=["care"])

    # ---------------- Horses ----------------

    @router.get("/horses")
    async def list_horses(user=Depends(get_current_user)):
        return await list_collection("horses")

    @router.post("/horses")
    async def create_horse(body: HorseIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        await db.horses.insert_one(doc)
        return clean(doc)

    @router.get("/horses/{horse_id}")
    async def get_horse(horse_id: str, user=Depends(get_current_user)):
        h = await db.horses.find_one({"id": horse_id}, {"_id": 0})
        if not h:
            raise HTTPException(404, "Horse not found")
        return h

    @router.patch("/horses/{horse_id}")
    async def update_horse(horse_id: str, body: Dict[str, Any], user=Depends(get_current_user)):
        await db.horses.update_one({"id": horse_id}, {"$set": body})
        return await db.horses.find_one({"id": horse_id}, {"_id": 0})

    # ---------------- Owners ----------------

    @router.get("/owners")
    async def list_owners(user=Depends(get_current_user)):
        return await list_collection("owners")

    @router.post("/owners")
    async def create_owner(body: OwnerIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        await db.owners.insert_one(doc)
        return clean(doc)

    # ---------------- Riders ----------------

    @router.get("/riders")
    async def list_riders(user=Depends(get_current_user)):
        return await list_collection("riders")

    @router.post("/riders")
    async def create_rider(body: RiderIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        await db.riders.insert_one(doc)
        return clean(doc)

    # ---------------- Medications ----------------

    @router.get("/medications")
    async def list_meds(horse_id: Optional[str] = None, user=Depends(get_current_user)):
        q = {"horse_id": horse_id} if horse_id else {}
        return await list_collection("medications", q)

    @router.post("/medications")
    async def create_med(body: MedicationIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        await db.medications.insert_one(doc)
        return clean(doc)

    @router.get("/medication-logs")
    async def list_med_logs(user=Depends(get_current_user)):
        return await list_collection("medication_logs", sort_field="scheduled_time")

    @router.post("/medication-logs")
    async def create_med_log(body: MedLogIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        doc.update({"id": new_id(), "completed_by": user["id"], "completed_at": _iso(_now_utc())})
        await db.medication_logs.insert_one(doc)
        return clean(doc)

    # ---------------- Feed Tasks (legacy collection — kept for back-compat) ----------------

    @router.get("/feed-tasks")
    async def list_feed(date_str: Optional[str] = None, user=Depends(get_current_user)):
        q = {"date": date_str} if date_str else {}
        return await list_collection("feed_tasks", q)

    @router.post("/feed-tasks/{task_id}/complete")
    async def complete_feed(task_id: str, user=Depends(get_current_user)):
        await db.feed_tasks.update_one(
            {"id": task_id},
            {"$set": {"completed": True, "completed_by": user["full_name"], "completed_at": _iso(_now_utc())}},
        )
        return await db.feed_tasks.find_one({"id": task_id}, {"_id": 0})

    # ---------------- Vet records ----------------

    @router.get("/vet-records")
    async def list_vet(horse_id: Optional[str] = None, user=Depends(get_current_user)):
        q = {"horse_id": horse_id} if horse_id else {}
        return await list_collection("vet_records", q, sort_field="date")

    @router.post("/vet-records")
    async def create_vet(body: VetRecordIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        await db.vet_records.insert_one(doc)
        return clean(doc)

    # ---------------- Farrier history (engine-projected) ----------------

    @router.get("/farrier-history")
    async def list_farrier(horse_id: Optional[str] = None, user=Depends(get_current_user)):
        q = {"horse_id": horse_id} if horse_id else {}
        return await db.farrier_history.find(q, {"_id": 0}).sort("date", -1).to_list(500)

    # ---------------- Injuries ----------------

    @router.get("/injuries")
    async def list_injuries(horse_id: Optional[str] = None, user=Depends(get_current_user)):
        q = {"horse_id": horse_id} if horse_id else {}
        return await list_collection("injuries", q)

    @router.post("/injuries")
    async def create_injury(body: InjuryIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        await db.injuries.insert_one(doc)
        return clean(doc)

    # ---------------- Wellness ----------------

    @router.get("/wellness")
    async def list_wellness(horse_id: Optional[str] = None, user=Depends(get_current_user)):
        q = {"horse_id": horse_id} if horse_id else {}
        return await list_collection("wellness", q, sort_field="created_at")

    @router.post("/wellness")
    async def create_wellness(body: WellnessIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        await db.wellness.insert_one(doc)
        # Bump horse wellness_score using the same heuristic as before.
        avg = (body.appetite + body.water_intake + body.energy + body.coat_quality) * 5
        await db.horses.update_one({"id": body.horse_id}, {"$set": {"wellness_score": min(100, avg)}})
        return clean(doc)

    return router
