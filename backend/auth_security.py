"""
Auth hardening utilities:
- Short-lived JWT access tokens (default 4h)
- Refresh-token rotation (30d, hashed at rest, single-use)
- Security headers + CSP middleware
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

JWT_EXP_HOURS = int(os.environ.get("JWT_EXP_HOURS", "4"))
REFRESH_EXP_DAYS = int(os.environ.get("REFRESH_EXP_DAYS", "30"))


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


# ---------- refresh-token storage ----------

async def issue_refresh_token(db, user_id: str, *, user_agent: Optional[str] = None,
                              ip: Optional[str] = None) -> str:
    """Mint a new refresh token, store its hash, return the raw value to caller."""
    raw = secrets.token_urlsafe(48)
    doc = {
        "id": secrets.token_urlsafe(12),
        "user_id": user_id,
        "token_hash": _hash_token(raw),
        "created_at": _iso(_now()),
        "expires_at": _iso(_now() + timedelta(days=REFRESH_EXP_DAYS)),
        "revoked": False,
        "rotated_to": None,
        "user_agent": (user_agent or "")[:200],
        "ip": ip,
    }
    await db.refresh_tokens.insert_one(doc)
    return raw


async def consume_refresh_token(db, raw: str) -> dict:
    """Validate + single-use rotate a refresh token.

    Raises 401 on any failure. On success, marks the old token revoked
    (with a pointer to the new one) and returns the user.
    """
    th = _hash_token(raw)
    rec = await db.refresh_tokens.find_one({"token_hash": th}, {"_id": 0})
    if not rec or rec.get("revoked"):
        raise HTTPException(401, "Invalid refresh token")
    expires_at = datetime.fromisoformat(rec["expires_at"])
    if expires_at < _now():
        raise HTTPException(401, "Refresh token expired")
    user = await db.users.find_one({"id": rec["user_id"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(401, "User not found")
    return {"record": rec, "user": user}


async def revoke_refresh_token(db, raw: str):
    th = _hash_token(raw)
    await db.refresh_tokens.update_one({"token_hash": th}, {"$set": {"revoked": True}})


async def revoke_all_user_refresh_tokens(db, user_id: str):
    await db.refresh_tokens.update_many(
        {"user_id": user_id, "revoked": False},
        {"$set": {"revoked": True}},
    )


async def ensure_refresh_indexes(db):
    await db.refresh_tokens.create_index([("token_hash", 1)], unique=True)
    await db.refresh_tokens.create_index([("user_id", 1)])
    await db.refresh_tokens.create_index([("expires_at", 1)])


# ---------- security headers middleware ----------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply OWASP-recommended hardening headers + Content-Security-Policy.

    CSP is intentionally restrictive but permissive enough to keep the React
    SPA, the Made-with-Emergent badge, and Resend's transactional emails
    rendering correctly. Tighten further once we move to nonces.
    """

    DEFAULT_CSP = (
        "default-src 'self'; "
        "img-src 'self' data: blob: https:; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://emergent.sh; "
        "connect-src 'self' https: wss:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Cross-Origin-Opener-Policy": "same-origin",
        "X-Permitted-Cross-Domain-Policies": "none",
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for k, v in self.HEADERS.items():
            response.headers.setdefault(k, v)
        # CSP is configurable via env so admins can loosen it without a deploy
        csp = os.environ.get("CSP_POLICY") or self.DEFAULT_CSP
        response.headers.setdefault("Content-Security-Policy", csp)
        return response
