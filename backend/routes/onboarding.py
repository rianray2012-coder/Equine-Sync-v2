"""routes/onboarding.py — Onboarding wizard, barn setup, CSV import.

Phase-F extraction (Feb 20 2026). Single self-contained module; all
collaborators injected via build_router(). ONBOARDING_STEPS lives here
as the authoritative source — server.py re-imports it for the reports
and invites modules that also need to reference step ids.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr


ONBOARDING_STEPS: List[Dict[str, Any]] = [
    {"id": "barn", "label": "Barn Profile", "required": True},
    {"id": "locations", "label": "Locations", "required": True},
    {"id": "owners", "label": "Owners & Clients", "required": True},
    {"id": "horses", "label": "Horse Profiles", "required": True},
    {"id": "riders", "label": "Riders", "required": False},
    {"id": "feed_templates", "label": "Feed Templates", "required": True},
    {"id": "inventory", "label": "Inventory", "required": False},
    {"id": "staff", "label": "Team & Staff", "required": False},
    {"id": "schedules", "label": "Recurring Schedules", "required": False},
    {"id": "review", "label": "Review & Launch", "required": True},
]


class BarnSettings(BaseModel):
    name: Optional[str] = None
    facility_type: Optional[str] = None
    disciplines: Optional[List[str]] = []
    address: Optional[str] = None
    timezone: Optional[str] = "America/New_York"
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None


class LocationIn(BaseModel):
    type: str
    name: str
    capacity: Optional[int] = 1
    notes: Optional[str] = None


class FeedTemplateIn(BaseModel):
    meal: str
    hay_type: Optional[str] = None
    hay_lbs: Optional[float] = 0
    grain_type: Optional[str] = None
    grain_lbs: Optional[float] = 0
    supplements: Optional[str] = None
    med_timing: Optional[str] = None
    instructions: Optional[str] = None


class InventoryIn(BaseModel):
    category: str
    name: str
    unit: str = "lbs"
    quantity: float = 0
    reorder_at: Optional[float] = 0
    vendor: Optional[str] = None
    cost_per_unit: Optional[float] = 0
    notes: Optional[str] = None


class RecurringScheduleIn(BaseModel):
    type: str
    name: str
    days_of_week: Optional[List[str]] = []
    time: Optional[str] = None
    location_id: Optional[str] = None
    notes: Optional[str] = None


class StaffInviteIn(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: str
    permissions: Optional[List[str]] = []


class ProgressPatch(BaseModel):
    step_id: Optional[str] = None
    status: Optional[str] = None
    current_step: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class CsvPreviewBody(BaseModel):
    kind: str
    csv_text: str


class CsvCommitBody(BaseModel):
    kind: str
    rows: List[Dict[str, Any]]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _deep_merge(base: dict, patch: dict) -> dict:
    """Recursively merge patch into base. dict values are merged, others replaced."""
    out = dict(base or {})
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _parse_csv(text: str) -> List[Dict[str, str]]:
    import csv
    import io
    reader = csv.DictReader(io.StringIO(text.strip()))
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            for row in reader]


def build_router(*, db, get_current_user, require_setup_role, roles: List[str],
                  list_collection, clean, new_id) -> APIRouter:
    router = APIRouter(tags=["onboarding"])

    # ---------- Wizard state ----------

    @router.get("/onboarding/steps")
    async def get_steps():
        return {"steps": ONBOARDING_STEPS}

    async def _ensure_progress(user) -> dict:
        doc = await db.onboarding_progress.find_one({"user_id": user["id"]}, {"_id": 0})
        if doc:
            return doc
        doc = {
            "user_id": user["id"],
            "steps": {s["id"]: "pending" for s in ONBOARDING_STEPS},
            "current_step": ONBOARDING_STEPS[0]["id"],
            "data": {},
            "completed": False,
            "created_at": _iso(_now_utc()),
            "updated_at": _iso(_now_utc()),
        }
        await db.onboarding_progress.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/onboarding/progress")
    async def get_progress(user=Depends(get_current_user)):
        doc = await _ensure_progress(user)
        completed = sum(1 for v in doc.get("steps", {}).values() if v == "complete")
        doc["percent"] = round(100 * completed / len(ONBOARDING_STEPS))
        return doc

    @router.patch("/onboarding/progress")
    async def patch_progress(body: ProgressPatch, user=Depends(get_current_user)):
        doc = await db.onboarding_progress.find_one({"user_id": user["id"]})
        if not doc:
            await _ensure_progress(user)
            doc = await db.onboarding_progress.find_one({"user_id": user["id"]})
        update: Dict[str, Any] = {"updated_at": _iso(_now_utc())}
        if body.step_id and body.status:
            update[f"steps.{body.step_id}"] = body.status
        if body.current_step:
            update["current_step"] = body.current_step
        if body.data:
            existing = doc.get("data", {}) or {}
            update["data"] = _deep_merge(existing, body.data)
        await db.onboarding_progress.update_one({"user_id": user["id"]}, {"$set": update})
        fresh = await db.onboarding_progress.find_one({"user_id": user["id"]}, {"_id": 0})
        completed_steps = sum(1 for v in fresh.get("steps", {}).values() if v == "complete")
        fresh["percent"] = round(100 * completed_steps / len(ONBOARDING_STEPS))
        return fresh

    @router.post("/onboarding/complete")
    async def complete_onboarding(user=Depends(get_current_user)):
        await db.onboarding_progress.update_one(
            {"user_id": user["id"]},
            {"$set": {"completed": True, "completed_at": _iso(_now_utc())}},
        )
        return {"ok": True}

    @router.post("/onboarding/reset")
    async def reset_onboarding(user=Depends(get_current_user)):
        await db.onboarding_progress.update_one(
            {"user_id": user["id"]},
            {"$set": {
                "completed": False,
                "completed_at": None,
                "steps": {s["id"]: "pending" for s in ONBOARDING_STEPS},
                "current_step": ONBOARDING_STEPS[0]["id"],
                "updated_at": _iso(_now_utc()),
            }},
            upsert=True,
        )
        return {"ok": True}

    # ---------- Barn settings ----------

    @router.get("/barn")
    async def get_barn(user=Depends(get_current_user)):
        doc = await db.barn.find_one({"id": "primary"}, {"_id": 0})
        if not doc:
            doc = {"id": "primary", "name": "", "facility_type": "boarding",
                   "disciplines": [], "address": "", "timezone": "America/New_York",
                   "contact_email": "", "contact_phone": "", "logo_url": "", "banner_url": ""}
        return doc

    @router.put("/barn")
    async def update_barn(body: BarnSettings, user=Depends(get_current_user)):
        require_setup_role(user)
        doc = body.model_dump()
        doc["id"] = "primary"
        doc["updated_at"] = _iso(_now_utc())
        await db.barn.update_one({"id": "primary"}, {"$set": doc}, upsert=True)
        return await db.barn.find_one({"id": "primary"}, {"_id": 0})

    # ---------- Locations ----------

    @router.get("/locations")
    async def list_locations(user=Depends(get_current_user)):
        return await list_collection("locations")

    @router.post("/locations")
    async def create_location(body: LocationIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        await db.locations.insert_one(doc)
        return clean(doc)

    @router.delete("/locations/{loc_id}")
    async def delete_location(loc_id: str, user=Depends(get_current_user)):
        await db.locations.delete_one({"id": loc_id})
        return {"ok": True}

    # ---------- Feed templates ----------

    @router.get("/feed-templates")
    async def list_feed_templates(user=Depends(get_current_user)):
        return await list_collection("feed_templates")

    @router.post("/feed-templates")
    async def create_feed_template(body: FeedTemplateIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        await db.feed_templates.insert_one(doc)
        return clean(doc)

    @router.delete("/feed-templates/{tid}")
    async def delete_feed_template(tid: str, user=Depends(get_current_user)):
        await db.feed_templates.delete_one({"id": tid})
        return {"ok": True}

    # ---------- Inventory ----------

    @router.get("/inventory")
    async def list_inventory(user=Depends(get_current_user)):
        items = await list_collection("inventory")
        for it in items:
            it["low_stock"] = (
                (it.get("reorder_at") or 0) > 0
                and (it.get("quantity") or 0) <= (it.get("reorder_at") or 0)
            )
        return items

    @router.post("/inventory")
    async def create_inventory(body: InventoryIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        await db.inventory.insert_one(doc)
        return clean(doc)

    @router.delete("/inventory/{iid}")
    async def delete_inventory(iid: str, user=Depends(get_current_user)):
        await db.inventory.delete_one({"id": iid})
        return {"ok": True}

    # ---------- Recurring Schedules ----------

    @router.get("/recurring-schedules")
    async def list_rs(user=Depends(get_current_user)):
        return await list_collection("recurring_schedules")

    @router.post("/recurring-schedules")
    async def create_rs(body: RecurringScheduleIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        doc.update({"id": new_id(), "created_at": _iso(_now_utc())})
        await db.recurring_schedules.insert_one(doc)
        return clean(doc)

    @router.delete("/recurring-schedules/{sid}")
    async def delete_rs(sid: str, user=Depends(get_current_user)):
        await db.recurring_schedules.delete_one({"id": sid})
        return {"ok": True}

    # ---------- Staff Invites (lightweight onboarding-side store) ----------

    @router.get("/staff-invites")
    async def list_invites(user=Depends(get_current_user)):
        return await list_collection("staff_invites")

    @router.post("/staff-invites")
    async def create_invite(body: StaffInviteIn, user=Depends(get_current_user)):
        require_setup_role(user)
        if body.role not in roles:
            raise HTTPException(400, "Invalid role")
        if await db.staff_invites.find_one({"email": body.email.lower()}):
            raise HTTPException(409, "Already invited")
        if await db.users.find_one({"email": body.email.lower()}):
            raise HTTPException(409, "User already exists")
        doc = body.model_dump()
        doc["email"] = doc["email"].lower()
        doc.update({"id": new_id(), "status": "pending",
                    "invited_by": user["full_name"],
                    "created_at": _iso(_now_utc())})
        await db.staff_invites.insert_one(doc)
        return clean(doc)

    @router.delete("/staff-invites/{sid}")
    async def delete_invite(sid: str, user=Depends(get_current_user)):
        await db.staff_invites.delete_one({"id": sid})
        return {"ok": True}

    # ---------- CSV import ----------

    @router.post("/onboarding/csv-preview")
    async def csv_preview(body: CsvPreviewBody, user=Depends(get_current_user)):
        try:
            rows = _parse_csv(body.csv_text)
        except Exception as e:
            raise HTTPException(400, f"Invalid CSV: {e}")
        if not rows:
            return {"rows": [], "duplicates": [], "count": 0}

        duplicates: List[str] = []
        if body.kind == "horses":
            existing_names = {
                h["name"].lower()
                for h in await db.horses.find({}, {"_id": 0, "name": 1}).to_list(1000)
            }
            for r in rows:
                if (r.get("name") or "").lower() in existing_names:
                    duplicates.append(r.get("name"))
        elif body.kind == "owners":
            existing = {
                o.get("email", "").lower()
                for o in await db.owners.find({}, {"_id": 0, "email": 1}).to_list(1000)
            }
            for r in rows:
                if (r.get("email") or "").lower() in existing:
                    duplicates.append(r.get("email"))
        return {"rows": rows, "duplicates": duplicates, "count": len(rows)}

    @router.post("/onboarding/csv-commit")
    async def csv_commit(body: CsvCommitBody, user=Depends(get_current_user)):
        created = 0
        skipped = 0
        if body.kind == "horses":
            existing_names = {
                h["name"].lower()
                for h in await db.horses.find({}, {"_id": 0, "name": 1}).to_list(2000)
            }
            owners_map = {
                o.get("full_name", "").lower(): o["id"]
                for o in await db.owners.find({}, {"_id": 0}).to_list(2000)
            }

            def _maybe_int(v):
                try:
                    return int(float(v)) if v not in (None, "") else None
                except Exception:
                    return None

            def _maybe_float(v):
                try:
                    return float(v) if v not in (None, "") else None
                except Exception:
                    return None

            for r in body.rows:
                name = (r.get("name") or "").strip()
                if not name:
                    continue
                if name.lower() in existing_names:
                    skipped += 1
                    continue
                existing_names.add(name.lower())
                doc = {
                    "id": new_id(),
                    "name": name,
                    "barn_name": r.get("barn_name") or name,
                    "breed": r.get("breed"),
                    "age": _maybe_int(r.get("age")),
                    "color": r.get("color"),
                    "height_hands": _maybe_float(r.get("height_hands")),
                    "discipline": r.get("discipline"),
                    "stall": r.get("stall"),
                    "owner_id": (owners_map.get((r.get("owner") or "").lower())
                                 or owners_map.get((r.get("owner_name") or "").lower())),
                    "status": r.get("status") or "active",
                    "wellness_score": _maybe_int(r.get("wellness_score")) or 85,
                    "allergies": [a.strip() for a in (r.get("allergies") or "").split(";") if a.strip()],
                    "feed_plan": r.get("feed_plan"),
                    "turnout_group": r.get("turnout_group"),
                    "behavior_flags": [b.strip() for b in (r.get("behavior_flags") or "").split(";") if b.strip()],
                    "photo_url": r.get("photo_url"),
                    "created_at": _iso(_now_utc()),
                }
                await db.horses.insert_one(doc)
                created += 1
        elif body.kind == "owners":
            existing_emails = {
                o.get("email", "").lower()
                for o in await db.owners.find({}, {"_id": 0, "email": 1}).to_list(2000)
                if o.get("email")
            }
            for r in body.rows:
                name = (r.get("full_name") or r.get("name") or "").strip()
                email = (r.get("email") or "").strip().lower()
                if not name:
                    continue
                if email and email in existing_emails:
                    skipped += 1
                    continue
                if email:
                    existing_emails.add(email)
                doc = {
                    "id": new_id(),
                    "full_name": name,
                    "email": email or None,
                    "phone": r.get("phone"),
                    "horses": [],
                    "billing_preferences": r.get("billing_preferences"),
                    "emergency_contact": r.get("emergency_contact"),
                    "waiver_signed": (r.get("waiver_signed") or "").lower() in ("yes", "true", "1"),
                    "created_at": _iso(_now_utc()),
                }
                await db.owners.insert_one(doc)
                created += 1
        else:
            raise HTTPException(400, "Unsupported kind")
        return {"created": created, "skipped": skipped}

    @router.get("/onboarding/csv-template")
    async def csv_template(kind: str):
        templates = {
            "horses": "name,breed,age,color,height_hands,discipline,stall,owner,status,wellness_score,allergies,feed_plan,turnout_group,behavior_flags,photo_url\nValentino,Hanoverian,11,Bay,16.3,Show Jumping,Stall 1,Charlotte Vance,active,92,Sweet itch,2lb grain + 6lb hay,Geldings A,Solo turnout,https://example.com/photo.jpg",
            "owners": "full_name,email,phone,emergency_contact,billing_preferences,waiver_signed\nCharlotte Vance,charlotte@example.com,+1 555 0142,Edward Vance +1 555 0143,monthly_card,yes",
        }
        text = templates.get(kind)
        if not text:
            raise HTTPException(400, "Unknown template")
        return {"text": text, "filename": f"equinesync_{kind}_template.csv"}

    return router
