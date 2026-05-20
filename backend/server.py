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
from routes.dashboard import build_router as build_dashboard_router
from routes.reports import build_router as build_reports_router
from routes.invites import build_router as build_invites_router
from routes.onboarding import build_router as build_onboarding_router, ONBOARDING_STEPS
from routes.care import build_router as build_care_router
from routes.operations import build_router as build_operations_router
from owner_digest import (
    run_daily_digest_pass,
    send_digest_to_owner,
    build_digest_for_owner,
    render_digest_html,
    render_digest_text,
    ensure_digest_indexes,
    build_weekly_recap_for_owner,
    send_weekly_recap_to_owner,
    render_weekly_recap_html,
    render_weekly_recap_text,
    run_weekly_recap_pass,
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


# ---------------- Owner weekly recap (lightweight Sunday update) ----------------

@api_router.post("/notifications/weekly-recap/preview")
async def weekly_recap_preview(user=Depends(get_current_user)):
    """Owner: preview this week's recap. Returns {empty:true} if nothing meaningful."""
    payload = await build_weekly_recap_for_owner(db, user["id"])
    if not payload:
        return {"empty": True, "reason": "no_updates_this_week"}
    return {
        "empty": False,
        "payload": payload,
        "html": render_weekly_recap_html(payload, app_base_url=os.environ.get("PUBLIC_APP_URL", "")),
        "text": render_weekly_recap_text(payload),
    }


@api_router.post("/notifications/weekly-recap/send-me")
async def weekly_recap_send_me(user=Depends(get_current_user)):
    """Owner: trigger their own weekly recap now."""
    if user.get("role") != "horse_owner":
        raise HTTPException(403, "Owner accounts only")
    mailer_handle = {"send": send_email, "render": render_email}
    return await send_weekly_recap_to_owner(db, mailer_handle, user["id"])


@api_router.post("/admin/weekly-recap/run-now")
async def weekly_recap_run_now(user=Depends(get_current_user)):
    """Admin: force-run this week's recap pass (idempotent on ISO week key)."""
    if user.get("role") not in ("admin", "barn_manager"):
        raise HTTPException(403, "Admin/Manager only")
    mailer_handle = {"send": send_email, "render": render_email}
    return await run_weekly_recap_pass(db, mailer_handle)


# ---------------- Dashboard summary (extracted to routes/dashboard.py) ----------------
# See routes/dashboard.py — included into api_router at the bottom of this file.

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

# ---------------- Shared analytics + url helpers (used across modules) ----------------
async def _track(name: str, props: Dict[str, Any], user_id: Optional[str] = None):
    """Internal: record an analytics event server-side."""
    try:
        await db.events.insert_one({
            "id": new_id(), "name": name, "props": props or {},
            "user_id": user_id, "at": iso(now_utc()),
        })
    except Exception:
        logger.exception("Failed to record event %s", name)


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


# ---------------- Magic-link Invites (extracted to routes/invites.py) ----------------
ROLE_LABELS = {
    "admin": "Stable Owner / Admin", "barn_manager": "Barn Manager", "trainer": "Trainer",
    "groom": "Groom", "working_student": "Working Student", "horse_owner": "Horse Owner",
    "rider": "Rider", "parent": "Parent / Guardian", "veterinarian": "Veterinarian", "farrier": "Farrier",
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

# ---------------- Setup Health Reports (extracted to routes/reports.py) ----------------
# See routes/reports.py — included into api_router below. The helpers
# (setup_health_payload, nudge_candidates, send_nudges) are exposed on the
# router instance via _reports_helpers so the startup auto-nudge scheduler can
# reuse send_nudges without duplicating the implementation.
_reports_router = build_reports_router(
    db=db,
    get_current_user=get_current_user,
    onboarding_steps=ONBOARDING_STEPS,
    mailer_send=send_email,
    track=lambda *a, **kw: _track(*a, **kw),
    base_url_from_request=lambda req: _base_url(req),
    require_setup_role=require_setup_role,
)
_send_nudges = _reports_router._reports_helpers["send_nudges"]

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

# ---------------- Dashboard (extracted to routes/dashboard.py) ----------------
api_router.include_router(build_dashboard_router(db, get_current_user, TASK_TENANT_ID))

# ---------------- Reports (extracted to routes/reports.py) ----------------
api_router.include_router(_reports_router)

# ---------------- Invites (extracted to routes/invites.py) ----------------
api_router.include_router(build_invites_router(
    db=db,
    get_current_user=get_current_user,
    require_setup_role=require_setup_role,
    roles=ROLES,
    role_labels=ROLE_LABELS,
    onboarding_steps=ONBOARDING_STEPS,
    mailer_send=send_email,
    track=_track,
    base_url_from_request=_base_url,
    create_token=create_token,
    hash_pwd=hash_pwd,
    user_safe=_user_safe,
    client_meta=_client_meta,
    issue_refresh_token=issue_refresh_token,
    jwt_exp_hours=JWT_EXP_HOURS,
    new_id=new_id,
))

# ---------------- Onboarding (extracted to routes/onboarding.py) ----------------
api_router.include_router(build_onboarding_router(
    db=db,
    get_current_user=get_current_user,
    require_setup_role=require_setup_role,
    roles=ROLES,
    list_collection=list_collection,
    clean=clean,
    new_id=new_id,
))

# ---------------- Care records (extracted to routes/care.py) ----------------
api_router.include_router(build_care_router(
    db=db,
    get_current_user=get_current_user,
    list_collection=list_collection,
    clean=clean,
    new_id=new_id,
))

# ---------------- Operations (extracted to routes/operations.py) ----------------
api_router.include_router(build_operations_router(
    db=db,
    get_current_user=get_current_user,
    list_collection=list_collection,
    clean=clean,
    new_id=new_id,
))

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

    # ---------- Owner weekly recap scheduler (lightweight, Sunday-evening) ----------
    if os.environ.get("DISABLE_OWNER_WEEKLY_RECAP", "").lower() not in ("1", "true", "yes"):
        async def _weekly_recap_loop():
            # Default: Sunday 18:00 UTC. Override via env if needed.
            target_dow = int(os.environ.get("OWNER_WEEKLY_RECAP_DOW", "6"))  # Mon=0 .. Sun=6
            target_hour = int(os.environ.get("OWNER_WEEKLY_RECAP_HOUR_UTC", "18"))
            mailer = {"send": send_email, "render": render_email}
            await asyncio.sleep(45)  # let startup settle (slight offset from daily digest)
            while True:
                try:
                    now = datetime.now(timezone.utc)
                    if now.weekday() == target_dow and now.hour == target_hour:
                        res = await run_weekly_recap_pass(db, mailer, now=now)
                        if res.get("sent"):
                            logger.info("Owner weekly recap: sent=%d skipped=%d week=%s",
                                        res["sent"], res["skipped"], res["for_week"])
                except Exception:
                    logger.exception("Owner weekly recap loop iteration failed")
                # Sleep until top of next hour
                now = datetime.now(timezone.utc)
                seconds_to_next_hour = 3600 - (now.minute * 60 + now.second)
                await asyncio.sleep(max(60, seconds_to_next_hour))

        asyncio.create_task(_weekly_recap_loop())

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
