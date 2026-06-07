"""cleanup_test_invoices.py — one-off invoice test-data hygiene (Phase 7D-3).

NOT product code and NOT imported by server.py. Removes leftover *test* invoices
that older suites created without teardown (synthetic owner_ids like
`TEST_owner_*`, `owner-test`, `ownerX`, `o`). It is conservative by design:

  * Only touches invoices in barn_id == "primary".
  * Only matches known test owner_id patterns (owner_name is NEVER used):
    owner_id.startswith("TEST_") / "owner-test" / "ownerX", or owner_id == "o".
  * DOUBLE GUARD: never deletes an invoice whose owner_id maps to a real user id
    or a real roster-owner id (so legitimate seed invoices are always preserved).
  * Dry-run by DEFAULT — requires --apply to actually delete.

Usage:
  python -m cleanup_test_invoices            # dry-run: counts + sample, no writes
  python -m cleanup_test_invoices --apply    # delete the matched test invoices
"""
import argparse
import os

import pymongo

TARGET_BARN = "primary"
# Exact synthetic owner_id used by older tests.
_SYNTHETIC_EXACT = {"o"}
# Prefixes that unambiguously denote test-fixture owner_ids.
_SYNTHETIC_PREFIXES = ("TEST_", "owner-test", "ownerX")


def _db():
    return pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _looks_like_test(inv) -> bool:
    # Candidate selection is based on owner_id ONLY (owner_name is ignored).
    oid = str(inv.get("owner_id") or "")
    if oid in _SYNTHETIC_EXACT:
        return True
    return any(oid.startswith(p) for p in _SYNTHETIC_PREFIXES)


def _safe_ids(db) -> set:
    """Real user ids + roster-owner ids — invoices for these are NEVER deleted."""
    users = {u["id"] for u in db.users.find({}, {"_id": 0, "id": 1}) if u.get("id")}
    owners = {o["id"] for o in db.owners.find({}, {"_id": 0, "id": 1}) if o.get("id")}
    return users | owners


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually delete (default: dry-run)")
    args = ap.parse_args()

    db = _db()
    safe = _safe_ids(db)
    invoices = list(db.invoices.find({"barn_id": TARGET_BARN}, {"_id": 0}))

    candidates, guarded = [], 0
    for inv in invoices:
        if not _looks_like_test(inv):
            continue
        if inv.get("owner_id") in safe:  # double guard
            guarded += 1
            continue
        candidates.append(inv)

    total = db.invoices.count_documents({})
    print(f"invoices total={total}  primary={len(invoices)}  "
          f"test-matches-to-delete={len(candidates)}  guarded(real-id)={guarded}")
    print("sample (up to 10):")
    for inv in candidates[:10]:
        print(f"  - id={inv.get('id')}  owner_id={inv.get('owner_id')!r}  "
              f"owner_name={inv.get('owner_name')!r}  status={inv.get('status')}")
    real_in_candidates = sum(1 for c in candidates if c.get("owner_id") in safe)
    print(f"guard check — real user/roster ids inside delete set: {real_in_candidates} (must be 0)")

    if not args.apply:
        print("\nDRY RUN — no changes made. Re-run with --apply to delete.")
        return

    ids = [c["id"] for c in candidates]
    res = db.invoices.delete_many({"id": {"$in": ids}})
    print(f"\nDELETED {res.deleted_count} test invoice(s). remaining total={db.invoices.count_documents({})}")


if __name__ == "__main__":
    main()
