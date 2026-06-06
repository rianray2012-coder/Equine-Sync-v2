"""seed_owner_demo_link.py — one-off, REVERSIBLE demo-data helper (Phase 7C-1).

NOT product code and NOT imported by server.py. Links a single demo horse to the
`owner@equinesync.com` user account (so the owner-facing Updates feed renders real
data during manual verification) and seeds one published, owner-facing Owner Update.

Every write is marker-tagged so cleanup never touches other documents, and the
horse's ORIGINAL owner_id is preserved for exact restoration.

Usage:
  python -m seed_owner_demo_link            # dry-run preview
  python -m seed_owner_demo_link --apply    # link horse + seed one published update
  python -m seed_owner_demo_link --reset    # restore original owner_id + remove the update
"""
import argparse
import asyncio
import os
import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

MARKER = "owner-demo-link-7c1"
OWNER_EMAIL = "owner@equinesync.com"


def _db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]]


def _iso():
    return datetime.now(timezone.utc).isoformat()


async def _apply(db):
    owner = await db.users.find_one({"email": OWNER_EMAIL}, {"_id": 0, "id": 1})
    if not owner:
        print(f"! owner user {OWNER_EMAIL} not found — is the demo seed present?")
        return
    owner_id = owner["id"]

    # Already linked? idempotent.
    existing = await db.horses.find_one({"_demo_owner_link": MARKER}, {"_id": 0, "id": 1, "name": 1})
    if existing:
        print(f"= already linked: horse {existing['name']} ({existing['id']})")
    else:
        horse = await db.horses.find_one({"barn_id": "primary"}, {"_id": 0, "id": 1, "name": 1, "owner_id": 1})
        if not horse:
            print("! no primary-barn horse found")
            return
        await db.horses.update_one(
            {"id": horse["id"]},
            {"$set": {"owner_id": owner_id, "_demo_owner_link": MARKER,
                      "_demo_prev_owner_id": horse.get("owner_id")}},
        )
        existing = horse
        print(f"+ linked horse {horse['name']} ({horse['id']}) -> owner {owner_id} "
              f"(prev owner_id={horse.get('owner_id')})")

    # Seed one published, owner-facing update (idempotent on marker).
    if await db.owner_updates.find_one({"_demo_marker": MARKER}, {"_id": 0, "id": 1}):
        print("= demo owner_update already present")
    else:
        uid = str(uuid.uuid4())
        now = _iso()
        await db.owner_updates.insert_one({
            "id": uid, "barn_id": "primary", "horse_id": existing["id"],
            "author_user_id": "demo", "kind": "routine", "visibility": "owner_facing",
            "sensitive": False, "status": "published",
            "body": "Today's care routine was completed as scheduled. "
                    "Bright, eating well, and turned out with the group — no concerns noted.",
            "created_at": now, "updated_at": now, "published_at": now, "published_by": "demo",
            "reviewed_by": None, "review_note": None, "archived_at": None, "archived_by": None,
            "_demo_marker": MARKER,
        })
        print(f"+ seeded published owner_update {uid}")


async def _reset(db):
    horse = await db.horses.find_one({"_demo_owner_link": MARKER}, {"_id": 0, "id": 1, "name": 1, "_demo_prev_owner_id": 1})
    if horse:
        await db.horses.update_one(
            {"id": horse["id"]},
            {"$set": {"owner_id": horse.get("_demo_prev_owner_id")},
             "$unset": {"_demo_owner_link": "", "_demo_prev_owner_id": ""}},
        )
        print(f"- restored horse {horse['name']} ({horse['id']}) owner_id -> {horse.get('_demo_prev_owner_id')}")
    res = await db.owner_updates.delete_many({"_demo_marker": MARKER})
    print(f"- removed {res.deleted_count} demo owner_update(s)")


async def _preview(db):
    owner = await db.users.find_one({"email": OWNER_EMAIL}, {"_id": 0, "id": 1})
    horse = await db.horses.find_one({"_demo_owner_link": MARKER}, {"_id": 0, "id": 1, "name": 1})
    n = await db.owner_updates.count_documents({"_demo_marker": MARKER})
    print(f"owner: {owner['id'] if owner else 'MISSING'}")
    print(f"linked horse: {horse if horse else 'none'}")
    print(f"demo updates: {n}")
    print("(dry run — pass --apply or --reset)")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    db = _db()
    if args.reset:
        await _reset(db)
    elif args.apply:
        await _apply(db)
    else:
        await _preview(db)


if __name__ == "__main__":
    asyncio.run(main())
