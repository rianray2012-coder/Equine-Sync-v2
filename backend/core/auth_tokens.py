"""One-time auth tokens for password reset and email verification (Phase 2C).

Tokens are cryptographically random, **hashed at rest** (sha256), single-use,
and expiring. Both purposes share a single ``auth_tokens`` collection
distinguished by ``purpose``.

This mirrors the refresh-token hashing approach in ``auth_security.py`` so the
raw token is never stored.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

PURPOSE_PASSWORD_RESET = "password_reset"
PURPOSE_EMAIL_VERIFY = "email_verify"


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


async def issue_token(db, user_id: str, purpose: str, ttl_hours: int) -> str:
    """Mint a one-time token for ``purpose``; store its hash, return the raw value."""
    raw = secrets.token_urlsafe(32)
    doc = {
        "id": secrets.token_urlsafe(12),
        "user_id": user_id,
        "purpose": purpose,
        "token_hash": _hash(raw),
        "created_at": _iso(_now()),
        "expires_at": _iso(_now() + timedelta(hours=ttl_hours)),
        "used": False,
    }
    await db.auth_tokens.insert_one(doc)
    return raw


async def consume_token(db, raw: str, purpose: str) -> Optional[dict]:
    """Validate + single-use a token. Returns the record on success, else None.

    Returns ``None`` for unknown, wrong-purpose, already-used, or expired tokens.
    """
    if not raw:
        return None
    th = _hash(raw)
    rec = await db.auth_tokens.find_one(
        {"token_hash": th, "purpose": purpose}, {"_id": 0}
    )
    if not rec or rec.get("used"):
        return None
    try:
        expires_at = datetime.fromisoformat(rec["expires_at"])
    except (KeyError, ValueError):
        return None
    if expires_at < _now():
        return None
    await db.auth_tokens.update_one(
        {"token_hash": th, "purpose": purpose},
        {"$set": {"used": True, "used_at": _iso(_now())}},
    )
    return rec


async def ensure_auth_token_indexes(db) -> None:
    await db.auth_tokens.create_index([("token_hash", 1)])
    await db.auth_tokens.create_index([("user_id", 1)])
    await db.auth_tokens.create_index([("expires_at", 1)])
