"""routes/care.py — care records: owners, riders, medications,
vet, farrier, injuries, wellness, feed-tasks.

Phase-F final sweep extraction (Feb 20 2026). All handlers are trivial
CRUD over MongoDB collections; they share the `list_collection`, `clean`
and `new_id` helpers from server.py. Models live here too because they
are not shared with any other route module.

Note: horse-profile CRUD was extracted to `routes/horses.py` in Phase 3C.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from core.tenancy import barn_filter, stamp_barn


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ---------------- Models ----------------

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
    # Phase 6B: optional client-supplied idempotency key. When provided, repeat
    # posts with the same (barn, client_log_id) return the same log instead of
    # inserting a duplicate. Omitting it preserves the original insert behavior.
    client_log_id: Optional[str] = None


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

    # ---------------- Phase 6A: care input integrity helpers ----------------
    # Validate that a referenced id belongs to the caller's barn BEFORE writing
    # a care record. Cross-barn and absent ids return the same generic 404 so
    # there is no existence leak (consistent with the 4E isolation contract).

    async def _require_horse(user, horse_id: str) -> None:
        if not await db.horses.find_one(barn_filter(user, {"id": horse_id}), {"_id": 0, "id": 1}):
            raise HTTPException(404, "Horse not found")

    async def _require_medication(user, medication_id: str) -> None:
        if not await db.medications.find_one(
            barn_filter(user, {"id": medication_id}), {"_id": 0, "id": 1}
        ):
            raise HTTPException(404, "Medication not found")

    # ---------------- Owners ----------------

    @router.get("/owners")
    async def list_owners(user=Depends(get_current_user)):
        # Phase 6C: deterministic newest-first ordering (created_at desc).
        return await list_collection("owners", barn_filter(user), sort_field="created_at")

    @router.post("/owners")
    async def create_owner(body: OwnerIn, user=Depends(get_current_user)):
        # Phase 6A: every referenced horse must belong to the caller's barn.
        for horse_id in (body.horses or []):
            await _require_horse(user, horse_id)
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        stamp_barn(user, doc)
        await db.owners.insert_one(doc)
        return clean(doc)

    # ---------------- Riders ----------------

    @router.get("/riders")
    async def list_riders(user=Depends(get_current_user)):
        # Phase 6C: deterministic newest-first ordering (created_at desc).
        return await list_collection("riders", barn_filter(user), sort_field="created_at")

    @router.post("/riders")
    async def create_rider(body: RiderIn, user=Depends(get_current_user)):
        # Phase 6A backlog (deferred): rider.trainer_id references a user/staff
        # record (cross-domain into `users`), outside the care-records boundary.
        # Validating trainer barn membership is tracked for a later phase.
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        stamp_barn(user, doc)
        await db.riders.insert_one(doc)
        return clean(doc)

    # ---------------- Medications ----------------

    @router.get("/medications")
    async def list_meds(horse_id: Optional[str] = None, user=Depends(get_current_user)):
        extra = {"horse_id": horse_id} if horse_id else {}
        # Phase 6C: deterministic newest-first ordering (created_at desc).
        return await list_collection("medications", barn_filter(user, extra), sort_field="created_at")

    @router.post("/medications")
    async def create_med(body: MedicationIn, user=Depends(get_current_user)):
        await _require_horse(user, body.horse_id)
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        stamp_barn(user, doc)
        await db.medications.insert_one(doc)
        return clean(doc)

    @router.get("/medication-logs")
    async def list_med_logs(medication_id: Optional[str] = None, user=Depends(get_current_user)):
        # Phase 6C: optional barn-scoped medication_id filter (parity with the
        # horse_id filter on the other care lists). A foreign/unknown id simply
        # returns an empty array (barn_filter scopes it) — no 404, no leak.
        extra = {"medication_id": medication_id} if medication_id else {}
        return await list_collection(
            "medication_logs", barn_filter(user, extra), sort_field="scheduled_time"
        )

    @router.post("/medication-logs")
    async def create_med_log(body: MedLogIn, user=Depends(get_current_user)):
        await _require_medication(user, body.medication_id)
        doc = body.model_dump()
        doc.update({"id": new_id(), "completed_by": user["id"], "completed_at": _iso(_now_utc())})
        stamp_barn(user, doc)
        # Phase 6B: opt-in idempotency. With a client_log_id, atomically upsert
        # keyed by (barn_id, client_log_id) so repeat submits return the first
        # log and never duplicate. Without it, behave exactly as before.
        if body.client_log_id:
            key = barn_filter(user, {"client_log_id": body.client_log_id})
            await db.medication_logs.update_one(key, {"$setOnInsert": doc}, upsert=True)
            return clean(await db.medication_logs.find_one(key, {"_id": 0}))
        # No key: preserve the original shape — don't persist/return client_log_id: null.
        doc.pop("client_log_id", None)
        await db.medication_logs.insert_one(doc)
        return clean(doc)

    # ---------------- Feed Tasks (legacy collection — kept for back-compat) ----------------

    @router.get("/feed-tasks")
    async def list_feed(date_str: Optional[str] = None, user=Depends(get_current_user)):
        extra = {"date": date_str} if date_str else {}
        # Phase 6C: deterministic newest-first ordering (created_at desc).
        return await list_collection("feed_tasks", barn_filter(user, extra), sort_field="created_at")

    @router.post("/feed-tasks/{task_id}/complete")
    async def complete_feed(task_id: str, user=Depends(get_current_user)):
        scope = barn_filter(user, {"id": task_id})
        if not await db.feed_tasks.find_one(scope, {"_id": 0}):
            raise HTTPException(404, "Feed task not found")
        # Phase 6B: idempotent completion — only set fields when not already
        # completed, so a re-complete preserves the original completer/timestamp.
        # Response shape is unchanged (still the feed-task doc).
        await db.feed_tasks.update_one(
            barn_filter(user, {"id": task_id, "completed": {"$ne": True}}),
            {"$set": {"completed": True, "completed_by": user["full_name"], "completed_at": _iso(_now_utc())}},
        )
        return await db.feed_tasks.find_one(scope, {"_id": 0})

    # ---------------- Vet records ----------------

    @router.get("/vet-records")
    async def list_vet(horse_id: Optional[str] = None, user=Depends(get_current_user)):
        # Phase 4B-7: read now barn-scoped — the task_engine completion hooks
        # stamp barn_id on engine-written vet_records (and the startup backfill
        # covers legacy rows), so barn_filter no longer hides engine-projected rows.
        extra = {"horse_id": horse_id} if horse_id else None
        return await list_collection("vet_records", barn_filter(user, extra), sort_field="date")

    @router.post("/vet-records")
    async def create_vet(body: VetRecordIn, user=Depends(get_current_user)):
        await _require_horse(user, body.horse_id)
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        stamp_barn(user, doc)
        await db.vet_records.insert_one(doc)
        return clean(doc)

    # ---------------- Farrier history (engine-projected) ----------------

    @router.get("/farrier-history")
    async def list_farrier(horse_id: Optional[str] = None, user=Depends(get_current_user)):
        # Phase 4B-7: read now barn-scoped — engine-written farrier_history rows
        # stamp barn_id (+ startup backfill for legacy rows). See vet-records note.
        # Phase 6C: harmonized to route through list_collection (date desc) — same
        # behavior as the bespoke .find().sort().to_list(500) it replaced.
        extra = {"horse_id": horse_id} if horse_id else None
        return await list_collection("farrier_history", barn_filter(user, extra), sort_field="date")

    # ---------------- Injuries ----------------

    @router.get("/injuries")
    async def list_injuries(horse_id: Optional[str] = None, user=Depends(get_current_user)):
        extra = {"horse_id": horse_id} if horse_id else {}
        # Phase 6C: deterministic newest-first ordering (created_at desc).
        return await list_collection("injuries", barn_filter(user, extra), sort_field="created_at")

    @router.post("/injuries")
    async def create_injury(body: InjuryIn, user=Depends(get_current_user)):
        await _require_horse(user, body.horse_id)
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        stamp_barn(user, doc)
        await db.injuries.insert_one(doc)
        return clean(doc)

    # ---------------- Wellness ----------------

    @router.get("/wellness")
    async def list_wellness(horse_id: Optional[str] = None, user=Depends(get_current_user)):
        extra = {"horse_id": horse_id} if horse_id else {}
        return await list_collection("wellness", barn_filter(user, extra), sort_field="created_at")

    @router.post("/wellness")
    async def create_wellness(body: WellnessIn, user=Depends(get_current_user)):
        # Phase 6A: reject a foreign/absent horse_id up front (no record written).
        await _require_horse(user, body.horse_id)
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        stamp_barn(user, doc)
        await db.wellness.insert_one(doc)
        # Bump horse wellness_score using the same heuristic as before.
        # Phase 4B-2: scope the horse update by barn so a cross-barn horse_id
        # can never trigger a side effect on another barn's horse.
        avg = (body.appetite + body.water_intake + body.energy + body.coat_quality) * 5
        await db.horses.update_one(barn_filter(user, {"id": body.horse_id}), {"$set": {"wellness_score": min(100, avg)}})
        return clean(doc)

    return router
