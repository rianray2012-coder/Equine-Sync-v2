"""Account-level brute-force lockout (Phase 2D).

Tracks failed login attempts per account email in the ``login_attempts``
collection. After ``max_attempts`` failures within ``window_minutes``, the
account is locked for ``lockout_minutes``. A **successful login clears** the
record.

Existing/demo/admin users are never locked out under normal use: a successful
login immediately clears their counter, and the default threshold (5) sits
comfortably above incidental single failures.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse(s) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


async def check_lockout(db, email: str) -> Optional[int]:
    """Return remaining lockout seconds if the account is locked, else None."""
    doc = await db.login_attempts.find_one({"email": email.lower()}, {"_id": 0})
    if not doc:
        return None
    locked_until = _parse(doc.get("locked_until"))
    if locked_until and locked_until > _now():
        return int((locked_until - _now()).total_seconds())
    return None


async def record_failure(
    db,
    email: str,
    *,
    max_attempts: int,
    window_minutes: int,
    lockout_minutes: int,
    ip: Optional[str] = None,
) -> dict:
    """Record a failed login. Locks the account once the threshold is reached."""
    email = email.lower()
    now = _now()
    doc = await db.login_attempts.find_one({"email": email}, {"_id": 0})
    first = _parse(doc.get("first_failed_at")) if doc else None
    count = doc.get("count", 0) if doc else 0
    # Reset the counting window if the first failure is older than the window.
    if not first or (now - first) > timedelta(minutes=window_minutes):
        count = 0
        first = now
    count += 1
    update = {
        "email": email,
        "count": count,
        "first_failed_at": _iso(first),
        "last_failed_at": _iso(now),
        "last_ip": ip,
    }
    if count >= max_attempts:
        update["locked_until"] = _iso(now + timedelta(minutes=lockout_minutes))
    await db.login_attempts.update_one({"email": email}, {"$set": update}, upsert=True)
    return update


async def clear_attempts(db, email: str) -> None:
    """Clear all recorded failures for an account (called on successful login)."""
    await db.login_attempts.delete_one({"email": email.lower()})


async def ensure_login_attempt_indexes(db) -> None:
    await db.login_attempts.create_index([("email", 1)], unique=True)
