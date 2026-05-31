"""routes/auth.py — JWT auth + refresh-token rotation endpoints.

Factored out of server.py per blueprint §14. Exposes a build_router(...)
factory that depends only on the Mongo db handle.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
import jwt as pyjwt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

from auth_security import (
    JWT_EXP_HOURS,
    issue_refresh_token,
    consume_refresh_token,
    revoke_refresh_token,
    revoke_all_user_refresh_tokens,
)
from core.config import (
    JWT_SECRET,
    JWT_ALG,
    app_base_url,
    is_production,
    enforce_email_verification,
    email_verify_ttl_hours,
    password_reset_ttl_hours,
    login_lockout_enabled,
    login_max_attempts,
    login_lockout_minutes,
    login_attempt_window_minutes,
)
from core.rate_limit import auth_rate_limiter
from mailer import send as send_email
from core.auth_tokens import (
    issue_token,
    consume_token,
    PURPOSE_PASSWORD_RESET,
    PURPOSE_EMAIL_VERIFY,
)
from core.login_attempts import check_lockout, record_failure, clear_attempts

logger = logging.getLogger(__name__)

ROLES = ["admin", "barn_manager", "trainer", "groom", "working_student",
         "horse_owner", "rider", "parent", "veterinarian", "farrier"]


# ---------------- helpers ----------------

def hash_pwd(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_pwd(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode("utf-8"), h.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXP_HOURS),
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


security = HTTPBearer(auto_error=False)


def make_current_user_dependency(db):
    """Returns a FastAPI dependency that resolves the current user from JWT."""
    async def _get(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)):
        if not creds:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            payload = pyjwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALG])
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    return _get


def require_setup_role(user):
    if user.get("role") not in ("admin", "barn_manager"):
        raise HTTPException(status_code=403, detail="Owner / Barn Manager access required")


def user_safe(user: dict) -> dict:
    return {k: v for k, v in user.items() if k not in ("password_hash", "_id")}


async def client_meta(request: Optional[Request]):
    ua = request.headers.get("user-agent") if request else None
    ip = request.client.host if request and request.client else None
    return ua, ip


# ---------------- request bodies ----------------

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = "admin"


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class RefreshBody(BaseModel):
    refresh_token: str


class ForgotPasswordBody(BaseModel):
    email: EmailStr


class ResetPasswordBody(BaseModel):
    token: str
    new_password: str


class TokenBody(BaseModel):
    token: str


class ResendVerificationBody(BaseModel):
    email: EmailStr


# ---------------- transactional email helpers ----------------

async def _send_verification_email(user: dict, raw: str, ttl_hours: int):
    base = app_base_url()
    verify_url = f"{base}/verify-email?token={raw}" if base else f"/verify-email?token={raw}"
    try:
        await send_email(
            to=user["email"],
            subject="Confirm your EquineSync email",
            template="verify_email",
            variables={
                "full_name": user.get("full_name", "there"),
                "verify_url": verify_url,
                "ttl_label": f"{ttl_hours} hours",
            },
            base="_base_auth",
        )
    except Exception:
        logger.exception("verification email send failed")


async def _send_reset_email(user: dict, raw: str, ttl_hours: int):
    base = app_base_url()
    reset_url = f"{base}/reset-password?token={raw}" if base else f"/reset-password?token={raw}"
    label = "1 hour" if ttl_hours == 1 else f"{ttl_hours} hours"
    try:
        await send_email(
            to=user["email"],
            subject="Reset your EquineSync password",
            template="password_reset",
            variables={
                "full_name": user.get("full_name", "there"),
                "reset_url": reset_url,
                "ttl_label": label,
            },
            base="_base_auth",
        )
    except Exception:
        logger.exception("reset email send failed")


# ---------------- router factory ----------------

def build_router(db) -> APIRouter:
    router = APIRouter()
    get_current_user = make_current_user_dependency(db)

    @router.post("/auth/register", dependencies=[Depends(auth_rate_limiter)])
    async def register(request: Request, body: UserCreate):
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
            "email_verified": False,
            "created_at": now_iso(),
        }
        await db.users.insert_one(user)
        # Issue + send an email-verification token (best-effort; never blocks signup).
        verify_ttl = email_verify_ttl_hours()
        raw_verify = await issue_token(db, user["id"], PURPOSE_EMAIL_VERIFY, verify_ttl)
        await _send_verification_email(user, raw_verify, verify_ttl)
        token = create_token(user["id"], user["role"])
        ua, ip = await client_meta(request)
        refresh = await issue_refresh_token(db, user["id"], user_agent=ua, ip=ip)
        resp = {
            "token": token,
            "refresh_token": refresh,
            "expires_in_seconds": JWT_EXP_HOURS * 3600,
            "user": user_safe(user),
        }
        # Dev convenience only — never leak the raw token in production.
        if not is_production():
            resp["dev_verification_token"] = raw_verify
        return resp

    @router.post("/auth/login", dependencies=[Depends(auth_rate_limiter)])
    async def login(request: Request, body: LoginBody):
        email = body.email.lower()
        ua, ip = await client_meta(request)
        # Account-level brute-force lockout (Phase 2D).
        if login_lockout_enabled():
            remaining = await check_lockout(db, email)
            if remaining:
                mins = (remaining + 59) // 60
                raise HTTPException(
                    423,
                    f"Account temporarily locked due to repeated failed attempts. "
                    f"Try again in {mins} minute(s).",
                )
        user = await db.users.find_one({"email": email})
        if not user or not verify_pwd(body.password, user.get("password_hash", "")):
            if login_lockout_enabled():
                await record_failure(
                    db, email,
                    max_attempts=login_max_attempts(),
                    window_minutes=login_attempt_window_minutes(),
                    lockout_minutes=login_lockout_minutes(),
                    ip=ip,
                )
            raise HTTPException(401, "Invalid credentials")
        # Successful auth — clear any failed-attempt history.
        if login_lockout_enabled():
            await clear_attempts(db, email)
        # Email-verification gate is OFF by default (ENFORCE_EMAIL_VERIFICATION).
        # Missing field is treated as verified so existing users are never locked out.
        if enforce_email_verification() and not user.get("email_verified", True):
            raise HTTPException(
                403,
                "Email not verified. Please check your inbox for the verification link.",
            )
        token = create_token(user["id"], user["role"])
        refresh = await issue_refresh_token(db, user["id"], user_agent=ua, ip=ip)
        return {
            "token": token,
            "refresh_token": refresh,
            "expires_in_seconds": JWT_EXP_HOURS * 3600,
            "user": user_safe(user),
        }

    @router.post("/auth/refresh", dependencies=[Depends(auth_rate_limiter)])
    async def refresh(request: Request, body: RefreshBody):
        res = await consume_refresh_token(db, body.refresh_token)
        user = res["user"]
        old = res["record"]
        await revoke_refresh_token(db, body.refresh_token)
        token = create_token(user["id"], user["role"])
        ua, ip = await client_meta(request)
        new_refresh = await issue_refresh_token(db, user["id"], user_agent=ua, ip=ip)
        await db.refresh_tokens.update_one(
            {"id": old["id"]}, {"$set": {"rotated_to": new_refresh[:8] + "…"}},
        )
        return {
            "token": token,
            "refresh_token": new_refresh,
            "expires_in_seconds": JWT_EXP_HOURS * 3600,
            "user": user_safe(user),
        }

    @router.post("/auth/logout")
    async def logout(body: RefreshBody, user=Depends(get_current_user)):
        try:
            await revoke_refresh_token(db, body.refresh_token)
        except Exception:
            logger.exception("logout: refresh revoke failed")
        return {"ok": True}

    @router.post("/auth/logout-all")
    async def logout_all(user=Depends(get_current_user)):
        await revoke_all_user_refresh_tokens(db, user["id"])
        return {"ok": True}

    @router.get("/auth/me")
    async def me(user=Depends(get_current_user)):
        return user

    # ---------------- password reset ----------------

    @router.post("/auth/forgot-password", dependencies=[Depends(auth_rate_limiter)])
    async def forgot_password(request: Request, body: ForgotPasswordBody):
        user = await db.users.find_one({"email": body.email.lower()})
        # Always return the same response to avoid leaking which emails exist.
        resp = {
            "ok": True,
            "message": "If an account exists for that email, a reset link has been sent.",
        }
        if user:
            ttl = password_reset_ttl_hours()
            raw = await issue_token(db, user["id"], PURPOSE_PASSWORD_RESET, ttl)
            await _send_reset_email(user, raw, ttl)
            if not is_production():
                resp["dev_token"] = raw
        return resp

    @router.post("/auth/reset-password", dependencies=[Depends(auth_rate_limiter)])
    async def reset_password(request: Request, body: ResetPasswordBody):
        if len(body.new_password) < 8:
            raise HTTPException(400, "Password must be at least 8 characters")
        rec = await consume_token(db, body.token, PURPOSE_PASSWORD_RESET)
        if not rec:
            raise HTTPException(400, "Invalid or expired reset token")
        await db.users.update_one(
            {"id": rec["user_id"]},
            {"$set": {"password_hash": hash_pwd(body.new_password)}},
        )
        # Invalidate all existing sessions after a password change.
        await revoke_all_user_refresh_tokens(db, rec["user_id"])
        return {"ok": True, "message": "Password updated. Please sign in with your new password."}

    # ---------------- email verification ----------------

    @router.post("/auth/verify-email")
    async def verify_email(body: TokenBody):
        rec = await consume_token(db, body.token, PURPOSE_EMAIL_VERIFY)
        if not rec:
            raise HTTPException(400, "Invalid or expired verification token")
        await db.users.update_one(
            {"id": rec["user_id"]}, {"$set": {"email_verified": True}}
        )
        return {"ok": True, "message": "Email verified."}

    @router.post("/auth/resend-verification", dependencies=[Depends(auth_rate_limiter)])
    async def resend_verification(request: Request, body: ResendVerificationBody):
        user = await db.users.find_one({"email": body.email.lower()})
        resp = {
            "ok": True,
            "message": "If an account exists and is unverified, a new link has been sent.",
        }
        if user and not user.get("email_verified", True):
            ttl = email_verify_ttl_hours()
            raw = await issue_token(db, user["id"], PURPOSE_EMAIL_VERIFY, ttl)
            await _send_verification_email(user, raw, ttl)
            if not is_production():
                resp["dev_token"] = raw
        return resp

    return router
