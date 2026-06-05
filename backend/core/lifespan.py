"""Application lifecycle: startup bootstrap + background loops (Phase 3G).

Relocated verbatim from ``server.py`` during the app-assembly refactor. All
behavior — auto-seed policy (Security Patch 2E), Task Engine bootstrap, index
ensures, the email_verified backfill, demo-template seed, the rolling
materializer, the notification dispatcher, the owner daily-digest + weekly-recap
schedulers, and the auto-nudge loop — is preserved exactly, including every
``DISABLE_*`` flag, env-driven timing, and warm-up delay.

The only non-local dependency is ``send_nudges`` (derived from the reports
router that is assembled in ``server.py``); it is injected via
``register_lifecycle`` rather than imported, so this module never imports from
``server.py``.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone

from core.config import auto_seed_enabled
from core.db import client, db
from core.analytics import _track
from seed_data import run_seed
from task_engine import TaskEngine, seed_demo_templates
from auth_security import ensure_refresh_indexes
from notifications import (
    start_dispatcher as start_notification_dispatcher,
    ensure_indexes as ensure_notification_indexes,
)
from core.auth_tokens import ensure_auth_token_indexes
from mailer import send as send_email, render as render_email
from owner_digest import (
    run_daily_digest_pass,
    ensure_digest_indexes,
    run_weekly_recap_pass,
)

logger = logging.getLogger(__name__)

PRIMARY_BARN_ID = "primary"

# Phase 4A: domain collections that gain a canonical `barn_id`.
# Phase 4B-7 extends this to the task-engine + `media` collections (previously
# excluded): they keep `tenant_id="default"` as the engine partition, and now
# additionally carry a canonical `barn_id` (the additive backfill below stamps
# legacy docs; the engine/storage write-paths stamp new docs). The user-keyed
# notification collections, the `barn` singleton (keyed by its own `id`), and
# all auth/session/attempt infra remain excluded.
BARN_BACKFILL_COLLECTIONS = [
    "users", "horses", "owners", "riders", "medications", "medication_logs",
    "feed_tasks", "vet_records", "farrier_history", "injuries", "wellness",
    "lessons", "training", "invoices", "messages", "service_requests",
    "incidents", "locations", "feed_templates", "inventory",
    "recurring_schedules", "staff_invites", "invites", "onboarding_progress",
    "events",
    # Phase 4B-7 — task engine + media (tenant_id="default" ≡ barn_id="primary"):
    "tasks", "task_templates", "task_completions", "task_events", "media",
]


async def _backfill_barn_id(db) -> int:
    """Idempotent, additive backfill of barn_id=primary on legacy documents.

    Only touches documents missing the field, so it is safe to re-run on every
    boot (no destructive updates). Returns the total number of docs modified.
    """
    total = 0
    for coll in BARN_BACKFILL_COLLECTIONS:
        res = await db[coll].update_many(
            {"barn_id": {"$exists": False}},
            {"$set": {"barn_id": PRIMARY_BARN_ID}},
        )
        total += res.modified_count
    return total


def register_lifecycle(app, *, send_nudges):
    """Attach startup/shutdown handlers (with background loops) to ``app``.

    ``send_nudges`` is the reports router's nudge sender, injected from the
    app-assembly layer so this module avoids importing ``server.py``.
    """

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
            # Phase 4B-7: backfill barn_id BEFORE any materialization so the new
            # barn-scoped occurrence-dedup check sees legacy (barn_id-less) tasks
            # and never creates duplicate occurrences for the same template slot.
            try:
                barn_filled = await _backfill_barn_id(db)
                if barn_filled:
                    logger.info("Phase 4A/4B-7: backfilled barn_id=primary on %d documents.", barn_filled)
            except Exception:
                logger.exception("barn_id backfill failed")
            # Initial materialization for the 14-day horizon (post-backfill)
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
                    result = await send_nudges(None, "EquineSync Concierge", min_days=3, cooldown_hours=24)
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
