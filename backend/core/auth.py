"""Authentication & authorization infrastructure (Phase 3G).

JWT issuance/verification, password hashing, the ``get_current_user`` FastAPI
dependency (including the Security Patch 2E email-verification defense-in-depth
gate), and the barn-setup role guard. Relocated verbatim from ``server.py``
during the app-assembly refactor — behavior is identical.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
import jwt as pyjwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core.config import JWT_SECRET, JWT_ALG, user_verification_ok
from core.db import db
from core.tenancy import resolve_barn_id
from auth_security import JWT_EXP_HOURS

security = HTTPBearer(auto_error=False)


def hash_pwd(p: str) -> str:
    return bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def create_token(user_id: str, role: str, barn_id: Optional[str] = None) -> str:
    payload = {
        'sub': user_id,
        'role': role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXP_HOURS),
    }
    # Phase 4A: forward-compat barn_id claim. Authorization/scoping always reads
    # the fresh user document, never this claim.
    if barn_id is not None:
        payload['barn_id'] = barn_id
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
    # Phase 4A: attach the authoritative barn scope from the user doc
    # (source of truth — never the JWT claim; missing => primary, legacy-safe).
    user["barn_id"] = resolve_barn_id(user)
    return user


def require_setup_role(user):
    """Stable Owner / Admin / Barn Manager can edit barn-level setup."""
    if user.get("role") not in ("admin", "barn_manager"):
        raise HTTPException(status_code=403, detail="Owner / Barn Manager access required")
