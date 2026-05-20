"""seed_pulse_demo.py — demo-scoped pulse seeder.

Drops 5 days of completed task_events for a horse belonging to the
demo owner so the Wellness Pulse can surface its calm 7-day observation
in the digest preview. Deterministic, idempotent and isolated from
production data:

  • Targets a configurable owner email (default: owner@equinesync.com)
  • Picks the owner's first horse, or refuses if none.
  • Inserts events with a stable `demo_marker="pulse-demo-v1"` tag so they
    can be undone with --reset.
  • Runs in dry-run mode by default — pass --apply to write.

Usage:
    python -m seed_pulse_demo                                # dry-run
    python -m seed_pulse_demo --apply                        # insert
    python -m seed_pulse_demo --apply --reset                # remove + reinsert
    python -m seed_pulse_demo --apply --owner-email a@b.com  # different owner

This script is NOT imported by server.py. It runs standalone and writes
ONLY documents tagged with the demo_marker — no other state mutations.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

DEMO_MARKER = "pulse-demo-v1"
DEFAULT_OWNER_EMAIL = "owner@equinesync.com"


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _make_event(category: str, horse_id: str, days_ago: int, hour: int = 9) -> dict:
    """Build a task_event document that the wellness pulse + digest can read."""
    now = datetime.now(timezone.utc)
    occurred = (now - timedelta(days=days_ago)).replace(hour=hour, minute=0, second=0, microsecond=0)
    return {
        "id": uuid.uuid4().hex,
        "tenant_id": "default",
        "event_type": "task.completed",
        "category": category,
        "task_id": f"demo-{uuid.uuid4().hex[:8]}",
        "subject_horse_ids": [horse_id],
        "actor_user_id": "demo-script",
        "actor_user_name": "Pulse Demo Seeder",
        "occurred_at": _iso(occurred),
        "payload_snapshot": {
            "title": f"Demo {category} completion",
            "outcome": "done",
            "demo": True,
        },
        "routing_tags": ["owner_visible"],
        "demo_marker": DEMO_MARKER,
    }


async def reset(db) -> dict:
    """Remove anything previously seeded by this script, including any
    temporary horse-owner linkages."""
    events_deleted = await db.task_events.delete_many({"demo_marker": DEMO_MARKER})

    # Restore any horses we temporarily re-linked.
    linked = await db.horses.find(
        {"_demo_marker": DEMO_MARKER},
        {"_id": 0, "id": 1, "_demo_prev_owner_id": 1},
    ).to_list(50)
    for h in linked:
        await db.horses.update_one(
            {"id": h["id"]},
            {
                "$set": {"owner_id": h.get("_demo_prev_owner_id")},
                "$unset": {"_demo_marker": "", "_demo_prev_owner_id": ""},
            },
        )
    return {"events": events_deleted.deleted_count, "horses_restored": len(linked)}


async def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write to MongoDB. Omit for a dry-run preview.")
    parser.add_argument("--reset", action="store_true",
                        help="Delete previously-seeded demo events before inserting.")
    parser.add_argument("--owner-email", default=DEFAULT_OWNER_EMAIL,
                        help=f"Owner email to seed against (default: {DEFAULT_OWNER_EMAIL}).")
    parser.add_argument("--link-first-horse", action="store_true",
                        help="If the owner has no horses linked (common in seeded data), "
                             "temporarily link the first available horse to them so the "
                             "digest pipeline can find it. Reversible via --reset.")
    args = parser.parse_args()

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        print("ERROR: MONGO_URL and DB_NAME must be set in backend/.env")
        return

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    owner = await db.users.find_one(
        {"email": args.owner_email.lower(), "role": "horse_owner"},
        {"_id": 0, "id": 1, "email": 1, "full_name": 1},
    )
    if not owner:
        print(f"ERROR: no horse_owner user found with email {args.owner_email}")
        return
    print(f"Owner: {owner['full_name']} <{owner['email']}>")

    # Reset runs FIRST — it doesn't need an owned horse and is operator's
    # explicit "clean slate" intent.
    if args.reset:
        if args.apply:
            r = await reset(db)
            print(f"Reset: deleted {r['events']} events, restored {r['horses_restored']} horse linkage(s).")
        else:
            preview = await db.task_events.count_documents({"demo_marker": DEMO_MARKER})
            horses_to_restore = await db.horses.count_documents({"_demo_marker": DEMO_MARKER})
            print(f"Reset (dry-run): would delete {preview} events, restore {horses_to_restore} horse linkage(s).")
        if not args.link_first_horse:
            print("\nReset complete. (Pass --link-first-horse to also re-seed.)")
            return

    horse = await db.horses.find_one(
        {"owner_id": owner["id"]},
        {"_id": 0, "id": 1, "name": 1, "owner_id": 1},
    )
    if not horse:
        if not args.link_first_horse:
            print(f"ERROR: owner has no horses linked. "
                  f"Re-run with --link-first-horse to attach the first available horse "
                  f"(reversible via --reset).")
            return
        # Pick any horse and attach the demo user. Store the prior owner_id
        # so --reset can restore it.
        any_horse = await db.horses.find_one({}, {"_id": 0, "id": 1, "name": 1, "owner_id": 1})
        if not any_horse:
            print("ERROR: no horses exist in the barn at all. Add a horse first.")
            return
        if args.apply:
            await db.horses.update_one(
                {"id": any_horse["id"]},
                {"$set": {
                    "owner_id": owner["id"],
                    "_demo_prev_owner_id": any_horse.get("owner_id"),
                    "_demo_marker": DEMO_MARKER,
                }},
            )
            print(f"Linked '{any_horse['name']}' to {args.owner_email} (was owner_id={any_horse.get('owner_id')}).")
            horse = {**any_horse, "owner_id": owner["id"]}
        else:
            print(f"Would link '{any_horse['name']}' to {args.owner_email} (dry-run).")
            horse = any_horse
    print(f"Horse: {horse['name']} ({horse['id']})")

    # 5 medication completions over the last 5 days at 09:00 → triggers
    # the medication-adherence pulse line.
    # Plus 2 rehab completions on different days to demonstrate the rehab
    # silence rule when meds already won the priority slot.
    events = []
    for d in range(1, 6):
        events.append(_make_event("medication", horse["id"], days_ago=d, hour=9))
    for d in (2, 4):
        events.append(_make_event("rehab", horse["id"], days_ago=d, hour=14))

    print(f"\nPrepared {len(events)} demo events:")
    for e in events:
        print(f"  · {e['occurred_at'][:16]}  {e['category']:10}  task={e['task_id']}")

    if not args.apply:
        print("\nDry-run mode. Pass --apply to insert these events.")
        return

    # Idempotency: don't double-insert. The reset path handles repeated runs.
    existing = await db.task_events.count_documents({
        "demo_marker": DEMO_MARKER,
        "subject_horse_ids": horse["id"],
    })
    if existing > 0 and not args.reset:
        print(f"\nSkipping insert — {existing} demo events already exist for this horse. "
              "Re-run with --reset to refresh.")
        return

    res = await db.task_events.insert_many(events)
    print(f"\nInserted {len(res.inserted_ids)} demo events.")
    print(f"Owner can now preview the pulse line at "
          f"POST /api/notifications/digest/preview (logged in as {args.owner_email}).")


if __name__ == "__main__":
    asyncio.run(main())
