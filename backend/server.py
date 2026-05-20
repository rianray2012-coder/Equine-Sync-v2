from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path

# Load .env BEFORE importing any submodule that reads env vars at import time
# (e.g. routes/auth.py reads JWT_SECRET; auth_security.py reads JWT_EXP_HOURS).
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta, date
import bcrypt
import jwt as pyjwt
import secrets
import hashlib
import asyncio
from mailer import send as send_email, render as render_email
from task_engine import (
    build_router as build_task_engine_router,
    TaskEngine,
    seed_demo_templates,
    DEFAULT_TENANT_ID as TASK_TENANT_ID,
)
from auth_security import (
    JWT_EXP_HOURS,
    SecurityHeadersMiddleware,
    issue_refresh_token,
    consume_refresh_token,
    revoke_refresh_token,
    revoke_all_user_refresh_tokens,
    ensure_refresh_indexes,
)
from notifications import (
    build_router as build_notifications_router,
    start_dispatcher as start_notification_dispatcher,
    ensure_indexes as ensure_notification_indexes,
)
from routes.auth import build_router as build_auth_router
from owner_digest import (
    run_daily_digest_pass,
    send_digest_to_owner,
    build_digest_for_owner,
    render_digest_html,
    render_digest_text,
    ensure_digest_indexes,
)

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ.get('JWT_SECRET', 'change-me')
JWT_ALG = 'HS256'

app = FastAPI(title="EquineSync API")
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

# ---------------- helpers ----------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def iso(dt: datetime) -> str:
    return dt.isoformat()

def new_id() -> str:
    return str(uuid.uuid4())

def hash_pwd(p: str) -> str:
    return bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_pwd(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode('utf-8'), h.encode('utf-8'))
    except Exception:
        return False

def create_token(user_id: str, role: str) -> str:
    payload = {
        'sub': user_id,
        'role': role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXP_HOURS),
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

async def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = pyjwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"id": payload['sub']}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def require_setup_role(user):
    """Stable Owner / Admin / Barn Manager can edit barn-level setup."""
    if user.get("role") not in ("admin", "barn_manager"):
        raise HTTPException(status_code=403, detail="Owner / Barn Manager access required")

# ---------------- Models ----------------
ROLES = ["admin", "barn_manager", "trainer", "groom", "working_student",
         "horse_owner", "rider", "parent", "veterinarian", "farrier"]

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = "admin"

class LoginBody(BaseModel):
    email: EmailStr
    password: str

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
    status: Optional[str] = "active"  # active, stall_rest, rehab
    training_goals: Optional[str] = None
    feed_plan: Optional[str] = None
    turnout_group: Optional[str] = None
    behavior_flags: Optional[List[str]] = []

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
    times: Optional[List[str]] = []  # e.g. ["08:00", "20:00"]

class MedLogIn(BaseModel):
    medication_id: str
    scheduled_time: str
    status: str  # given, missed, skipped
    notes: Optional[str] = None

class FeedTaskIn(BaseModel):
    horse_id: str
    meal: str  # morning, midday, evening
    ration: str
    instructions: Optional[str] = None
    completed: bool = False
    completed_by: Optional[str] = None

class VetRecordIn(BaseModel):
    horse_id: str
    type: str  # vaccine, dental, exam, xray, lab, coggins, prescription
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
    status: str = "active"  # active, improving, monitoring, resolved, chronic
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
    status: str = "normal"  # normal, watch, concern, urgent

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

class RiderIn(BaseModel):
    full_name: str
    age: Optional[int] = None
    skill_level: str = "beginner"  # beginner, intermediate, advanced
    goals: Optional[str] = None
    trainer_id: Optional[str] = None
    emergency_contact: Optional[str] = None
    photo_url: Optional[str] = None

class OwnerIn(BaseModel):
    full_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    horses: Optional[List[str]] = []
    photo_url: Optional[str] = None

class InvoiceIn(BaseModel):
    owner_id: str
    horse_id: Optional[str] = None
    items: List[Dict[str, Any]]
    total: float
    due_date: str
    status: str = "open"  # open, paid, overdue
    notes: Optional[str] = None

class MessageIn(BaseModel):
    to_role: Optional[str] = None
    to_user_id: Optional[str] = None
    subject: str
    body: str
    visibility: str = "staff_only"  # staff_only, owner_visible, parent_visible, admin_only

class ServiceRequestIn(BaseModel):
    horse_id: str
    type: str  # extra_ride, grooming, body_clip, hand_walk, lesson, hauling, show_prep
    details: Optional[str] = None
    requested_date: Optional[str] = None

class IncidentIn(BaseModel):
    horse_id: Optional[str] = None
    type: str  # injury, colic, loose_horse, fall, medication_error, weather, aggression
    title: str
    description: str
    severity: str = "moderate"
    occurred_at: str
    follow_up: Optional[str] = None

class AIRequest(BaseModel):
    kind: str  # wellness_insight, training_summary, owner_update
    context: Dict[str, Any]

def _user_safe(user: dict) -> dict:
    return {k: v for k, v in user.items() if k not in ("password_hash", "_id")}


async def _client_meta(request: Request):
    ua = request.headers.get("user-agent") if request else None
    ip = request.client.host if request and request.client else None
    return ua, ip


class RefreshBody(BaseModel):
    refresh_token: str


# Auth endpoints extracted to routes/auth.py. Router included below near
# the bottom of this file along with task engine and notifications.

# ---------------- Generic listing helpers ----------------
def clean(doc):
    if not doc:
        return doc
    doc.pop("_id", None)
    return doc

async def list_collection(coll, query=None, sort_field=None, limit=500):
    q = query or {}
    cursor = db[coll].find(q, {"_id": 0})
    if sort_field:
        cursor = cursor.sort(sort_field, -1)
    return await cursor.to_list(limit)

# ---------------- Horses ----------------
@api_router.get("/horses")
async def list_horses(user=Depends(get_current_user)):
    return await list_collection("horses")

