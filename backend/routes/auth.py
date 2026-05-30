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
from config import JWT_SECRET, JWT_ALG
from rate_limit import auth_rate_limiter

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
            "created_at": now_iso(),
        }
        await db.users.insert_one(user)
        token = create_token(user["id"], user["role"])
        ua, ip = await client_meta(request)
        refresh = await issue_refresh_token(db, user["id"], user_agent=ua, ip=ip)
        return {
            "token": token,
            "refresh_token": refresh,
            "expires_in_seconds": JWT_EXP_HOURS * 3600,
            "user": user_safe(user),
        }

    @router.post("/auth/login", dependencies=[Depends(auth_rate_limiter)])
    async def login(request: Request, body: LoginBody):
        user = await db.users.find_one({"email": body.email.lower()})
        if not user or not verify_pwd(body.password, user.get("password_hash", "")):
            raise HTTPException(401, "Invalid credentials")
        token = create_token(user["id"], user["role"])
        ua, ip = await client_meta(request)
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

    return router
