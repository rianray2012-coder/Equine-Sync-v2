"""routes/owner_updates.py — Phase 7A: Owner Update model + lifecycle.

The first concrete primitive of the Owner Trust Layer (see
``docs/OWNER_TRUST_FRAMEWORK.md`` §Approval Workflow / Update Types). An
*Owner Update* is a publishable note authored by barn staff about a specific
horse, with an explicit lifecycle and an internal/owner-facing visibility flag.

Boundary (7A — backend only):
  * Status vocabulary is the FULL enum ``draft | pending_review | published |
    archived`` for forward-compat, but 7A only wires the **non-sensitive**
    lifecycle: ``draft -> published`` and ``published -> archived``.
  * Sensitive-content review gating (``-> pending_review``) is **deferred to 7B**
    and intentionally NOT implemented here.
  * Barn-scoped (Phase-4 isolation) + owner-isolated reads (owners see only their
    own horses' published, owner-facing updates).
  * High-signal lifecycle events emit fail-open Phase-5 audit
    (``owner_update.published`` / ``owner_update.archived``) with minimal,
    non-PII metadata (``{kind, visibility}`` only).

No frontend, no task-engine/billing/onboarding changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core import audit
from core.permissions import has_capability, require
from core.tenancy import barn_filter, stamp_barn

OwnerUpdateKind = Literal["routine", "training", "wellness", "incident", "billing", "recap"]
Visibility = Literal["internal", "owner_facing"]

# Full lifecycle vocabulary (forward-compatible). 7A wires only the
# non-sensitive transitions; `pending_review` exists for 7B.
STATUS_VALUES = ("draft", "pending_review", "published", "archived")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class OwnerUpdateIn(BaseModel):
    horse_id: str
    body: str = Field(min_length=1)
    kind: OwnerUpdateKind = "routine"
    visibility: Visibility = "owner_facing"
    # Stored for forward-compat; 7A does NOT act on it (review gating is 7B).
    sensitive: bool = False


class OwnerUpdatePatch(BaseModel):
    body: Optional[str] = Field(default=None, min_length=1)
    kind: Optional[OwnerUpdateKind] = None
    visibility: Optional[Visibility] = None
    sensitive: Optional[bool] = None


class ReviewChangesIn(BaseModel):
    # Phase 7B: optional reviewer note stored on the update (capped). It is
    # surfaced internally but is NEVER written to the audit trail.
    review_note: Optional[str] = Field(default=None, max_length=500)


def build_router(*, db, get_current_user, list_collection, clean, new_id) -> APIRouter:
    router = APIRouter(tags=["owner-updates"])

    async def _require_horse(user, horse_id: str) -> None:
        # Reuses the Phase 6A contract: a foreign/absent horse id returns the
        # same generic 404 (no existence leak).
        if not await db.horses.find_one(barn_filter(user, {"id": horse_id}), {"_id": 0, "id": 1}):
            raise HTTPException(404, "Horse not found")

    async def _owner_horse_ids(user) -> list[str]:
        horses = await db.horses.find(
            barn_filter(user, {"owner_id": user["id"]}), {"_id": 0, "id": 1},
        ).to_list(500)
        return [h["id"] for h in horses]

    # ---------------- Create (staff) ----------------

    @router.post("/owner-updates")
    async def create_update(body: OwnerUpdateIn, user=Depends(get_current_user)):
        require(user, "owner_update:create")
        await _require_horse(user, body.horse_id)
        now = _iso(_now_utc())
        doc = body.model_dump()
        doc.update({
            "id": new_id(),
            "author_user_id": user["id"],
            "status": "draft",
            "created_at": now,
            "updated_at": now,
            "published_at": None,
            "published_by": None,
            "reviewed_by": None,
            "review_note": None,
            "archived_at": None,
            "archived_by": None,
        })
        stamp_barn(user, doc)
        await db.owner_updates.insert_one(doc)
        return clean(doc)

    # ---------------- List ----------------

    @router.get("/owner-updates")
    async def list_updates(
        horse_id: Optional[str] = None,
        status: Optional[str] = None,
        user=Depends(get_current_user),
    ):
        if user.get("role") == "horse_owner":
            # Owner view: only their own horses' published, owner-facing updates.
            horse_ids = await _owner_horse_ids(user)
            if not horse_ids:
                return []
            if horse_id is not None:
                # narrow to a single owned horse (foreign/unowned -> empty)
                horse_ids = [hid for hid in horse_ids if hid == horse_id]
                if not horse_ids:
                    return []
            extra = {
                "horse_id": {"$in": horse_ids},
                "status": "published",
                "visibility": "owner_facing",
            }
            return await list_collection(
                "owner_updates", barn_filter(user, extra), sort_field="published_at",
            )

        # Staff view: barn-scoped full read (reuses the create capability set in
        # 7A; a dedicated read capability can be split out later if needed).
        if not has_capability(user, "owner_update:create"):
            raise HTTPException(403, "Insufficient role to view owner updates")
        extra: dict = {}
        if horse_id is not None:
            extra["horse_id"] = horse_id
        if status is not None:
            extra["status"] = status
        return await list_collection(
            "owner_updates", barn_filter(user, extra), sort_field="created_at",
        )

    # ---------------- Read one ----------------

    @router.get("/owner-updates/{update_id}")
    async def get_update(update_id: str, user=Depends(get_current_user)):
        doc = await db.owner_updates.find_one(barn_filter(user, {"id": update_id}), {"_id": 0})
        if not doc:
            raise HTTPException(404, "Owner update not found")
        if user.get("role") == "horse_owner":
            owned = await _owner_horse_ids(user)
            if (doc.get("horse_id") not in owned
                    or doc.get("status") != "published"
                    or doc.get("visibility") != "owner_facing"):
                # Generic 404 — never leak the existence of an internal/draft note.
                raise HTTPException(404, "Owner update not found")
            return doc
        if not has_capability(user, "owner_update:create"):
            raise HTTPException(403, "Insufficient role to view owner updates")
        return doc

    # ---------------- Edit (draft only) ----------------

    @router.patch("/owner-updates/{update_id}")
    async def edit_update(update_id: str, body: OwnerUpdatePatch, user=Depends(get_current_user)):
        require(user, "owner_update:create")
        scope = barn_filter(user, {"id": update_id})
        doc = await db.owner_updates.find_one(scope, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Owner update not found")
        if doc["status"] != "draft":
            raise HTTPException(409, "Only draft updates can be edited")
        changes = {k: v for k, v in body.model_dump().items() if v is not None}
        if changes:
            changes["updated_at"] = _iso(_now_utc())
            await db.owner_updates.update_one(scope, {"$set": changes})
        return await db.owner_updates.find_one(scope, {"_id": 0})

    # ---------------- Publish (draft -> published) ----------------

    @router.post("/owner-updates/{update_id}/publish")
    async def publish_update(update_id: str, request: Request, user=Depends(get_current_user)):
        require(user, "owner_update:publish")
        scope = barn_filter(user, {"id": update_id})
        doc = await db.owner_updates.find_one(scope, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Owner update not found")
        if doc["status"] != "draft":
            # 7A only publishes from draft. (Sensitive -> pending_review is 7B.)
            raise HTTPException(409, "Only draft updates can be published")
        if doc.get("sensitive"):
            # 7A guardrail: sensitive updates cannot be published until the 7B
            # review gate exists. Status is unchanged; no publish audit emitted.
            raise HTTPException(409, "Sensitive updates require review")
        now = _iso(_now_utc())
        await db.owner_updates.update_one(scope, {"$set": {
            "status": "published", "published_at": now, "published_by": user["id"], "updated_at": now,
        }})
        await audit.record(
            action="owner_update.published", user=user, request=request,
            resource_type="owner_update", resource_id=update_id,
            metadata={"kind": doc["kind"], "visibility": doc["visibility"]},
        )
        return await db.owner_updates.find_one(scope, {"_id": 0})

    # ---------------- Phase 7B: review workflow ----------------

    @router.post("/owner-updates/{update_id}/submit")
    async def submit_update(update_id: str, request: Request, user=Depends(get_current_user)):
        """draft -> pending_review. Any draft may be submitted; sensitive drafts
        MUST use this path (they cannot be published directly)."""
        require(user, "owner_update:create")
        scope = barn_filter(user, {"id": update_id})
        doc = await db.owner_updates.find_one(scope, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Owner update not found")
        if doc["status"] != "draft":
            raise HTTPException(409, "Only draft updates can be submitted for review")
        now = _iso(_now_utc())
        await db.owner_updates.update_one(scope, {"$set": {
            "status": "pending_review", "updated_at": now,
        }})
        await audit.record(
            action="owner_update.submitted", user=user, request=request,
            resource_type="owner_update", resource_id=update_id,
            metadata={"kind": doc["kind"], "visibility": doc["visibility"]},
        )
        return await db.owner_updates.find_one(scope, {"_id": 0})

    @router.post("/owner-updates/{update_id}/approve")
    async def approve_update(update_id: str, request: Request, user=Depends(get_current_user)):
        """pending_review -> published. Four-eyes: the author of a *sensitive*
        update cannot approve their own submission."""
        require(user, "owner_update:review")
        scope = barn_filter(user, {"id": update_id})
        doc = await db.owner_updates.find_one(scope, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Owner update not found")
        if doc["status"] != "pending_review":
            raise HTTPException(409, "Only updates pending review can be approved")
        if doc.get("sensitive") and doc.get("author_user_id") == user["id"]:
            raise HTTPException(403, "Author cannot approve their own sensitive update")
        now = _iso(_now_utc())
        await db.owner_updates.update_one(scope, {"$set": {
            "status": "published", "published_at": now, "published_by": user["id"],
            "reviewed_by": user["id"], "updated_at": now,
        }})
        await audit.record(
            action="owner_update.approved", user=user, request=request,
            resource_type="owner_update", resource_id=update_id,
            metadata={"kind": doc["kind"], "visibility": doc["visibility"]},
        )
        return await db.owner_updates.find_one(scope, {"_id": 0})

    @router.post("/owner-updates/{update_id}/request-changes")
    async def request_changes(update_id: str, body: ReviewChangesIn, request: Request,
                              user=Depends(get_current_user)):
        """pending_review -> draft, with an optional reviewer note (stored,
        never audited)."""
        require(user, "owner_update:review")
        scope = barn_filter(user, {"id": update_id})
        doc = await db.owner_updates.find_one(scope, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Owner update not found")
        if doc["status"] != "pending_review":
            raise HTTPException(409, "Only updates pending review can be sent back")
        now = _iso(_now_utc())
        note = (body.review_note or "").strip() or None
        await db.owner_updates.update_one(scope, {"$set": {
            "status": "draft", "reviewed_by": user["id"], "review_note": note, "updated_at": now,
        }})
        await audit.record(
            action="owner_update.changes_requested", user=user, request=request,
            resource_type="owner_update", resource_id=update_id,
            metadata={"kind": doc["kind"], "visibility": doc["visibility"]},
        )
        return await db.owner_updates.find_one(scope, {"_id": 0})

    # ---------------- Archive (published -> archived; soft, never deleted) ----------------

    @router.post("/owner-updates/{update_id}/archive")
    async def archive_update(update_id: str, request: Request, user=Depends(get_current_user)):
        require(user, "owner_update:archive")
        scope = barn_filter(user, {"id": update_id})
        doc = await db.owner_updates.find_one(scope, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Owner update not found")
        if doc["status"] != "published":
            raise HTTPException(409, "Only published updates can be archived")
        now = _iso(_now_utc())
        await db.owner_updates.update_one(scope, {"$set": {
            "status": "archived", "archived_at": now, "archived_by": user["id"], "updated_at": now,
        }})
        await audit.record(
            action="owner_update.archived", user=user, request=request,
            resource_type="owner_update", resource_id=update_id,
            metadata={"kind": doc["kind"], "visibility": doc["visibility"]},
        )
        return await db.owner_updates.find_one(scope, {"_id": 0})

    return router
