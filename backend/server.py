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

# Centralized config validation — fail fast on missing/insecure security vars (Phase 2A).
# Must run after load_dotenv and before security-critical setup below.
from core.config import (
    JWT_SECRET, JWT_ALG, validate_config, get_cors_origins,
    auto_seed_enabled, user_verification_ok,
)
validate_config()

from core.auth_tokens import ensure_auth_token_indexes
from core.login_attempts import ensure_login_attempt_indexes

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
from routes.system import build_router as build_system_router
from routes.admin import build_router as build_admin_router
from routes.analytics import build_router as build_analytics_router
from seed_data import run_seed
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
    # Defense-in-depth (Security Patch 2E hardening): when email verification is
    # enforced, block unverified users even if they hold an old/pre-issued token.
    # Missing email_verified is treated as verified (legacy/backfilled users).
    if not user_verification_ok(user):
        raise HTTPException(status_code=403, detail="Email not verified")
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

# ---------------- Seed (extracted to seed_data.py + routes/admin.py) ----------------

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

# ---------------- Analytics (extracted to routes/analytics.py) ----------------

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

# ---------------- Tenant Reset (extracted to routes/admin.py) ----------------

# ---------------- System routes (root + health) extracted to routes/system.py ----------------

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

# ---------------- System (root + health, extracted to routes/system.py) ----------------
api_router.include_router(build_system_router(db))

# ---------------- Admin (seed + tenant-reset, extracted to routes/admin.py) ----------------
api_router.include_router(build_admin_router(
    db=db,
    get_current_user=get_current_user,
    track=_track,
    run_seed=run_seed,
))

# ---------------- Analytics (extracted to routes/analytics.py) ----------------
api_router.include_router(build_analytics_router(db, get_current_user, require_setup_role))

# (health endpoint extracted to routes/system.py)


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=get_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def on_startup():
    # Auto-seed if empty — but NEVER in production (Security Patch 2E hardening),
    # so a fresh production DB never silently creates demo accounts.
    if auto_seed_enabled() and await db.users.count_documents({}) == 0:
        try:
            await run_seed(db)
            logger.info("Auto-seeded demo data.")
        except Exception as e:
            logger.exception("Seed failed: %s", e)

    # ---------- Task Engine bootstrap ----------
    try:
        engine = TaskEngine(db, _track)
        await engine.ensure_indexes()
        await ensure_refresh_indexes(db)
        await ensure_notification_indexes(db)
        await ensure_auth_token_indexes(db)
        # Safe migration (Phase 2C): backfill email_verified=True for any pre-existing
        # users missing the field so verification rollout never locks them out.
        backfill = await db.users.update_many(
            {"email_verified": {"$exists": False}},
            {"$set": {"email_verified": True}},
        )
        if backfill.modified_count:
            logger.info("Backfilled email_verified=True for %d existing users.", backfill.modified_count)
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
