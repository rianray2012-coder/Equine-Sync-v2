"""routes/dashboard.py — Dashboard summary + deprecated barn-board.

Extracted from server.py (Phase-F). Engine-backed counts derived from
the unified Task Engine, not legacy collections. The /barn-board endpoint
is retained for backward compatibility and emits RFC 8594 deprecation
headers — new callers should use /api/tasks/today directly.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Response

from core.tenancy import barn_filter, resolve_barn_id


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def build_router(db, get_current_user, tenant_id: str) -> APIRouter:
    router = APIRouter(prefix="/dashboard", tags=["dashboard"])

    @router.get("/summary")
    async def dashboard(user=Depends(get_current_user)):
        """Engine-derived dashboard counts. Feed/meds/lesson counts come from
        the unified Task Engine (Phase-A migration, Feb 19 2026).
        """
        today_start = _now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        today_start_iso = today_start.isoformat()
        today_end_iso = today_end.isoformat()

        total_horses = await db.horses.count_documents(barn_filter(user))
        stall_rest = await db.horses.count_documents(barn_filter(user, {"status": {"$in": ["stall_rest", "rehab"]}}))
        active_injuries = await db.injuries.count_documents(barn_filter(user, {"status": {"$in": ["active", "monitoring", "improving"]}}))

        feed_q = {"tenant_id": tenant_id, "barn_id": resolve_barn_id(user), "category": "feed",
                  "scheduled_at": {"$gte": today_start_iso, "$lt": today_end_iso}}
        feed_today_total = await db.tasks.count_documents(feed_q)
        feed_pending = await db.tasks.count_documents({**feed_q, "status": {"$nin": ["completed", "skipped", "cancelled"]}})

        med_q = {"tenant_id": tenant_id, "barn_id": resolve_barn_id(user), "category": "medication",
                 "scheduled_at": {"$gte": today_start_iso, "$lt": today_end_iso}}
        meds_due = await db.tasks.count_documents({**med_q, "status": {"$nin": ["completed", "skipped", "cancelled"]}})
        meds_missed = await db.task_completions.count_documents({
            "tenant_id": tenant_id, "barn_id": resolve_barn_id(user), "voided": {"$ne": True},
            "outcome": {"$in": ["refused", "skipped"]},
            "completed_at": {"$gte": today_start_iso, "$lt": today_end_iso},
        })

        pending_sr = await db.service_requests.count_documents(barn_filter(user, {"status": "pending"}))
        open_incidents = await db.incidents.count_documents(barn_filter(user, {"status": {"$ne": "closed"}}))
        lessons_today = await db.lessons.count_documents(barn_filter(user, {"start_time": {"$regex": f"^{_now_utc().date().isoformat()}"}}))

        overdue_list = await db.invoices.find(
            barn_filter(user, {"status": {"$in": ["open", "overdue"]}}), {"_id": 0, "total": 1},
        ).to_list(1000)
        overdue_invoices = len(overdue_list)
        overdue_amount = sum(i.get("total", 0) for i in overdue_list)

        wellness_list = await db.horses.find(barn_filter(user), {"_id": 0, "wellness_score": 1}).to_list(1000)
        avg_wellness = round(sum(h.get("wellness_score", 0) for h in wellness_list) / max(1, len(wellness_list))) if wellness_list else 0

        return {
            "total_horses": total_horses,
            "feed_pending": feed_pending,
            "feed_today_total": feed_today_total,
            "meds_due": meds_due,
            "meds_missed": meds_missed,
            "stall_rest": stall_rest,
            "active_injuries": active_injuries,
            "overdue_invoices": overdue_invoices,
            "overdue_amount": overdue_amount,
            "pending_service_requests": pending_sr,
            "open_incidents": open_incidents,
            "lessons_today": lessons_today,
            "avg_wellness": avg_wellness,
            "_source": "engine",
        }

    @router.get("/barn-board")
    async def barn_board(response: Response, user=Depends(get_current_user)):
        """DEPRECATED (Phase-A): kept for backward compatibility while callers
        migrate to /tasks/today. Backed by the unified Task Engine.
        """
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = "Wed, 30 Apr 2026 00:00:00 GMT"
        response.headers["Link"] = '</api/tasks/today>; rel="successor-version"'
        today_start = _now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        today_str = _now_utc().date().isoformat()

        feed = await db.tasks.find({
            "tenant_id": tenant_id, "barn_id": resolve_barn_id(user), "category": "feed",
            "scheduled_at": {"$gte": today_start.isoformat(), "$lt": today_end.isoformat()},
        }, {"_id": 0}).sort("scheduled_at", 1).to_list(200)
        meds = await db.tasks.find({
            "tenant_id": tenant_id, "barn_id": resolve_barn_id(user), "category": "medication",
            "scheduled_at": {"$gte": today_start.isoformat(), "$lt": today_end.isoformat()},
        }, {"_id": 0}).sort("scheduled_at", 1).to_list(200)
        lessons = await db.lessons.find(barn_filter(user, {"start_time": {"$regex": f"^{today_str}"}}), {"_id": 0}).to_list(200)
        stall_rest = await db.horses.find(barn_filter(user, {"status": {"$in": ["stall_rest", "rehab"]}}), {"_id": 0}).to_list(100)
        incidents = await db.incidents.find(barn_filter(user), {"_id": 0}).sort("occurred_at", -1).to_list(5)
        return {
            "date": today_str,
            "feed": feed,
            "medications": meds,
            "lessons": lessons,
            "stall_rest": stall_rest,
            "urgent": incidents,
            "_deprecated": "Use /tasks/today; this endpoint will be removed.",
        }

    return router
