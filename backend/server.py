from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta, date
import bcrypt
import jwt as pyjwt

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ.get('JWT_SECRET', 'change-me')
JWT_ALG = 'HS256'
JWT_EXP_DAYS = 7

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
        'exp': datetime.now(timezone.utc) + timedelta(days=JWT_EXP_DAYS),
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

# ---------------- Auth ----------------
@api_router.post("/auth/register")
async def register(body: UserCreate):
    if body.role not in ROLES:
        raise HTTPException(400, "Invalid role")
    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(400, "Email already registered")
    user = {
        "id": new_id(),
        "email": body.email.lower(),
        "full_name": body.full_name,
        "role": body.role,
        "password_hash": hash_pwd(body.password),
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(user)
    token = create_token(user["id"], user["role"])
    return {"token": token, "user": {k: v for k, v in user.items() if k not in ("password_hash", "_id")}}

@api_router.post("/auth/login")
async def login(body: LoginBody):
    user = await db.users.find_one({"email": body.email.lower()})
    if not user or not verify_pwd(body.password, user.get("password_hash", "")):
        raise HTTPException(401, "Invalid credentials")
    token = create_token(user["id"], user["role"])
    return {"token": token, "user": {k: v for k, v in user.items() if k not in ("password_hash", "_id")}}

@api_router.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return user

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
    today_str = now_utc().date().isoformat()
    today_prefix = today_str  # ISO date prefix
    # parallel-ish counts using projections + filters
    total_horses = await db.horses.count_documents({})
    stall_rest = await db.horses.count_documents({"status": {"$in": ["stall_rest", "rehab"]}})
    active_injuries = await db.injuries.count_documents({"status": {"$in": ["active", "monitoring", "improving"]}})
    feed_today_total = await db.feed_tasks.count_documents({"date": today_str})
    feed_pending = await db.feed_tasks.count_documents({"date": today_str, "completed": {"$ne": True}})
    meds_missed = await db.medication_logs.count_documents({"scheduled_time": {"$regex": f"^{today_prefix}"}, "status": "missed"})
    meds_due = await db.medication_logs.count_documents({"scheduled_time": {"$regex": f"^{today_prefix}"}, "status": {"$nin": ["given", "missed", "skipped"]}})
    pending_sr = await db.service_requests.count_documents({"status": "pending"})
    open_incidents = await db.incidents.count_documents({"status": {"$ne": "closed"}})
    lessons_today = await db.lessons.count_documents({"start_time": {"$regex": f"^{today_prefix}"}})

    overdue_cursor = db.invoices.find({"status": {"$in": ["open", "overdue"]}}, {"_id": 0, "total": 1})
    overdue_list = await overdue_cursor.to_list(1000)
    overdue_invoices = len(overdue_list)
    overdue_amount = sum(i.get("total", 0) for i in overdue_list)

    wellness_cursor = db.horses.find({}, {"_id": 0, "wellness_score": 1})
    wellness_list = await wellness_cursor.to_list(1000)
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
    }

@api_router.get("/dashboard/barn-board")
async def barn_board(user=Depends(get_current_user)):
    today_str = now_utc().date().isoformat()
    today_prefix = today_str
    feed = await db.feed_tasks.find({"date": today_str}, {"_id": 0}).to_list(200)
    med_logs = await db.medication_logs.find({"scheduled_time": {"$regex": f"^{today_prefix}"}}, {"_id": 0}).to_list(200)
    lessons = await db.lessons.find({"start_time": {"$regex": f"^{today_prefix}"}}, {"_id": 0}).to_list(200)
    stall_rest = await db.horses.find({"status": {"$in": ["stall_rest", "rehab"]}}, {"_id": 0}).to_list(100)
    incidents = await db.incidents.find({}, {"_id": 0}).sort("occurred_at", -1).to_list(5)
    return {
        "date": today_str,
        "feed": feed,
        "medications": med_logs,
        "lessons": lessons,
        "stall_rest": stall_rest,
        "urgent": incidents,
        "weather": {"temp_f": 58, "condition": "Light Rain", "alert": "Wet footing — limit outdoor jumping"},
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

# ---------------- Health ----------------
@api_router.get("/")
async def root():
    return {"app": "EquineSync", "status": "ok"}

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