@api_router.post("/horses")
async def create_horse(body: HorseIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({"id": new_id(), "created_at": iso(now_utc())})
    await db.horses.insert_one(doc)
    return clean(doc)

@api_router.get("/horses/{horse_id}")
async def get_horse(horse_id: str, user=Depends(get_current_user)):
    h = await db.horses.find_one({"id": horse_id}, {"_id": 0})
    if not h:
        raise HTTPException(404, "Horse not found")
    return h

@api_router.patch("/horses/{horse_id}")
async def update_horse(horse_id: str, body: Dict[str, Any], user=Depends(get_current_user)):
    await db.horses.update_one({"id": horse_id}, {"$set": body})
    return await db.horses.find_one({"id": horse_id}, {"_id": 0})

# ---------------- Owners ----------------
@api_router.get("/owners")
async def list_owners(user=Depends(get_current_user)):
    return await list_collection("owners")

@api_router.post("/owners")
async def create_owner(body: OwnerIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({"id": new_id(), "created_at": iso(now_utc())})
    await db.owners.insert_one(doc)
    return clean(doc)

# ---------------- Riders ----------------
@api_router.get("/riders")
async def list_riders(user=Depends(get_current_user)):
    return await list_collection("riders")

@api_router.post("/riders")
async def create_rider(body: RiderIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({"id": new_id(), "created_at": iso(now_utc())})
    await db.riders.insert_one(doc)
    return clean(doc)

# ---------------- Medications ----------------
@api_router.get("/medications")
async def list_meds(horse_id: Optional[str] = None, user=Depends(get_current_user)):
    q = {"horse_id": horse_id} if horse_id else {}
    return await list_collection("medications", q)

@api_router.post("/medications")
async def create_med(body: MedicationIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({"id": new_id(), "created_at": iso(now_utc())})
    await db.medications.insert_one(doc)
    return clean(doc)

@api_router.get("/medication-logs")
async def list_med_logs(user=Depends(get_current_user)):
    return await list_collection("medication_logs", sort_field="scheduled_time")

@api_router.post("/medication-logs")
async def create_med_log(body: MedLogIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({"id": new_id(), "completed_by": user["id"], "completed_at": iso(now_utc())})
    await db.medication_logs.insert_one(doc)
    return clean(doc)

# ---------------- Feed Tasks ----------------
@api_router.get("/feed-tasks")
async def list_feed(date_str: Optional[str] = None, user=Depends(get_current_user)):
    q = {"date": date_str} if date_str else {}
    return await list_collection("feed_tasks", q)

@api_router.post("/feed-tasks/{task_id}/complete")
async def complete_feed(task_id: str, user=Depends(get_current_user)):
    await db.feed_tasks.update_one(
        {"id": task_id},
        {"$set": {"completed": True, "completed_by": user["full_name"], "completed_at": iso(now_utc())}}
    )
    return await db.feed_tasks.find_one({"id": task_id}, {"_id": 0})

# ---------------- Vet records ----------------
@api_router.get("/vet-records")
async def list_vet(horse_id: Optional[str] = None, user=Depends(get_current_user)):
    q = {"horse_id": horse_id} if horse_id else {}
    return await list_collection("vet_records", q, sort_field="date")

@api_router.post("/vet-records")
async def create_vet(body: VetRecordIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({"id": new_id(), "created_at": iso(now_utc())})
    await db.vet_records.insert_one(doc)
    return clean(doc)

# ---------------- Farrier history (engine-projected; Phase-B) ----------------
@api_router.get("/farrier-history")
async def list_farrier(horse_id: Optional[str] = None, user=Depends(get_current_user)):
    q = {"horse_id": horse_id} if horse_id else {}
    items = await db.farrier_history.find(q, {"_id": 0}).sort("date", -1).to_list(500)
    return items

# ---------------- Injuries ----------------
@api_router.get("/injuries")
async def list_injuries(horse_id: Optional[str] = None, user=Depends(get_current_user)):
    q = {"horse_id": horse_id} if horse_id else {}
    return await list_collection("injuries", q)

@api_router.post("/injuries")
async def create_injury(body: InjuryIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({"id": new_id(), "created_at": iso(now_utc())})
    await db.injuries.insert_one(doc)
    return clean(doc)

# ---------------- Wellness ----------------
@api_router.get("/wellness")
async def list_wellness(horse_id: Optional[str] = None, user=Depends(get_current_user)):
    q = {"horse_id": horse_id} if horse_id else {}
    return await list_collection("wellness", q, sort_field="created_at")

@api_router.post("/wellness")
async def create_wellness(body: WellnessIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({"id": new_id(), "created_at": iso(now_utc())})
    await db.wellness.insert_one(doc)
    # Also bump horse wellness_score
    avg = (body.appetite + body.water_intake + body.energy + body.coat_quality) * 5
    await db.horses.update_one({"id": body.horse_id}, {"$set": {"wellness_score": min(100, avg)}})
    return clean(doc)

# ---------------- Lessons ----------------
@api_router.get("/lessons")
async def list_lessons(user=Depends(get_current_user)):
    return await list_collection("lessons", sort_field="start_time")

@api_router.post("/lessons")
async def create_lesson(body: LessonIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({"id": new_id(), "created_at": iso(now_utc())})
    await db.lessons.insert_one(doc)
    return clean(doc)

# ---------------- Training ----------------
@api_router.get("/training")
async def list_training(horse_id: Optional[str] = None, user=Depends(get_current_user)):
    q = {"horse_id": horse_id} if horse_id else {}
    return await list_collection("training", q, sort_field="date")

@api_router.post("/training")
async def create_training(body: TrainingSessionIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({"id": new_id(), "created_at": iso(now_utc())})
    await db.training.insert_one(doc)
    return clean(doc)

# ---------------- Invoices ----------------
@api_router.get("/invoices")
async def list_invoices(user=Depends(get_current_user)):
    return await list_collection("invoices", sort_field="due_date")

@api_router.post("/invoices")
async def create_invoice(body: InvoiceIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({"id": new_id(), "created_at": iso(now_utc())})
    await db.invoices.insert_one(doc)
    return clean(doc)

@api_router.post("/invoices/{invoice_id}/pay")
async def pay_invoice(invoice_id: str, user=Depends(get_current_user)):
    await db.invoices.update_one({"id": invoice_id}, {"$set": {"status": "paid", "paid_at": iso(now_utc())}})
    return await db.invoices.find_one({"id": invoice_id}, {"_id": 0})

# ---------------- Messages ----------------
@api_router.get("/messages")
async def list_messages(user=Depends(get_current_user)):
    return await list_collection("messages", sort_field="created_at")

@api_router.post("/messages")
async def create_message(body: MessageIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({
        "id": new_id(),
        "from_user_id": user["id"],
        "from_name": user["full_name"],
        "created_at": iso(now_utc()),
        "read": False,
    })
    await db.messages.insert_one(doc)
    return clean(doc)

# ---------------- Service Requests ----------------
@api_router.get("/service-requests")
async def list_sr(user=Depends(get_current_user)):
    return await list_collection("service_requests", sort_field="created_at")

@api_router.post("/service-requests")
async def create_sr(body: ServiceRequestIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({
        "id": new_id(),
        "requested_by": user["id"],
        "requester_name": user["full_name"],
        "status": "pending",
        "created_at": iso(now_utc()),
    })
    await db.service_requests.insert_one(doc)
    return clean(doc)

@api_router.post("/service-requests/{sr_id}/approve")
async def approve_sr(sr_id: str, user=Depends(get_current_user)):
    await db.service_requests.update_one({"id": sr_id}, {"$set": {"status": "approved", "approved_at": iso(now_utc())}})
    return await db.service_requests.find_one({"id": sr_id}, {"_id": 0})


class DeclineSRBody(BaseModel):
    reason: Optional[str] = None


@api_router.post("/service-requests/{sr_id}/decline")
async def decline_sr(sr_id: str, body: Optional[DeclineSRBody] = None, user=Depends(get_current_user)):
    reason = (body.reason if body else None) or "Request declined."
    r = await db.service_requests.update_one(
        {"id": sr_id},
        {"$set": {
            "status": "declined",
            "declined_at": iso(now_utc()),
            "declined_by_user_id": user["id"],
            "decline_reason": reason[:500],
        }},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "Service request not found")
    return await db.service_requests.find_one({"id": sr_id}, {"_id": 0})


# ---------------- Owner daily digest (Phase-C) ----------------

@api_router.post("/notifications/digest/preview")
async def digest_preview(user=Depends(get_current_user)):
    """Owner: see what their next daily digest would look like."""
    payload = await build_digest_for_owner(db, user["id"])
    if not payload:
        return {"empty": True, "reason": "no_updates_today"}
    return {
        "empty": False,
        "payload": payload,
        "html": render_digest_html(payload, app_base_url=os.environ.get("PUBLIC_APP_URL", "")),
        "text": render_digest_text(payload),
    }


@api_router.post("/notifications/digest/send-me")
async def digest_send_me(user=Depends(get_current_user)):
    """Owner: trigger their own digest now (useful pre-domain-verification)."""
    if user.get("role") != "horse_owner":
        raise HTTPException(403, "Owner accounts only")
    mailer_handle = {"send": send_email, "render": render_email}
    res = await send_digest_to_owner(db, mailer_handle, user["id"])
    return res


@api_router.post("/admin/digest/run-now")
async def digest_run_now(user=Depends(get_current_user)):
    """Admin: force-run today's digest pass (idempotent — won't double-send)."""
    if user.get("role") not in ("admin", "barn_manager"):
        raise HTTPException(403, "Admin/Manager only")
    mailer_handle = {"send": send_email, "render": render_email}
    return await run_daily_digest_pass(db, mailer_handle)

# ---------------- Incidents ----------------
@api_router.get("/incidents")
async def list_incidents(user=Depends(get_current_user)):
    return await list_collection("incidents", sort_field="occurred_at")

@api_router.post("/incidents")
async def create_incident(body: IncidentIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({"id": new_id(), "reported_by": user["full_name"], "created_at": iso(now_utc())})
    await db.incidents.insert_one(doc)
    return clean(doc)

# ---------------- Dashboard summary ----------------
@api_router.get("/dashboard/summary")
async def dashboard(user=Depends(get_current_user)):
    """Engine-derived dashboard counts. Phase-A migration (Feb 19 2026):
    Feed/meds/lesson counts now come from the unified Task Engine instead of
    legacy `feed_tasks` and `medication_logs` collections.
    """
    today_start = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    today_start_iso = today_start.isoformat()
    today_end_iso = today_end.isoformat()

    total_horses = await db.horses.count_documents({})
    stall_rest = await db.horses.count_documents({"status": {"$in": ["stall_rest", "rehab"]}})
    active_injuries = await db.injuries.count_documents({"status": {"$in": ["active", "monitoring", "improving"]}})

    # Engine-backed counts. Tasks are tenant-scoped + filtered to today.
    feed_q = {"tenant_id": TASK_TENANT_ID, "category": "feed",
              "scheduled_at": {"$gte": today_start_iso, "$lt": today_end_iso}}
    feed_today_total = await db.tasks.count_documents(feed_q)
    feed_pending = await db.tasks.count_documents({**feed_q, "status": {"$nin": ["completed", "skipped", "cancelled"]}})

    med_q = {"tenant_id": TASK_TENANT_ID, "category": "medication",
             "scheduled_at": {"$gte": today_start_iso, "$lt": today_end_iso}}
    meds_due = await db.tasks.count_documents({**med_q, "status": {"$nin": ["completed", "skipped", "cancelled"]}})
    # Missed = a completion with outcome=refused OR a task overdue beyond its window.
    meds_missed = await db.task_completions.count_documents({
        "tenant_id": TASK_TENANT_ID, "voided": {"$ne": True},
        "outcome": {"$in": ["refused", "skipped"]},
        "completed_at": {"$gte": today_start_iso, "$lt": today_end_iso},
    })

    pending_sr = await db.service_requests.count_documents({"status": "pending"})
    open_incidents = await db.incidents.count_documents({"status": {"$ne": "closed"}})
    lessons_today = await db.lessons.count_documents({"start_time": {"$regex": f"^{now_utc().date().isoformat()}"}})

    overdue_list = await db.invoices.find(
        {"status": {"$in": ["open", "overdue"]}}, {"_id": 0, "total": 1},
    ).to_list(1000)
    overdue_invoices = len(overdue_list)
    overdue_amount = sum(i.get("total", 0) for i in overdue_list)

    wellness_list = await db.horses.find({}, {"_id": 0, "wellness_score": 1}).to_list(1000)
    avg_wellness = round(sum(h.get("wellness_score", 0) for h in wellness_list) / max(1, len(wellness_list))) if wellness_list else 0

    return {
        "total_horses": total_horses,
        "feed_pending": feed_pending,
        "feed_today_total": feed_today_total,
        "meds_due": meds_due,
        "meds_missed": meds_missed,
        "stall_rest": stall_rest,
        "active_injuries": active_injuries,
        "overdue_invoices": overdue_invoices,
        "overdue_amount": overdue_amount,
        "pending_service_requests": pending_sr,
        "open_incidents": open_incidents,
        "lessons_today": lessons_today,
        "avg_wellness": avg_wellness,
        "_source": "engine",
    }


@api_router.get("/dashboard/barn-board")
async def barn_board(response: Response, user=Depends(get_current_user)):
    """DEPRECATED Phase-A (Feb 19 2026): kept for backward compatibility while
    callers migrate to /tasks/today. New code should not use this endpoint.

    Now backed by the unified Task Engine instead of legacy collections.
    """
    # RFC 8594 deprecation signaling for HTTP clients.
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Wed, 30 Apr 2026 00:00:00 GMT"
    response.headers["Link"] = '</api/tasks/today>; rel="successor-version"'
    today_start = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    today_str = now_utc().date().isoformat()

    feed = await db.tasks.find({
        "tenant_id": TASK_TENANT_ID, "category": "feed",
        "scheduled_at": {"$gte": today_start.isoformat(), "$lt": today_end.isoformat()},
    }, {"_id": 0}).sort("scheduled_at", 1).to_list(200)
    meds = await db.tasks.find({
        "tenant_id": TASK_TENANT_ID, "category": "medication",
        "scheduled_at": {"$gte": today_start.isoformat(), "$lt": today_end.isoformat()},
    }, {"_id": 0}).sort("scheduled_at", 1).to_list(200)
    lessons = await db.lessons.find({"start_time": {"$regex": f"^{today_str}"}}, {"_id": 0}).to_list(200)
    stall_rest = await db.horses.find({"status": {"$in": ["stall_rest", "rehab"]}}, {"_id": 0}).to_list(100)
    incidents = await db.incidents.find({}, {"_id": 0}).sort("occurred_at", -1).to_list(5)
    return {
        "date": today_str,
        "feed": feed,
        "medications": meds,
        "lessons": lessons,
        "stall_rest": stall_rest,
        "urgent": incidents,
        "weather": {"temp_f": 58, "condition": "Light Rain", "alert": "Wet footing — limit outdoor jumping"},
        "_deprecated": "Use /tasks/today; this endpoint will be removed.",
    }

# ---------------- AI assistant ----------------
@api_router.post("/ai/generate")
async def ai_generate(body: AIRequest, user=Depends(get_current_user)):
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:
        raise HTTPException(500, f"AI library unavailable: {e}")

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(500, "Emergent LLM key not configured")

    prompts = {
        "wellness_insight": "You are an experienced equine wellness specialist. Given the horse's wellness data, write a concise 3-4 sentence professional insight noting trends, risks, and one practical recommendation. Be warm and authoritative.",
        "training_summary": "You are a top-tier riding coach. Given the training session details, write a refined 3-4 sentence summary that captures progress, what was schooled, and the next priority for the horse. Use elegant, professional language.",
        "owner_update": "You are the barn manager at a luxury show stable writing to a horse's owner. Compose a warm 3-5 sentence personalised update covering today's training, wellbeing, and one delightful observation. Keep tone refined and reassuring.",
    }
    system = prompts.get(body.kind, prompts["owner_update"])
    chat = LlmChat(
        api_key=api_key,
        session_id=f"equinesync-{user['id']}-{new_id()[:8]}",
        system_message=system,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    ctx_text = "\n".join(f"{k}: {v}" for k, v in body.context.items())
    msg = UserMessage(text=f"Context:\n{ctx_text}\n\nWrite the response now.")
    try:
        reply = await chat.send_message(msg)
        return {"text": reply}
    except Exception as e:
        logging.exception("AI failed")
        raise HTTPException(500, f"AI generation failed: {e}")

# ---------------- Seed ----------------
@api_router.post("/seed")
async def seed():
    """Idempotent: clears and inserts rich demo data."""
    for c in ["users", "horses", "owners", "riders", "medications", "medication_logs",
              "feed_tasks", "vet_records", "injuries", "wellness", "lessons", "training",
              "invoices", "messages", "service_requests", "incidents"]:
        await db[c].delete_many({})

    # demo users
    demo_users = [
        ("admin@equinesync.com", "demo1234", "Eleanor Whitfield", "admin"),
        ("trainer@equinesync.com", "demo1234", "Marcus Aldridge", "trainer"),
        ("groom@equinesync.com", "demo1234", "Sophia Reyes", "groom"),
        ("owner@equinesync.com", "demo1234", "Charlotte Vance", "horse_owner"),
        ("vet@equinesync.com", "demo1234", "Dr. Henrik Vossler", "veterinarian"),
    ]
    for email, pwd, name, role in demo_users:
        await db.users.insert_one({
            "id": new_id(), "email": email, "full_name": name, "role": role,
            "password_hash": hash_pwd(pwd), "created_at": iso(now_utc()),
        })

    # Owners
    owners = []
    for name, email, phone in [
        ("Charlotte Vance", "charlotte@vanceequestrian.com", "+1 555 0142"),
        ("Alexandre Beaumont", "a.beaumont@beaumonte.eu", "+33 1 22 33 44 55"),
        ("Isabella Hartwell", "isabella@hartwellfarms.com", "+1 555 0388"),
    ]:
        o = {"id": new_id(), "full_name": name, "email": email, "phone": phone,
             "horses": [], "photo_url": None, "created_at": iso(now_utc())}
        await db.owners.insert_one(o); owners.append(o)

    # Riders
    riders = []
    for name, level, goals in [
        ("Amelia Vance", "intermediate", "Move up to 1.10m jumpers by summer"),
        ("Theodore Beaumont", "advanced", "Compete CDI Small Tour 2026"),
        ("Olivia Hartwell", "beginner", "Confident canter on the rail"),
    ]:
        r = {"id": new_id(), "full_name": name, "age": 16, "skill_level": level,
             "goals": goals, "emergency_contact": "+1 555 0900",
             "photo_url": None, "created_at": iso(now_utc())}
        await db.riders.insert_one(r); riders.append(r)

    # Horses
    horse_seed = [
        ("Valentino", "Hanoverian", 11, "Bay", 16.3, "Show Jumping", "active", "Stall 1",
         "https://images.unsplash.com/photo-1553284965-5dc02f396399?w=900&auto=format&fit=crop",
         "Sweet itch", "Premier Equine 2.5M", 92, "Aim for 1.20m by April."),
        ("Saint-Cloud", "Selle Français", 9, "Grey", 17.0, "Show Jumping", "active", "Stall 3",
         "https://images.unsplash.com/photo-1534773728080-33d31da27ae5?w=900&auto=format&fit=crop",
         "", "Hartwell Insurance 1.8M", 88, "Maintain fitness through indoor season."),
        ("Belle Étoile", "Dutch Warmblood", 14, "Chestnut", 16.2, "Dressage", "active", "Stall 5",
         "https://images.unsplash.com/photo-1605713704694-f59ae1ca8efb?w=900&auto=format&fit=crop",
         "Bee stings", "Beaumont Coverage 1.2M", 90, "Confirm flying changes in 4-tempi."),
        ("Whisper", "Thoroughbred", 16, "Black", 16.0, "Hunters", "stall_rest", "Stall 7",
         "https://images.unsplash.com/photo-1639570830431-6c2d0100d37b?w=900&auto=format&fit=crop",
         "Penicillin", "Vance Premier 800K", 64, "Rehab from soft tissue."),
        ("Mercury", "KWPN", 7, "Dark Bay", 16.1, "Show Jumping", "active", "Stall 9",
         "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?w=900&auto=format&fit=crop",
         "", "Working Insurance", 86, "Build canter strength."),
        ("Iolani", "Lusitano", 12, "Grey", 15.3, "Dressage", "rehab", "Stall 11",
         "https://images.unsplash.com/photo-1598974357801-cbca100e65d3?w=900&auto=format&fit=crop",
         "", "Beaumont 1.2M", 71, "Return to controlled work."),
    ]
    horses = []
    flags_pool = ["Buddy sour", "Hard to catch", "Solo turnout", "Dominant", "Kicks"]
    for i, h in enumerate(horse_seed):
        doc = {
            "id": new_id(),
            "name": h[0], "barn_name": h[0].split()[0], "breed": h[1], "age": h[2],
            "color": h[3], "height_hands": h[4], "discipline": h[5], "status": h[6],
            "stall": h[7], "photo_url": h[8],
            "allergies": [h[9]] if h[9] else [],
            "insurance": h[10], "wellness_score": h[11], "training_goals": h[12],
            "owner_id": owners[i % 3]["id"],
            "rider_id": riders[i % 3]["id"],
            "feed_plan": "Morning: 2lb grain + 4lb hay. Midday: 4lb hay. Evening: 2lb grain + 6lb hay + supplements.",
            "turnout_group": ["Geldings A", "Geldings B", "Mares Pasture"][i % 3],
            "behavior_flags": [flags_pool[i % len(flags_pool)]] if i % 2 == 0 else [],
            "emergency_notes": "Owner authorises emergency vet care up to $5,000.",
            "created_at": iso(now_utc()),
        }
        await db.horses.insert_one(doc); horses.append(doc)

    # Feed tasks (today, all 3 meals each horse)
    today = now_utc().date().isoformat()
    meals = [("morning", "2lb Triple Crown Senior + 4lb timothy hay"),
             ("midday", "4lb timothy hay + free-choice water"),
             ("evening", "2lb grain + 6lb hay + joint supplement")]
    for h in horses:
        for meal, ration in meals:
            await db.feed_tasks.insert_one({
                "id": new_id(),
                "horse_id": h["id"], "horse_name": h["name"], "meal": meal,
                "ration": ration, "instructions": "Soak feed for Whisper.",
                "date": today, "completed": meal == "morning",
                "completed_by": "Sophia Reyes" if meal == "morning" else None,
                "completed_at": iso(now_utc()) if meal == "morning" else None,
            })

    # Medications
    for h in horses[:4]:
        med = {
            "id": new_id(),
            "horse_id": h["id"], "horse_name": h["name"],
            "name": "Previcox", "dosage": "57mg", "route": "oral",
            "frequency": "Once daily", "prescribing_vet": "Dr. Henrik Vossler",
            "times": ["08:00"], "notes": "Give with feed.",
            "start_date": today, "created_at": iso(now_utc()),
        }
        await db.medications.insert_one(med)
        # log entries
        await db.medication_logs.insert_one({
            "id": new_id(),
            "medication_id": med["id"], "horse_id": h["id"], "horse_name": h["name"],
            "med_name": med["name"], "dosage": med["dosage"],
            "scheduled_time": f"{today}T08:00:00",
            "status": "given" if h["wellness_score"] > 80 else "missed",
            "notes": None,
        })

    # Vet records
    for h in horses:
        await db.vet_records.insert_one({
            "id": new_id(), "horse_id": h["id"], "horse_name": h["name"],
            "type": "vaccine", "title": "Spring Vaccine — EWT, Flu/Rhino",
            "date": (now_utc() - timedelta(days=30)).date().isoformat(),
            "vet_name": "Dr. Henrik Vossler", "cost": 245.0,
            "notes": "All shots up to date.", "created_at": iso(now_utc()),
        })
        await db.vet_records.insert_one({
            "id": new_id(), "horse_id": h["id"], "horse_name": h["name"],
            "type": "coggins", "title": "Coggins (negative)",
            "date": (now_utc() - timedelta(days=60)).date().isoformat(),
            "vet_name": "Dr. Henrik Vossler", "cost": 95.0,
            "notes": "Valid 12 months.", "created_at": iso(now_utc()),
        })

    # Injuries
    await db.injuries.insert_one({
        "id": new_id(), "horse_id": horses[3]["id"], "horse_name": horses[3]["name"],
        "title": "Right front suspensory strain", "description": "Mild proximal suspensory desmitis.",
        "status": "improving", "severity": "moderate",
        "start_date": (now_utc() - timedelta(days=21)).date().isoformat(),
        "rehab_plan": "6 weeks: 4 wks hand-walking, then tack walk + jog.",
        "created_at": iso(now_utc()),
    })
    await db.injuries.insert_one({
        "id": new_id(), "horse_id": horses[5]["id"], "horse_name": horses[5]["name"],
        "title": "Hind fetlock swelling", "description": "Soft tissue, monitoring.",
        "status": "monitoring", "severity": "mild",
        "start_date": (now_utc() - timedelta(days=10)).date().isoformat(),
        "rehab_plan": "Cold therapy 2x daily, light hand walking.",
        "created_at": iso(now_utc()),
    })

    # Wellness entries
    for h in horses:
        await db.wellness.insert_one({
            "id": new_id(), "horse_id": h["id"], "horse_name": h["name"],
            "appetite": 5, "water_intake": 5, "energy": 4 if h["wellness_score"] < 80 else 5,
            "body_condition": 5.5, "coat_quality": 5,
            "status": "concern" if h["wellness_score"] < 75 else ("watch" if h["wellness_score"] < 85 else "normal"),
            "notes": "Bright and forward today.",
            "created_at": iso(now_utc() - timedelta(hours=4)),
        })

    # Lessons (today + tomorrow)
    for idx, r in enumerate(riders):
        start = now_utc().replace(hour=10 + idx * 2, minute=0, second=0, microsecond=0)
        await db.lessons.insert_one({
            "id": new_id(),
            "rider_id": r["id"], "rider_name": r["full_name"],
            "horse_id": horses[idx]["id"], "horse_name": horses[idx]["name"],
            "trainer_id": None, "trainer_name": "Marcus Aldridge",
            "start_time": iso(start), "duration_min": 60,
            "focus": ["Gymnastic grid", "Lateral work", "Position & balance"][idx],
            "completed": False, "created_at": iso(now_utc()),
        })

    # Training sessions
    for h in horses[:4]:
        await db.training.insert_one({
            "id": new_id(), "horse_id": h["id"], "horse_name": h["name"],
            "trainer_id": None, "trainer_name": "Marcus Aldridge",
            "date": (now_utc() - timedelta(days=1)).date().isoformat(),
            "discipline": h["discipline"],
            "exercises": "Trot poles, canter transitions, gymnastic line 2-1-2.",
            "notes": "Forward, balanced, sharp off the leg.",
            "rating": 8, "homework": "Hack out tomorrow.",
            "created_at": iso(now_utc()),
        })

    # Invoices
    invoice_items = [
        {"label": "Full Board (Monthly)", "amount": 2850},
        {"label": "Training (4x/week)", "amount": 1200},
        {"label": "Supplements", "amount": 145},
    ]
    for idx, o in enumerate(owners):
        await db.invoices.insert_one({
            "id": new_id(), "owner_id": o["id"], "owner_name": o["full_name"],
            "horse_id": horses[idx]["id"], "horse_name": horses[idx]["name"],
            "items": invoice_items,
            "total": sum(i["amount"] for i in invoice_items),
            "due_date": (now_utc() + timedelta(days=10 - idx * 4)).date().isoformat(),
            "status": ["open", "paid", "overdue"][idx],
            "created_at": iso(now_utc()),
        })

    # Messages
    await db.messages.insert_one({
        "id": new_id(), "from_user_id": "system", "from_name": "Eleanor Whitfield",
        "to_role": "trainer", "subject": "Spring Show Schedule",
        "body": "Please confirm entries for the Wellington circuit by Friday.",
        "visibility": "staff_only", "read": False,
        "created_at": iso(now_utc() - timedelta(hours=3)),
    })
    await db.messages.insert_one({
        "id": new_id(), "from_user_id": "system", "from_name": "Charlotte Vance",
        "to_role": "admin", "subject": "Extra grooming for Saturday",
        "body": "Could we add a body clip before Saturday's show?",
        "visibility": "admin_only", "read": False,
        "created_at": iso(now_utc() - timedelta(hours=6)),
    })

    # Service requests
    await db.service_requests.insert_one({
        "id": new_id(), "horse_id": horses[0]["id"], "horse_name": horses[0]["name"],
        "type": "body_clip", "details": "Full body clip before Saturday show.",
        "requested_date": (now_utc() + timedelta(days=2)).date().isoformat(),
        "requested_by": "system", "requester_name": "Charlotte Vance",
        "status": "pending", "created_at": iso(now_utc()),
    })
    await db.service_requests.insert_one({
        "id": new_id(), "horse_id": horses[2]["id"], "horse_name": horses[2]["name"],
        "type": "extra_ride", "details": "Schoolmaster ride on Thursday morning.",
        "requested_date": (now_utc() + timedelta(days=3)).date().isoformat(),
        "requested_by": "system", "requester_name": "Alexandre Beaumont",
        "status": "pending", "created_at": iso(now_utc()),
    })

    # Incidents
    await db.incidents.insert_one({
        "id": new_id(), "horse_id": horses[3]["id"], "horse_name": horses[3]["name"],
        "type": "injury", "title": "Cast in stall overnight",
        "description": "Whisper found cast at 5am; freed without injury.",
        "severity": "moderate", "occurred_at": iso(now_utc() - timedelta(hours=8)),
        "status": "open", "follow_up": "Add stall padding & monitor cameras.",
        "reported_by": "Sophia Reyes", "created_at": iso(now_utc()),
    })

    return {"ok": True, "seeded": True}

# ---------------- Onboarding ----------------
ONBOARDING_STEPS = [
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
    facility_type: Optional[str] = None  # private, boarding, lesson, training, show, rescue
    disciplines: Optional[List[str]] = []
    address: Optional[str] = None
    timezone: Optional[str] = "America/New_York"
    contact_email: Optional[str] = None  # plain str to allow empty
    contact_phone: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None

class LocationIn(BaseModel):
    type: str  # stall, paddock, pasture, arena, tack_room, feed_room, wash_rack
    name: str
    capacity: Optional[int] = 1
    notes: Optional[str] = None

class FeedTemplateIn(BaseModel):
    meal: str  # morning, midday, evening
    hay_type: Optional[str] = None
    hay_lbs: Optional[float] = 0
    grain_type: Optional[str] = None
    grain_lbs: Optional[float] = 0
    supplements: Optional[str] = None
    med_timing: Optional[str] = None
    instructions: Optional[str] = None

class InventoryIn(BaseModel):
    category: str  # grain, hay, bedding, supplements, medical, blankets, tack, other
    name: str
    unit: str = "lbs"
    quantity: float = 0
    reorder_at: Optional[float] = 0
    vendor: Optional[str] = None
    cost_per_unit: Optional[float] = 0
    notes: Optional[str] = None

class RecurringScheduleIn(BaseModel):
    type: str  # turnout, feed, medication, blanketing, lesson_block, training_ride
    name: str
    days_of_week: Optional[List[str]] = []  # mon, tue...
    time: Optional[str] = None  # "08:00"
    location_id: Optional[str] = None
    notes: Optional[str] = None

class StaffInviteIn(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: str
    permissions: Optional[List[str]] = []

class ProgressPatch(BaseModel):
    step_id: Optional[str] = None
    status: Optional[str] = None  # complete, in_progress, skipped, pending
    current_step: Optional[str] = None
    data: Optional[Dict[str, Any]] = None  # autosave bag

class CsvPreviewBody(BaseModel):
    kind: str  # horses, owners
    csv_text: str

class CsvCommitBody(BaseModel):
    kind: str
    rows: List[Dict[str, Any]]

@api_router.get("/onboarding/steps")
async def get_steps():
    return {"steps": ONBOARDING_STEPS}

@api_router.get("/onboarding/progress")
async def get_progress(user=Depends(get_current_user)):
    doc = await db.onboarding_progress.find_one({"user_id": user["id"]}, {"_id": 0})
    if not doc:
        doc = {
            "user_id": user["id"],
            "steps": {s["id"]: "pending" for s in ONBOARDING_STEPS},
            "current_step": ONBOARDING_STEPS[0]["id"],
            "data": {},
            "completed": False,
            "created_at": iso(now_utc()),
            "updated_at": iso(now_utc()),
        }
        await db.onboarding_progress.insert_one(doc)
        doc.pop("_id", None)
    # Compute percent complete
    completed = sum(1 for v in doc.get("steps", {}).values() if v == "complete")
    doc["percent"] = round(100 * completed / len(ONBOARDING_STEPS))
    return doc

def _deep_merge(base: dict, patch: dict) -> dict:
    """Recursively merge patch into base. dict values are merged, others replaced."""
    out = dict(base or {})
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

@api_router.patch("/onboarding/progress")
async def patch_progress(body: ProgressPatch, user=Depends(get_current_user)):
    doc = await db.onboarding_progress.find_one({"user_id": user["id"]})
    if not doc:
        await get_progress(user)
        doc = await db.onboarding_progress.find_one({"user_id": user["id"]})
    update = {"updated_at": iso(now_utc())}
    if body.step_id and body.status:
        update[f"steps.{body.step_id}"] = body.status
    if body.current_step:
        update["current_step"] = body.current_step
    if body.data:
        # deep merge data bag so nested objects (e.g. data['barn']['contact']) aren't replaced wholesale
        existing = doc.get("data", {}) or {}
        update["data"] = _deep_merge(existing, body.data)
    await db.onboarding_progress.update_one({"user_id": user["id"]}, {"$set": update})
    fresh = await db.onboarding_progress.find_one({"user_id": user["id"]}, {"_id": 0})
    completed_steps = sum(1 for v in fresh.get("steps", {}).values() if v == "complete")
    fresh["percent"] = round(100 * completed_steps / len(ONBOARDING_STEPS))
    return fresh

@api_router.post("/onboarding/complete")
async def complete_onboarding(user=Depends(get_current_user)):
    await db.onboarding_progress.update_one(
        {"user_id": user["id"]},
        {"$set": {"completed": True, "completed_at": iso(now_utc())}}
    )
    return {"ok": True}

@api_router.post("/onboarding/reset")
async def reset_onboarding(user=Depends(get_current_user)):
    """Re-open the wizard for the current user (resets steps to pending)."""
    await db.onboarding_progress.update_one(
        {"user_id": user["id"]},
        {"$set": {
            "completed": False,
            "completed_at": None,
            "steps": {s["id"]: "pending" for s in ONBOARDING_STEPS},
            "current_step": ONBOARDING_STEPS[0]["id"],
            "updated_at": iso(now_utc()),
        }},
        upsert=True,
    )
    return {"ok": True}

# ---------- Barn settings ----------
@api_router.get("/barn")
async def get_barn(user=Depends(get_current_user)):
    doc = await db.barn.find_one({"id": "primary"}, {"_id": 0})
    if not doc:
        doc = {"id": "primary", "name": "", "facility_type": "boarding",
               "disciplines": [], "address": "", "timezone": "America/New_York",
               "contact_email": "", "contact_phone": "", "logo_url": "", "banner_url": ""}
    return doc

@api_router.put("/barn")
async def update_barn(body: BarnSettings, user=Depends(get_current_user)):
    require_setup_role(user)
    doc = body.model_dump()
    doc["id"] = "primary"
    doc["updated_at"] = iso(now_utc())
    await db.barn.update_one({"id": "primary"}, {"$set": doc}, upsert=True)
    saved = await db.barn.find_one({"id": "primary"}, {"_id": 0})
    return saved

# ---------- Locations ----------
@api_router.get("/locations")
async def list_locations(user=Depends(get_current_user)):
    return await list_collection("locations")

@api_router.post("/locations")
async def create_location(body: LocationIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({"id": new_id(), "created_at": iso(now_utc())})
    await db.locations.insert_one(doc)
    return clean(doc)

@api_router.delete("/locations/{loc_id}")
async def delete_location(loc_id: str, user=Depends(get_current_user)):
    await db.locations.delete_one({"id": loc_id})
    return {"ok": True}

# ---------- Feed templates ----------
@api_router.get("/feed-templates")
async def list_feed_templates(user=Depends(get_current_user)):
    return await list_collection("feed_templates")

@api_router.post("/feed-templates")
async def create_feed_template(body: FeedTemplateIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({"id": new_id(), "created_at": iso(now_utc())})
    await db.feed_templates.insert_one(doc)
    return clean(doc)

@api_router.delete("/feed-templates/{tid}")
async def delete_feed_template(tid: str, user=Depends(get_current_user)):
    await db.feed_templates.delete_one({"id": tid})
    return {"ok": True}

# ---------- Inventory ----------
@api_router.get("/inventory")
async def list_inventory(user=Depends(get_current_user)):
    items = await list_collection("inventory")
    for it in items:
        it["low_stock"] = (it.get("reorder_at") or 0) > 0 and (it.get("quantity") or 0) <= (it.get("reorder_at") or 0)
    return items

@api_router.post("/inventory")
async def create_inventory(body: InventoryIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({"id": new_id(), "created_at": iso(now_utc())})
    await db.inventory.insert_one(doc)
    return clean(doc)

@api_router.delete("/inventory/{iid}")
async def delete_inventory(iid: str, user=Depends(get_current_user)):
    await db.inventory.delete_one({"id": iid})
    return {"ok": True}

# ---------- Recurring Schedules ----------
@api_router.get("/recurring-schedules")
async def list_rs(user=Depends(get_current_user)):
    return await list_collection("recurring_schedules")

@api_router.post("/recurring-schedules")
async def create_rs(body: RecurringScheduleIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({"id": new_id(), "created_at": iso(now_utc())})
    await db.recurring_schedules.insert_one(doc)
    return clean(doc)

@api_router.delete("/recurring-schedules/{sid}")
async def delete_rs(sid: str, user=Depends(get_current_user)):
    await db.recurring_schedules.delete_one({"id": sid})
    return {"ok": True}

# ---------- Staff Invites ----------
@api_router.get("/staff-invites")
async def list_invites(user=Depends(get_current_user)):
    return await list_collection("staff_invites")

@api_router.post("/staff-invites")
async def create_invite(body: StaffInviteIn, user=Depends(get_current_user)):
    require_setup_role(user)
    if body.role not in ROLES:
        raise HTTPException(400, "Invalid role")
    # de-dupe by email (already invited or already a user)
    existing = await db.staff_invites.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(409, "Already invited")
    if await db.users.find_one({"email": body.email.lower()}):
        raise HTTPException(409, "User already exists")
    doc = body.model_dump()
    doc["email"] = doc["email"].lower()
    doc.update({"id": new_id(), "status": "pending",
                "invited_by": user["full_name"], "created_at": iso(now_utc())})
    await db.staff_invites.insert_one(doc)
    return clean(doc)

@api_router.delete("/staff-invites/{sid}")
async def delete_invite(sid: str, user=Depends(get_current_user)):
    await db.staff_invites.delete_one({"id": sid})
    return {"ok": True}

# ---------- CSV import ----------
def _parse_csv(text: str) -> List[Dict[str, str]]:
    import csv, io
    reader = csv.DictReader(io.StringIO(text.strip()))
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in reader]

@api_router.post("/onboarding/csv-preview")
async def csv_preview(body: CsvPreviewBody, user=Depends(get_current_user)):
    try:
        rows = _parse_csv(body.csv_text)
    except Exception as e:
        raise HTTPException(400, f"Invalid CSV: {e}")
    if not rows:
        return {"rows": [], "duplicates": [], "count": 0}

    duplicates = []
    if body.kind == "horses":
        existing_names = {h["name"].lower() for h in await db.horses.find({}, {"_id": 0, "name": 1}).to_list(1000)}
        for r in rows:
            if (r.get("name") or "").lower() in existing_names:
                duplicates.append(r.get("name"))
    elif body.kind == "owners":
        existing = {o.get("email", "").lower() for o in await db.owners.find({}, {"_id": 0, "email": 1}).to_list(1000)}
        for r in rows:
            if (r.get("email") or "").lower() in existing:
                duplicates.append(r.get("email"))
    return {"rows": rows, "duplicates": duplicates, "count": len(rows)}

@api_router.post("/onboarding/csv-commit")
async def csv_commit(body: CsvCommitBody, user=Depends(get_current_user)):
    created = 0
    skipped = 0
    if body.kind == "horses":
        existing_names = {h["name"].lower() for h in await db.horses.find({}, {"_id": 0, "name": 1}).to_list(2000)}
        owners_map = {o.get("full_name", "").lower(): o["id"] for o in await db.owners.find({}, {"_id": 0}).to_list(2000)}
        for r in body.rows:
            name = (r.get("name") or "").strip()
            if not name:
                continue
            if name.lower() in existing_names:
                skipped += 1
                continue
            existing_names.add(name.lower())
            def _maybe_int(v):
                try: return int(float(v)) if v not in (None, "") else None
                except Exception: return None
            def _maybe_float(v):
                try: return float(v) if v not in (None, "") else None
                except Exception: return None
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
                "owner_id": owners_map.get((r.get("owner") or "").lower()) or owners_map.get((r.get("owner_name") or "").lower()),
                "status": r.get("status") or "active",
                "wellness_score": _maybe_int(r.get("wellness_score")) or 85,
                "allergies": [a.strip() for a in (r.get("allergies") or "").split(";") if a.strip()],
                "feed_plan": r.get("feed_plan"),
                "turnout_group": r.get("turnout_group"),
                "behavior_flags": [b.strip() for b in (r.get("behavior_flags") or "").split(";") if b.strip()],
                "photo_url": r.get("photo_url"),
                "created_at": iso(now_utc()),
            }
            await db.horses.insert_one(doc); created += 1
    elif body.kind == "owners":
        existing_emails = {o.get("email", "").lower() for o in await db.owners.find({}, {"_id": 0, "email": 1}).to_list(2000) if o.get("email")}
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
                "created_at": iso(now_utc()),
            }
            await db.owners.insert_one(doc); created += 1
    else:
        raise HTTPException(400, "Unsupported kind")
    return {"created": created, "skipped": skipped}

@api_router.get("/onboarding/csv-template")
async def csv_template(kind: str):
    templates = {
        "horses": "name,breed,age,color,height_hands,discipline,stall,owner,status,wellness_score,allergies,feed_plan,turnout_group,behavior_flags,photo_url\nValentino,Hanoverian,11,Bay,16.3,Show Jumping,Stall 1,Charlotte Vance,active,92,Sweet itch,2lb grain + 6lb hay,Geldings A,Solo turnout,https://example.com/photo.jpg",
        "owners": "full_name,email,phone,emergency_contact,billing_preferences,waiver_signed\nCharlotte Vance,charlotte@example.com,+1 555 0142,Edward Vance +1 555 0143,monthly_card,yes",
    }
    text = templates.get(kind)
    if not text:
        raise HTTPException(400, "Unknown template")
    return {"text": text, "filename": f"equinesync_{kind}_template.csv"}

# ---------------- Magic-link Invites ----------------
ROLE_LABELS = {
    "admin": "Stable Owner / Admin", "barn_manager": "Barn Manager", "trainer": "Trainer",
    "groom": "Groom", "working_student": "Working Student", "horse_owner": "Horse Owner",
    "rider": "Rider", "parent": "Parent / Guardian", "veterinarian": "Veterinarian", "farrier": "Farrier",
}

class InviteCreate(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: str
    barn_id: Optional[str] = "primary"
    message: Optional[str] = None

class InviteAccept(BaseModel):
    token: str
    password: str
    full_name: Optional[str] = None

def _hash_token(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()

def _new_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, _hash_token(raw)

async def _track(name: str, props: Dict[str, Any], user_id: Optional[str] = None):
    """Internal: record an analytics event server-side."""
    try:
        await db.events.insert_one({
            "id": new_id(), "name": name, "props": props or {},
            "user_id": user_id, "at": iso(now_utc()),
        })
    except Exception:
        logger.exception("Failed to record event %s", name)

@api_router.get("/invites")
async def list_invites_full(user=Depends(get_current_user)):
    require_setup_role(user)
    items = await db.invites.find({}, {"_id": 0, "token_hash": 0}).sort("created_at", -1).to_list(500)
    return items

def _base_url(request: Optional[Request] = None) -> str:
    env_url = (os.environ.get("APP_BASE_URL") or "").strip().rstrip("/")
    if env_url:
        return env_url
    if request is not None:
        # Honor x-forwarded-* set by ingress so the link points to the user-facing origin
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme
        host = request.headers.get("x-forwarded-host") or request.headers.get("origin", "").replace("https://", "").replace("http://", "") or request.url.netloc
        host = host.split(",")[0].strip().rstrip("/")
        if host:
            return f"{proto}://{host}"
    return "https://herd-hub-19.emergent.host"

@api_router.post("/invites")
async def create_invite_with_link(body: InviteCreate, request: Request, user=Depends(get_current_user)):
    require_setup_role(user)
    if body.role not in ROLES:
        raise HTTPException(400, "Invalid role")
    email_l = body.email.lower()
    # de-dupe by email — active (pending, non-expired) invites or existing users
    if await db.users.find_one({"email": email_l}):
        raise HTTPException(409, "A user with this email already exists")
    existing = await db.invites.find_one({"email": email_l, "status": "pending"})
    if existing:
        raise HTTPException(409, "An invite for this email is already pending — resend or revoke it first")

    raw_token, token_hash = _new_token()
    ttl_days = int(os.environ.get("INVITE_TTL_DAYS", "7"))
    expires_at = now_utc() + timedelta(days=ttl_days)
    barn = await db.barn.find_one({"id": body.barn_id or "primary"}, {"_id": 0, "name": 1}) or {}

    invite = {
        "id": new_id(),
        "email": email_l,
        "full_name": body.full_name,
        "role": body.role,
        "barn_id": body.barn_id or "primary",
        "token_hash": token_hash,
        "status": "pending",
        "message": body.message,
        "invited_by_id": user["id"],
        "invited_by_name": user["full_name"],
        "expires_at": iso(expires_at),
        "created_at": iso(now_utc()),
        "sends": [],
    }
    await db.invites.insert_one(invite)

    accept_url = f"{_base_url(request)}/accept-invite?token={raw_token}"

    mail = await send_email(
        to=email_l,
        subject=f"You're invited to {barn.get('name') or 'EquineSync'}",
        template="onboarding_invite",
        variables={
            "barn_name": barn.get("name") or "EquineSync",
            "invitee_name": (body.full_name or email_l.split('@')[0]).strip() or "rider",
            "inviter_name": user["full_name"],
            "role_label": ROLE_LABELS.get(body.role, body.role.replace('_', ' ')),
            "accept_url": accept_url,
            "ttl_days": ttl_days,
        },
    )
    await db.invites.update_one({"id": invite["id"]},
        {"$push": {"sends": {"at": iso(now_utc()), "status": mail.get("status"), "id": mail.get("id")}}})
    await _track("invite.sent", {"invite_id": invite["id"], "role": body.role, "dev_mode": mail.get("dev", False)}, user["id"])

    out = await db.invites.find_one({"id": invite["id"]}, {"_id": 0, "token_hash": 0})
    # Surface the magic link to the inviter in dev mode so they can share it manually if email is disabled.
    if mail.get("dev"):
        out["dev_accept_url"] = accept_url
    return out

@api_router.post("/invites/{invite_id}/resend")
async def resend_invite(invite_id: str, request: Request, user=Depends(get_current_user)):
    require_setup_role(user)
    inv = await db.invites.find_one({"id": invite_id})
    if not inv: raise HTTPException(404, "Invite not found")
    if inv.get("status") != "pending":
        raise HTTPException(400, f"Invite is {inv.get('status')}")
    raw_token, token_hash = _new_token()
    ttl_days = int(os.environ.get("INVITE_TTL_DAYS", "7"))
    expires_at = now_utc() + timedelta(days=ttl_days)
    await db.invites.update_one({"id": invite_id},
        {"$set": {"token_hash": token_hash, "expires_at": iso(expires_at), "updated_at": iso(now_utc())}})

    barn = await db.barn.find_one({"id": inv.get("barn_id", "primary")}, {"_id": 0, "name": 1}) or {}
    accept_url = f"{_base_url(request)}/accept-invite?token={raw_token}"
    mail = await send_email(
        to=inv["email"],
        subject=f"Reminder: your invitation to {barn.get('name') or 'EquineSync'}",
        template="onboarding_invite",
        variables={
            "barn_name": barn.get("name") or "EquineSync",
            "invitee_name": (inv.get("full_name") or inv["email"].split('@')[0]),
            "inviter_name": user["full_name"],
            "role_label": ROLE_LABELS.get(inv["role"], inv["role"].replace('_', ' ')),
            "accept_url": accept_url,
            "ttl_days": ttl_days,
        },
    )
    await db.invites.update_one({"id": invite_id},
        {"$push": {"sends": {"at": iso(now_utc()), "status": mail.get("status"), "id": mail.get("id"), "resend": True}}})
    await _track("invite.resent", {"invite_id": invite_id}, user["id"])
    out = await db.invites.find_one({"id": invite_id}, {"_id": 0, "token_hash": 0})
    if mail.get("dev"):
        out["dev_accept_url"] = accept_url
    return out

@api_router.post("/invites/{invite_id}/revoke")
async def revoke_invite(invite_id: str, user=Depends(get_current_user)):
    require_setup_role(user)
    res = await db.invites.update_one(
        {"id": invite_id, "status": "pending"},
        {"$set": {"status": "revoked", "revoked_at": iso(now_utc()), "revoked_by": user["full_name"]}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "No pending invite found")
    await _track("invite.revoked", {"invite_id": invite_id}, user["id"])
    return {"ok": True}

@api_router.get("/invites/verify")
async def verify_invite(token: str):
    inv = await db.invites.find_one({"token_hash": _hash_token(token)}, {"_id": 0, "token_hash": 0})
    if not inv:
        raise HTTPException(404, "Invalid invitation link")
    if inv.get("status") != "pending":
        raise HTTPException(410, f"This invitation is {inv.get('status')}")
    try:
        exp = datetime.fromisoformat(inv["expires_at"])
        if exp.tzinfo is None: exp = exp.replace(tzinfo=timezone.utc)
        if exp < now_utc():
            await db.invites.update_one({"id": inv["id"]}, {"$set": {"status": "expired"}})
            raise HTTPException(410, "This invitation has expired")
    except KeyError:
        pass
    barn = await db.barn.find_one({"id": inv.get("barn_id", "primary")}, {"_id": 0, "name": 1, "facility_type": 1}) or {}
    inv["barn"] = barn
    return inv

@api_router.post("/invites/accept")
async def accept_invite(body: InviteAccept, request: Request):
    inv = await db.invites.find_one({"token_hash": _hash_token(body.token)})
    if not inv:
        raise HTTPException(404, "Invalid invitation")
    if inv.get("status") != "pending":
        raise HTTPException(410, f"Invitation is {inv.get('status')}")
    exp = datetime.fromisoformat(inv["expires_at"])
    if exp.tzinfo is None: exp = exp.replace(tzinfo=timezone.utc)
    if exp < now_utc():
        await db.invites.update_one({"id": inv["id"]}, {"$set": {"status": "expired"}})
        raise HTTPException(410, "Invitation expired")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if await db.users.find_one({"email": inv["email"]}):
        raise HTTPException(409, "A user already exists for this email — please sign in")

    full_name = (body.full_name or inv.get("full_name") or inv["email"].split('@')[0]).strip()
    user = {
        "id": new_id(),
        "email": inv["email"],
        "full_name": full_name,
        "role": inv["role"],
        "password_hash": hash_pwd(body.password),
        "created_at": iso(now_utc()),
        "via_invite_id": inv["id"],
    }
    await db.users.insert_one(user)
    await db.invites.update_one({"id": inv["id"]},
        {"$set": {"status": "accepted", "accepted_at": iso(now_utc()), "accepted_user_id": user["id"]}})

    # Pre-create an onboarding progress doc so wizard auto-launches and resumes cleanly.
    has_setup_role = inv["role"] in ("admin", "barn_manager")
    progress = {
        "user_id": user["id"],
        "steps": {s["id"]: "pending" for s in ONBOARDING_STEPS},
        "current_step": ONBOARDING_STEPS[0]["id"],
        "data": {},
        "completed": not has_setup_role,  # non-setup roles don't see the wizard
        "auto_launch": has_setup_role,
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
    }
    await db.onboarding_progress.insert_one(progress)

    token = create_token(user["id"], user["role"])
    ua, ip = await _client_meta(request)
    refresh = await issue_refresh_token(db, user["id"], user_agent=ua, ip=ip)
    await _track("invite.accepted", {"invite_id": inv["id"], "role": inv["role"]}, user["id"])
    return {
        "token": token,
        "refresh_token": refresh,
        "expires_in_seconds": JWT_EXP_HOURS * 3600,
        "user": _user_safe(user),
        "auto_launch_onboarding": has_setup_role,
    }

# ---------------- Analytics ----------------
class EventIn(BaseModel):
    name: str
    props: Optional[Dict[str, Any]] = {}

@api_router.post("/events")
async def track_event(body: EventIn, user=Depends(get_current_user)):
    await db.events.insert_one({
        "id": new_id(), "name": body.name, "props": body.props or {},
        "user_id": user["id"], "user_role": user.get("role"), "at": iso(now_utc()),
    })
    return {"ok": True}

@api_router.get("/events/onboarding-funnel")
async def onboarding_funnel(user=Depends(get_current_user)):
    require_setup_role(user)
    pipeline = [
        {"$match": {"name": {"$regex": "^onboarding\\."}}},
        {"$group": {"_id": "$name", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    rows = await db.events.aggregate(pipeline).to_list(100)
    return [{"event": r["_id"], "count": r["count"]} for r in rows]

# ---------------- Setup Health Reports ----------------
async def _setup_health_payload() -> Dict[str, Any]:
    """Aggregate everything the Setup Health report needs in a single payload."""
    total_progress = await db.onboarding_progress.count_documents({})
    completed_progress = await db.onboarding_progress.count_documents({"completed": True})

    # Funnel by step
    progresses = await db.onboarding_progress.find({}, {"_id": 0, "steps": 1, "data": 1, "updated_at": 1, "created_at": 1, "completed": 1, "completed_at": 1, "user_id": 1}).to_list(2000)
    funnel = {s["id"]: {"label": s["label"], "complete": 0, "in_progress": 0, "skipped": 0, "pending": 0} for s in ONBOARDING_STEPS}
    durations: List[float] = []
    for p in progresses:
        for sid, status in (p.get("steps") or {}).items():
            if sid in funnel and status in funnel[sid]:
                funnel[sid][status] += 1
        if p.get("completed") and p.get("created_at") and p.get("completed_at"):
            try:
                a = datetime.fromisoformat(p["created_at"]); b = datetime.fromisoformat(p["completed_at"])
                if a.tzinfo is None: a = a.replace(tzinfo=timezone.utc)
                if b.tzinfo is None: b = b.replace(tzinfo=timezone.utc)
                durations.append((b - a).total_seconds() / 3600.0)  # hours
            except Exception:
                pass

    def _median(xs):
        if not xs: return None
        xs = sorted(xs); n = len(xs)
        return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2

    median_hours = _median(durations)

    # Invite metrics
    total_invites = await db.invites.count_documents({})
    accepted = await db.invites.count_documents({"status": "accepted"})
    pending_invites = await db.invites.count_documents({"status": "pending"})
    revoked = await db.invites.count_documents({"status": "revoked"})
    expired = await db.invites.count_documents({"status": "expired"})
    acceptance_rate = round(100 * accepted / total_invites) if total_invites else 0

    return {
        "total_setups": total_progress,
        "completed_setups": completed_progress,
        "in_progress_setups": total_progress - completed_progress,
        "completion_rate": round(100 * completed_progress / total_progress) if total_progress else 0,
        "median_hours_to_launch": round(median_hours, 1) if median_hours else None,
        "median_days_to_launch": round(median_hours / 24, 1) if median_hours else None,
        "funnel": [{"step": sid, **counts} for sid, counts in funnel.items()],
        "invites": {
            "total": total_invites, "accepted": accepted, "pending": pending_invites,
            "revoked": revoked, "expired": expired, "acceptance_rate": acceptance_rate,
        },
    }

@api_router.get("/reports/setup-health")
async def setup_health(user=Depends(get_current_user)):
    require_setup_role(user)
    return await _setup_health_payload()

async def _nudge_candidates(min_days: int = 3) -> List[Dict[str, Any]]:
    """Users with onboarding in progress whose last update is N days old."""
    cutoff = now_utc() - timedelta(days=min_days)
    cursor = db.onboarding_progress.find({"completed": {"$ne": True}}, {"_id": 0})
    rows = await cursor.to_list(2000)
    out = []
    for p in rows:
        try:
            updated = datetime.fromisoformat(p.get("updated_at") or p.get("created_at"))
            if updated.tzinfo is None: updated = updated.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if updated > cutoff:
            continue
        u = await db.users.find_one({"id": p["user_id"]}, {"_id": 0, "email": 1, "full_name": 1, "role": 1})
        if not u or not u.get("email"):
            continue
        steps = p.get("steps") or {}
        completed = sum(1 for v in steps.values() if v == "complete")
        next_step = next((s for s in ONBOARDING_STEPS if steps.get(s["id"]) not in ("complete", "skipped")), None)
        days_stalled = max(1, int((now_utc() - updated).total_seconds() / 86400))
        out.append({
            "user_id": p["user_id"], "email": u["email"], "full_name": u.get("full_name", ""), "role": u.get("role"),
            "percent_done": round(100 * completed / len(ONBOARDING_STEPS)),
            "next_step": next_step["id"] if next_step else "review",
            "next_step_label": next_step["label"] if next_step else "Review & Launch",
            "days_stalled": days_stalled, "updated_at": p.get("updated_at"),
            "current_step": p.get("current_step"),
            "last_nudged_at": p.get("last_nudged_at"),
        })
    return out

@api_router.get("/reports/nudge-candidates")
async def nudge_candidates(min_days: int = 3, user=Depends(get_current_user)):
    require_setup_role(user)
    return await _nudge_candidates(min_days)

class SendNudgesBody(BaseModel):
    min_days: int = 3
    cooldown_hours: int = 24  # don't nudge same user within N hours
    user_ids: Optional[List[str]] = None  # restrict to subset

async def _send_nudges(request: Optional[Request], inviter_name: str, min_days: int = 3, cooldown_hours: int = 24, user_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    candidates = await _nudge_candidates(min_days)
    if user_ids is not None:
        wanted = set(user_ids)
        candidates = [c for c in candidates if c["user_id"] in wanted]
    barn = await db.barn.find_one({"id": "primary"}, {"_id": 0, "name": 1}) or {}
    sent = 0; skipped = 0; errors = 0; detail = []
    cooldown = now_utc() - timedelta(hours=cooldown_hours)
    base = _base_url(request) if request else (os.environ.get("APP_BASE_URL", "").rstrip("/") or "https://herd-hub-19.emergent.host")
    for c in candidates:
        last = c.get("last_nudged_at")
        if last:
            try:
                dt = datetime.fromisoformat(last)
                if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
                if dt > cooldown:
                    skipped += 1
                    detail.append({"email": c["email"], "result": "cooldown"}); continue
            except Exception:
                pass
        mail = await send_email(
            to=c["email"],
            subject=f"Pick up where you left off at {barn.get('name') or 'EquineSync'}",
            template="onboarding_nudge",
            variables={
                "barn_name": barn.get("name") or "EquineSync",
                "invitee_name": (c["full_name"].split(" ")[0] if c["full_name"] else c["email"].split("@")[0]),
                "days_stalled": c["days_stalled"],
                "percent_done": c["percent_done"],
                "next_step_label": c["next_step_label"],
                "resume_url": f"{base}/onboarding",
                "ttl_days": 7,
            },
        )
        sent_ok = mail.get("status") in ("sent", "sandbox", "dev_logged")
        if mail.get("status") == "sent":
            sent += 1
            detail.append({"email": c["email"], "result": "sent"})
        elif mail.get("dev"):
            skipped += 1
            detail.append({"email": c["email"], "result": mail.get("status")})
        else:
            errors += 1
            detail.append({"email": c["email"], "result": "error", "error": mail.get("error", "")[:120]})
        # Only persist cooldown if the message was at least attempted successfully — transient
        # errors should NOT lock the recipient out of nudges for 24h.
        if sent_ok:
            await db.onboarding_progress.update_one(
                {"user_id": c["user_id"]},
                {"$set": {"last_nudged_at": iso(now_utc())}, "$inc": {"nudges_sent": 1}}
            )
        await _track("onboarding.nudge_sent", {"user_id": c["user_id"], "days_stalled": c["days_stalled"], "result": mail.get("status")}, None)
    return {"candidates": len(candidates), "sent": sent, "skipped": skipped, "errors": errors, "detail": detail}

@api_router.post("/admin/send-nudges")
async def admin_send_nudges(body: SendNudgesBody, request: Request, user=Depends(get_current_user)):
    require_setup_role(user)
    result = await _send_nudges(request, user["full_name"], body.min_days, body.cooldown_hours, body.user_ids)
    await _track("admin.nudges_run", {"trigger": "manual", **{k: v for k, v in result.items() if k != "detail"}}, user["id"])
    return result

# ---------------- Tenant Reset (admin support) ----------------
class TenantResetBody(BaseModel):
    scope: str = "onboarding"  # 'onboarding' | 'all_setup_data'
    confirm: str  # must equal "RESET"

@api_router.post("/admin/tenant-reset")
async def tenant_reset(body: TenantResetBody, user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    if body.confirm != "RESET":
        raise HTTPException(400, "Confirmation token required (send confirm=\"RESET\")")
    cleared: Dict[str, int] = {}
    if body.scope == "onboarding":
        r = await db.onboarding_progress.delete_many({})
        cleared["onboarding_progress"] = r.deleted_count
    elif body.scope == "all_setup_data":
        for c in ["onboarding_progress", "barn", "locations", "feed_templates",
                  "inventory", "recurring_schedules", "staff_invites", "invites"]:
            r = await db[c].delete_many({})
            cleared[c] = r.deleted_count
    else:
        raise HTTPException(400, "Unknown scope")
    await _track("tenant.reset", {"scope": body.scope, "cleared": cleared}, user["id"])
    return {"ok": True, "cleared": cleared}

# ---------------- Health ----------------
@api_router.get("/")
async def root():
    return {"app": "EquineSync", "status": "ok"}

# ---------------- Unified Task Engine ----------------
api_router.include_router(build_task_engine_router(db, get_current_user, _track))

# ---------------- Auth routes (extracted to routes/auth.py) ----------------
api_router.include_router(build_auth_router(db))

# ---------------- Notifications ----------------
api_router.include_router(build_notifications_router(db, get_current_user))

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def on_startup():
    # Auto-seed if empty
    if await db.users.count_documents({}) == 0:
        try:
            await seed()
            logger.info("Auto-seeded demo data.")
        except Exception as e:
            logger.exception("Seed failed: %s", e)

    # ---------- Task Engine bootstrap ----------
    try:
        engine = TaskEngine(db, _track)
        await engine.ensure_indexes()
        await ensure_refresh_indexes(db)
        await ensure_notification_indexes(db)
        # Seed demo templates if none exist yet
        admin_user = await db.users.find_one({"role": "admin"}, {"_id": 0, "id": 1})
        admin_id = admin_user.get("id") if admin_user else None
        seed_res = await seed_demo_templates(db, admin_id)
        if not seed_res.get("skipped"):
            logger.info("Task engine: seeded %d demo templates.", seed_res.get("templates_created", 0))
        # Initial materialization for the 14-day horizon
        created = await engine.materialize_all()
        if created:
            logger.info("Task engine: materialized %d initial occurrences.", created)
    except Exception:
        logger.exception("Task engine startup failed")

    async def _materialize_loop():
        await asyncio.sleep(60)
        engine_loop = TaskEngine(db, _track)
        while True:
            try:
                n = await engine_loop.materialize_all()
                if n:
                    logger.info("Task engine: rolling materialization created %d tasks.", n)
            except Exception:
                logger.exception("Materialization loop failed")
            await asyncio.sleep(15 * 60)

    if os.environ.get("DISABLE_TASK_MATERIALIZER", "").lower() not in ("1", "true", "yes"):
        asyncio.create_task(_materialize_loop())

    # ---------- Notification dispatcher ----------
    if os.environ.get("DISABLE_NOTIFICATIONS", "").lower() not in ("1", "true", "yes"):
        mailer_handle = {"send": send_email, "render": render_email}
        asyncio.create_task(start_notification_dispatcher(db, mailer_handle))

    # ---------- Owner daily digest scheduler (Phase-C) ----------
    if os.environ.get("DISABLE_OWNER_DIGEST", "").lower() not in ("1", "true", "yes"):
        try:
            await ensure_digest_indexes(db)
        except Exception:
            logger.exception("Could not create digest indexes")

        async def _digest_loop():
            # Default delivery hour is 07:00 barn-local; we use UTC offset for simplicity.
            target_hour = int(os.environ.get("OWNER_DIGEST_HOUR_UTC", "7"))
            mailer = {"send": send_email, "render": render_email}
            await asyncio.sleep(30)  # let startup settle
            while True:
                try:
                    now = datetime.now(timezone.utc)
                    if now.hour == target_hour:
                        res = await run_daily_digest_pass(db, mailer)
                        if res.get("sent"):
                            logger.info("Owner digest pass: sent=%d skipped=%d",
                                        res["sent"], res["skipped"])
                except Exception:
                    logger.exception("Owner digest loop iteration failed")
                # Sleep until top of next hour
                now = datetime.now(timezone.utc)
                seconds_to_next_hour = 3600 - (now.minute * 60 + now.second)
                await asyncio.sleep(max(60, seconds_to_next_hour))

        asyncio.create_task(_digest_loop())

    # Kick off the daily nudge scheduler (24h interval, 6h warm-up after boot).
    async def _nudge_loop():
        await asyncio.sleep(6 * 3600)  # initial delay so server is warm + first nudges aren't spam
        while True:
            try:
                result = await _send_nudges(None, "EquineSync Concierge", min_days=3, cooldown_hours=24)
                logger.info("Daily nudge run: %s", {k: v for k, v in result.items() if k != "detail"})
                await _track("admin.nudges_run", {"trigger": "auto_daily", "sent": result.get("sent"), "candidates": result.get("candidates")}, None)
            except Exception:
                logger.exception("Auto nudge loop failed")
            await asyncio.sleep(24 * 3600)

    if os.environ.get("DISABLE_AUTO_NUDGES", "").lower() not in ("1", "true", "yes"):
        asyncio.create_task(_nudge_loop())

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
