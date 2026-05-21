"""Batch C — Notification dispatcher transient-error retry behaviour.

A transient exception inside `_dispatch_event` must NOT permanently drop the
event. The loop increments `dispatch_attempts` and only marks the event
dispatched-with-error after MAX_DISPATCH_ATTEMPTS.

Uses asyncio.run rather than pytest-asyncio (kept out of the project's
dependency surface) so the test file stays plug-and-play with the existing
sync pytest harness.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

import motor.motor_asyncio
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
import notifications as N  # noqa: E402


def _get_db():
    client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ.get("DB_NAME", "test_database")], client


def _patch(obj, attr, val):
    """Tiny monkeypatch helper that returns a restore-callable."""
    orig = getattr(obj, attr)
    setattr(obj, attr, val)
    return lambda: setattr(obj, attr, orig)


def test_transient_error_retries_until_cap():
    async def run():
        db, client = _get_db()
        restore_attempts = _patch(N, "MAX_DISPATCH_ATTEMPTS", 3)

        ev_id = str(uuid.uuid4())
        await db.task_events.insert_one({
            "id": ev_id,
            "event_type": "task.completed",
            "category": "medication",
            "occurred_at": "2026-02-20T00:00:00+00:00",
        })

        async def boom(_db, _event, _mailer):
            raise RuntimeError("transient — DB hiccup")

        restore_dispatch = _patch(N, "_dispatch_event", boom)

        try:
            n = await N.drain_once(db)
            assert n == 1
            doc = await db.task_events.find_one({"id": ev_id}, {"_id": 0})
            assert doc.get("dispatched_at") is None
            assert doc.get("dispatch_attempts") == 1

            await N.drain_once(db)
            doc = await db.task_events.find_one({"id": ev_id}, {"_id": 0})
            assert doc.get("dispatched_at") is None
            assert doc.get("dispatch_attempts") == 2

            await N.drain_once(db)
            doc = await db.task_events.find_one({"id": ev_id}, {"_id": 0})
            assert doc.get("dispatched_at") is not None
            assert doc.get("dispatched_channels") == ["error"]
            assert doc.get("dispatch_attempts") == 3
        finally:
            await db.task_events.delete_one({"id": ev_id})
            restore_dispatch()
            restore_attempts()
            client.close()

    asyncio.run(run())


def test_transient_error_recovers_on_later_success():
    async def run():
        db, client = _get_db()
        restore_attempts = _patch(N, "MAX_DISPATCH_ATTEMPTS", 5)

        ev_id = str(uuid.uuid4())
        await db.task_events.insert_one({
            "id": ev_id,
            "event_type": "task.completed",
            "category": "feed",
            "occurred_at": "2026-02-20T00:00:00+00:00",
        })

        call = {"n": 0}

        async def flaky(_db, event, _mailer):
            call["n"] += 1
            if call["n"] < 2:
                raise RuntimeError("transient")
            await _db.task_events.update_one(
                {"id": event["id"]},
                {"$set": {
                    "dispatched_at": N._iso(N._now()),
                    "dispatched_channels": ["inbox"],
                    "recipient_count": 0,
                }},
            )

        restore_dispatch = _patch(N, "_dispatch_event", flaky)

        try:
            await N.drain_once(db)
            doc = await db.task_events.find_one({"id": ev_id}, {"_id": 0})
            assert doc.get("dispatched_at") is None
            assert doc.get("dispatch_attempts") == 1

            await N.drain_once(db)
            doc = await db.task_events.find_one({"id": ev_id}, {"_id": 0})
            assert doc.get("dispatched_at") is not None
            assert "inbox" in (doc.get("dispatched_channels") or [])
            assert "error" not in (doc.get("dispatched_channels") or [])
        finally:
            await db.task_events.delete_one({"id": ev_id})
            restore_dispatch()
            restore_attempts()
            client.close()

    asyncio.run(run())
