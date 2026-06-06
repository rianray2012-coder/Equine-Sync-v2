"""EquineSync API — application assembly (Phase 3G).

This module is intentionally thin: it loads the environment, validates the
security-critical configuration, constructs the FastAPI app, wires every
domain router under ``/api``, attaches middleware, and registers the
application lifecycle (startup bootstrap + background loops).

All shared infrastructure now lives in ``core/*``:
  - ``core.db``        Mongo client + ``db`` handle
  - ``core.auth``      JWT helpers, ``get_current_user`` (Security Patch 2E gate)
  - ``core.helpers``   generic time/id + Mongo listing utilities
  - ``core.analytics`` ``_track`` event recorder
  - ``core.urls``      ``_base_url`` link resolution
  - ``core.constants`` ``ROLES`` / ``ROLE_LABELS``
  - ``core.lifespan``  startup/shutdown + materializer/dispatcher/digest/nudge loops

No module imports from ``server.py``; the ASGI entrypoint remains ``server:app``.
"""
from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import logging
from pathlib import Path

# Load .env BEFORE importing any submodule that reads env vars at import time
# (core.config reads JWT_SECRET; core.db reads MONGO_URL/DB_NAME; auth_security
# reads JWT_EXP_HOURS).
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Centralized config validation — fail fast on missing/insecure security vars
# (Phase 2A). Must run after load_dotenv and before importing modules below
# that read env at import time.
from core.config import validate_config, get_cors_origins
validate_config()

# Shared infrastructure (imported only after .env load + config validation).
from core.db import db
from core.auth import get_current_user, create_token, hash_pwd, require_setup_role
from core.helpers import (
    new_id, clean, list_collection, _user_safe, _client_meta,
)
from core.analytics import _track
from core.urls import _base_url
from core.constants import ROLES, ROLE_LABELS
from core.lifespan import register_lifecycle

from auth_security import (
    JWT_EXP_HOURS,
    SecurityHeadersMiddleware,
    issue_refresh_token,
)
from mailer import send as send_email
from task_engine import (
    build_router as build_task_engine_router,
    DEFAULT_TENANT_ID as TASK_TENANT_ID,
)
from notifications import build_router as build_notifications_router
from routes.auth import build_router as build_auth_router
from routes.dashboard import build_router as build_dashboard_router
from routes.reports import build_router as build_reports_router
from routes.invites import build_router as build_invites_router
from routes.onboarding import build_router as build_onboarding_router, ONBOARDING_STEPS
from routes.care import build_router as build_care_router
from routes.horses import build_router as build_horses_router
from routes.operations import build_router as build_operations_router
from routes.billing import build_router as build_billing_router
from routes.system import build_router as build_system_router
from routes.admin import build_router as build_admin_router
from routes.analytics import build_router as build_analytics_router
from routes.digests import build_router as build_digests_router
from routes.barns import build_router as build_barns_router
from routes.audit import build_router as build_audit_router
from routes.owner_updates import build_router as build_owner_updates_router
from seed_data import run_seed

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="EquineSync API")
api_router = APIRouter(prefix="/api")

# ---------------- Router assembly ----------------
# Unified Task Engine
api_router.include_router(build_task_engine_router(db, get_current_user, _track))

# Auth (routes/auth.py)
api_router.include_router(build_auth_router(db))

# Notifications
api_router.include_router(build_notifications_router(db, get_current_user))

# Dashboard (routes/dashboard.py)
api_router.include_router(build_dashboard_router(db, get_current_user, TASK_TENANT_ID))

# Reports (routes/reports.py) — exposes send_nudges for the startup auto-nudge loop
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
api_router.include_router(_reports_router)

# Invites (routes/invites.py)
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

# Onboarding (routes/onboarding.py)
api_router.include_router(build_onboarding_router(
    db=db,
    get_current_user=get_current_user,
    require_setup_role=require_setup_role,
    roles=ROLES,
    list_collection=list_collection,
    clean=clean,
    new_id=new_id,
))

# Horses — horse-profile CRUD (routes/horses.py).
# NOTE: GET /horses/{id}/timeline intentionally remains in task_engine.py
# (it is a task-event projection, not horse-profile CRUD).
api_router.include_router(build_horses_router(
    db=db,
    get_current_user=get_current_user,
    list_collection=list_collection,
    clean=clean,
    new_id=new_id,
))

# Care records (routes/care.py)
api_router.include_router(build_care_router(
    db=db,
    get_current_user=get_current_user,
    list_collection=list_collection,
    clean=clean,
    new_id=new_id,
))

# Operations (routes/operations.py)
api_router.include_router(build_operations_router(
    db=db,
    get_current_user=get_current_user,
    list_collection=list_collection,
    clean=clean,
    new_id=new_id,
))

# Billing — invoices (routes/billing.py)
api_router.include_router(build_billing_router(
    db=db,
    get_current_user=get_current_user,
    list_collection=list_collection,
    clean=clean,
    new_id=new_id,
))

# System — root + health (routes/system.py)
api_router.include_router(build_system_router(db))

# Admin — seed + tenant-reset (routes/admin.py)
api_router.include_router(build_admin_router(
    db=db,
    get_current_user=get_current_user,
    track=_track,
    run_seed=run_seed,
))

# Analytics (routes/analytics.py)
api_router.include_router(build_analytics_router(db, get_current_user, require_setup_role))

# Owner digest + weekly recap HTTP routes (routes/digests.py)
api_router.include_router(build_digests_router(db=db, get_current_user=get_current_user))

# Barn provisioning — Phase 4D multi-barn (routes/barns.py)
api_router.include_router(build_barns_router(
    db=db,
    get_current_user=get_current_user,
    hash_pwd=hash_pwd,
    user_safe=_user_safe,
    new_id=new_id,
    onboarding_steps=ONBOARDING_STEPS,
))

# Audit log read API — Phase 5D (routes/audit.py)
api_router.include_router(build_audit_router(db=db, get_current_user=get_current_user))

# Owner Updates — Phase 7A Owner Trust Layer (routes/owner_updates.py)
api_router.include_router(build_owner_updates_router(
    db=db,
    get_current_user=get_current_user,
    list_collection=list_collection,
    clean=clean,
    new_id=new_id,
))

app.include_router(api_router)

# ---------------- Middleware ----------------
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=get_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)

# ---------------- Lifecycle (startup/shutdown + background loops) ----------------
register_lifecycle(app, send_nudges=_send_nudges)
