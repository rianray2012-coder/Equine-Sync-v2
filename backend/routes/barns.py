"""routes/barns.py — Phase 4D multi-barn provisioning.

The founder/platform admin (a user in ``barn_id="primary"``) can create a new
barn together with its first admin. Membership in any barn is otherwise gained
via invite (routes/invites.py). One barn per user; no switching/multi-membership
(deferred). Gated by the ``barn:create`` capability AND a founder-barn check so
a newly-provisioned barn admin cannot spawn further barns until a real
``superadmin`` role exists.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr

from core.permissions import require
from core.tenancy import PRIMARY_BARN_ID, resolve_barn_id
from core import audit


class BarnCreate(BaseModel):
    name: str
    facility_type: Optional[str] = "boarding"
    admin_email: EmailStr
    admin_full_name: str
    admin_password: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_router(*, db, get_current_user, hash_pwd, user_safe, new_id,
                 onboarding_steps: List[dict]) -> APIRouter:
    router = APIRouter(prefix="/barns", tags=["barns"])

    @router.post("")
    async def create_barn(body: BarnCreate, request: Request, user=Depends(get_current_user)):
        require(user, "barn:create")
        # Founder-only for now: only the primary barn can provision new barns.
        if resolve_barn_id(user) != PRIMARY_BARN_ID:
            raise HTTPException(403, "Only the founder barn can create new barns")
        if len(body.admin_password) < 8:
            raise HTTPException(400, "Password must be at least 8 characters")
        email_l = body.admin_email.lower()
        if await db.users.find_one({"email": email_l}):
            raise HTTPException(409, "A user with this email already exists")

        barn_id = new_id()
        barn_doc = {
            "id": barn_id,
            "name": body.name,
            "facility_type": body.facility_type or "boarding",
            "disciplines": [], "address": "", "timezone": "America/New_York",
            "contact_email": "", "contact_phone": "", "logo_url": "", "banner_url": "",
            "created_by": user["id"],
            "created_at": _now_iso(),
        }
        await db.barn.insert_one(barn_doc)

        admin_user = {
            "id": new_id(),
            "email": email_l,
            "full_name": body.admin_full_name,
            "role": "admin",
            "barn_id": barn_id,
            "password_hash": hash_pwd(body.admin_password),
            "email_verified": True,
            "created_at": _now_iso(),
            "provisioned_by": user["id"],
        }
        await db.users.insert_one(admin_user)

        progress = {
            "user_id": admin_user["id"],
            "barn_id": barn_id,
            "steps": {s["id"]: "pending" for s in onboarding_steps},
            "current_step": onboarding_steps[0]["id"],
            "data": {},
            "completed": False,
            "auto_launch": True,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        await db.onboarding_progress.insert_one(progress)

        await audit.record(
            action="barn.created", request=request, user=user,
            resource_type="barn", resource_id=barn_id,
            metadata={"name": body.name,
                      "facility_type": barn_doc["facility_type"],
                      "new_admin_user_id": admin_user["id"]},
        )

        return {
            "barn": {k: v for k, v in barn_doc.items() if k != "_id"},
            "admin": user_safe(admin_user),
        }

    return router
