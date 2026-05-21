"""
Notification dispatcher.

Phase 1 design (per /app/memory/TASK_ENGINE_ARCHITECTURE.md §5):
- TaskEvent rows are written by the engine inside the completion transaction.
- A polling loop in this module picks up un-dispatched events and fans them
  out to registered channel handlers (in-app inbox, email; push deferred).
- Per-user `notification_preferences` document gates each channel × category.
- Marks each event row with `dispatched_at` so we never double-send.

When MongoDB change streams become available (replica set), swap the poll
for `db.task_events.watch()` without touching the route layer.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = int(os.environ.get("NOTIFY_POLL_SECONDS", "10"))
BATCH_SIZE = int(os.environ.get("NOTIFY_BATCH_SIZE", "50"))
MAX_DISPATCH_ATTEMPTS = int(os.environ.get("NOTIFY_MAX_ATTEMPTS", "3"))

# Defaults: which event_type × category should ship by channel, when a user
# has no explicit preferences saved.
DEFAULT_INBOX_RULES = {
    # event_type -> set of categories (or "*" for all)
    "task.completed": {"medication", "farrier", "vet", "rehab"},
    "task.skipped":   {"medication", "vet"},
    "task.voided":    {"medication", "vet"},
}
DEFAULT_EMAIL_RULES = {
    # email is intentionally narrower to avoid noise
    "task.skipped":   {"medication"},
    "task.voided":    {"medication"},
}


# ---------- Pydantic models ----------

class NotificationPrefsIn(BaseModel):
    inbox_enabled: bool = True
    email_enabled: bool = True
    push_enabled: bool = False
    digest_enabled: bool = True  # owner-only; ignored for non-owner accounts
    # event_type -> categories list ([] = none, ["*"] = all)
    inbox_rules: dict | None = None
    email_rules: dict | None = None


# ---------- helpers ----------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _new_id() -> str:
    import uuid
    return str(uuid.uuid4())


def _rule_matches(rules: dict | None, event_type: str, category: Optional[str]) -> bool:
    if not rules:
        return False
    cats = rules.get(event_type)
    if cats is None:
        return False
    if cats == "*" or "*" in cats:
        return True
    return bool(category and category in cats)


async def _get_user_prefs(db, user_id: str) -> dict:
    rec = await db.notification_preferences.find_one({"user_id": user_id}, {"_id": 0})
    defaults = {
        "user_id": user_id,
        "inbox_enabled": True,
        "email_enabled": True,
        "push_enabled": False,
        "digest_enabled": True,
        "inbox_rules": DEFAULT_INBOX_RULES,
        "email_rules": DEFAULT_EMAIL_RULES,
    }
    if rec:
        # Merge in any new defaults that were added after this row was first saved.
        for k, v in defaults.items():
            rec.setdefault(k, v)
        return rec
    return defaults


# ---------- channel handlers ----------

async def _deliver_inbox(db, recipient_user_id: str, event: dict):
    """Append to per-user inbox."""
    doc = {
        "id": _new_id(),
        "user_id": recipient_user_id,
        "event_id": event["id"],
        "event_type": event.get("event_type"),
        "category": event.get("category"),
        "title": (event.get("payload_snapshot") or {}).get("title") or event.get("event_type"),
        "summary": _summarize(event),
        "task_id": event.get("task_id"),
        "subject_horse_ids": event.get("subject_horse_ids", []),
        "occurred_at": event.get("occurred_at"),
        "read_at": None,
        "created_at": _iso(_now()),
    }
    await db.notifications.insert_one(doc)


def _summarize(event: dict) -> str:
    snap = event.get("payload_snapshot") or {}
    title = snap.get("title") or event.get("event_type")
    et = event.get("event_type")
    outcome = snap.get("outcome")
    if et == "task.completed":
        return f"{title} marked done"
    if et == "task.skipped":
        if outcome == "refused":
            return f"{title} — horse refused"
        return f"{title} skipped"
    if et == "task.voided":
        return f"Completion of {title} reverted"
    if et == "task.created":
        return f"{title} scheduled"
    if et == "task.reassigned":
        return f"{title} reassigned"
    return title


async def _deliver_email(db, recipient_user_id: str, event: dict, mailer):
    """Send an email digest entry (very lightweight in P1)."""
    if mailer is None:
        return
    user = await db.users.find_one({"id": recipient_user_id}, {"_id": 0, "email": 1, "full_name": 1})
    if not user:
        return
    try:
        subject = f"EquineSync · {_summarize(event)}"
        body_text = f"Hi {user.get('full_name','there')},\n\n{_summarize(event)}\n\n— EquineSync"
        # Use the existing render+send pipeline; fall back to plain text body.
        mailer["send"](
            to=user["email"],
            subject=subject,
            html=f"<p>Hi {user.get('full_name','there')},</p><p>{_summarize(event)}</p><p>— EquineSync</p>",
            text=body_text,
        )
    except Exception:
        logger.exception("notification email failed for user=%s", recipient_user_id)


# ---------- core dispatch ----------

async def _candidate_recipients(db, event: dict) -> list[str]:
    """Resolve who should receive an event.

    Phase 1 single-tenant heuristics:
    - The actor (if present) gets no self-notification.
    - All non-actor admins/barn_managers receive inbox events by default.
    - Horse owners receive curated events only (filtered by category match).
    """
    actor = event.get("actor_user_id")
    recipients = set()
    # Staff/admins
    staff = await db.users.find(
        {"role": {"$in": ["admin", "barn_manager"]}}, {"_id": 0, "id": 1},
    ).to_list(100)
    for u in staff:
        recipients.add(u["id"])
    # Horse owners whose horses are subjects of this event — curated categories only
    subjects = event.get("subject_horse_ids") or []
    if subjects and event.get("category") in {"medication", "farrier", "vet", "rehab", "feed"}:
        horses = await db.horses.find(
            {"id": {"$in": subjects}}, {"_id": 0, "owner_id": 1},
        ).to_list(200)
        owner_ids = [h.get("owner_id") for h in horses if h.get("owner_id")]
        if owner_ids:
            owner_users = await db.users.find(
                {"id": {"$in": owner_ids}, "role": "horse_owner"},
                {"_id": 0, "id": 1},
            ).to_list(200)
            for u in owner_users:
                recipients.add(u["id"])
    recipients.discard(actor)
    return list(recipients)


async def _dispatch_event(db, event: dict, mailer):
    recipients = await _candidate_recipients(db, event)
    channels_used = []
    for uid in recipients:
        prefs = await _get_user_prefs(db, uid)
        cat = event.get("category")
        et = event.get("event_type")
        inbox_ok = prefs.get("inbox_enabled") and _rule_matches(
            prefs.get("inbox_rules"), et, cat,
        )
        email_ok = prefs.get("email_enabled") and _rule_matches(
            prefs.get("email_rules"), et, cat,
        )
        if inbox_ok:
            await _deliver_inbox(db, uid, event)
            channels_used.append("inbox")
        if email_ok:
            await _deliver_email(db, uid, event, mailer)
            channels_used.append("email")
    await db.task_events.update_one(
        {"id": event["id"]},
        {"$set": {
            "dispatched_at": _iso(_now()),
            "dispatched_channels": list(set(channels_used)),
            "recipient_count": len(recipients),
        }},
    )


async def drain_once(db, mailer=None) -> int:
    """One pass: dispatch up to BATCH_SIZE undispatched events. Returns count.

    Transient-error tolerance (Batch C, Feb 2026): events that raise during
    dispatch are retried up to MAX_DISPATCH_ATTEMPTS times across polling
    cycles. Only after the cap do we mark them dispatched-with-error, so a
    momentary DB hiccup or email-provider blip no longer permanently drops
    an in-app notification.
    """
    cursor = db.task_events.find(
        {"dispatched_at": {"$exists": False}},
        {"_id": 0},
    ).sort("occurred_at", 1).limit(BATCH_SIZE)
    events = await cursor.to_list(BATCH_SIZE)
    for ev in events:
        try:
            await _dispatch_event(db, ev, mailer)
        except Exception:
            attempts = int(ev.get("dispatch_attempts") or 0) + 1
            logger.exception(
                "Notification dispatch failed for event=%s (attempt %d/%d)",
                ev.get("id"), attempts, MAX_DISPATCH_ATTEMPTS,
            )
            if attempts >= MAX_DISPATCH_ATTEMPTS:
                # Cap reached — finalise so we don't loop forever.
                await db.task_events.update_one(
                    {"id": ev["id"]},
                    {"$set": {
                        "dispatched_at": _iso(_now()),
                        "dispatched_channels": ["error"],
                        "dispatch_attempts": attempts,
                    }},
                )
            else:
                # Leave dispatched_at unset so the next poll picks it up again.
                await db.task_events.update_one(
                    {"id": ev["id"]},
                    {"$set": {
                        "dispatch_attempts": attempts,
                        "last_attempt_at": _iso(_now()),
                    }},
                )
    return len(events)


async def start_dispatcher(db, mailer=None):
    """Background loop. Cancelable via task cancellation."""
    await ensure_indexes(db)
    await asyncio.sleep(8)  # let server settle after startup
    while True:
        try:
            n = await drain_once(db, mailer)
            if n:
                logger.info("Notifications: dispatched %d events", n)
        except Exception:
            logger.exception("Notification loop failed")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def ensure_indexes(db):
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.notifications.create_index([("user_id", 1), ("read_at", 1)])
    await db.notification_preferences.create_index([("user_id", 1)], unique=True)


# ---------- router ----------

def build_router(db, get_current_user) -> APIRouter:
    router = APIRouter()

    @router.get("/notifications")
    async def list_notifications(user=Depends(get_current_user),
                                  unread_only: bool = False, limit: int = 50):
        q = {"user_id": user["id"]}
        if unread_only:
            q["read_at"] = None
        items = await db.notifications.find(q, {"_id": 0}).sort("created_at", -1).limit(min(limit, 200)).to_list(min(limit, 200))
        unread = await db.notifications.count_documents({"user_id": user["id"], "read_at": None})
        return {"items": items, "unread": unread}

    @router.post("/notifications/{notif_id}/read")
    async def mark_read(notif_id: str, user=Depends(get_current_user)):
        r = await db.notifications.update_one(
            {"id": notif_id, "user_id": user["id"]},
            {"$set": {"read_at": _iso(_now())}},
        )
        if r.matched_count == 0:
            raise HTTPException(404, "Notification not found")
        return {"ok": True}

    @router.post("/notifications/read-all")
    async def mark_all_read(user=Depends(get_current_user)):
        await db.notifications.update_many(
            {"user_id": user["id"], "read_at": None},
            {"$set": {"read_at": _iso(_now())}},
        )
        return {"ok": True}

    @router.get("/notifications/preferences")
    async def get_prefs(user=Depends(get_current_user)):
        return await _get_user_prefs(db, user["id"])

    @router.put("/notifications/preferences")
    async def put_prefs(body: NotificationPrefsIn, user=Depends(get_current_user)):
        doc = body.model_dump(exclude_unset=True)
        doc["user_id"] = user["id"]
        doc["updated_at"] = _iso(_now())
        # Fill any missing fields with defaults so the doc is complete.
        existing = await _get_user_prefs(db, user["id"])
        for key in ("inbox_enabled", "email_enabled", "push_enabled",
                     "digest_enabled", "inbox_rules", "email_rules"):
            doc.setdefault(key, existing.get(key))
        await db.notification_preferences.update_one(
            {"user_id": user["id"]}, {"$set": doc}, upsert=True,
        )
        return doc

    @router.post("/notifications/drain")
    async def manual_drain(user=Depends(get_current_user)):
        if user.get("role") not in ("admin", "barn_manager"):
            raise HTTPException(403, "Admin/Manager only")
        n = await drain_once(db)
        return {"drained": n}

    return router
