"""routes/admin.py — Admin / system maintenance routes.

Extracted from server.py (Phase 3B). Houses the destructive, 2E-hardened
seed route and the admin tenant-reset. Co-locating the seed authorization
logic here keeps the destructive surface auditable in one place.

Seed protections preserved verbatim (Security Patch 2E):
  - Always blocked in production (404), even with ALLOW_SEED_ROUTE=true.
  - Outside production: disabled by default (404); when enabled requires an
    authenticated admin + explicit {"confirm": "SEED"} body.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from core.config import is_production, allow_seed_route, evaluate_seed_access
from core.permissions import require
from core.tenancy import resolve_barn_id
from core import audit

_security = HTTPBearer(auto_error=False)


class SeedBody(BaseModel):
    confirm: Optional[str] = None


class TenantResetBody(BaseModel):
    scope: str = "onboarding"  # 'onboarding' | 'all_setup_data'
    confirm: str  # must equal "RESET"


def build_router(*, db, get_current_user, track, run_seed) -> APIRouter:
    """Factory.

    - ``get_current_user``: server's JWT dependency callable (also called
      directly with explicit creds inside the seed route).
    - ``track``: internal analytics recorder (``_track``) used by tenant-reset.
    - ``run_seed``: ``seed_data.run_seed`` coroutine (db-bound at call time).
    """
    router = APIRouter(tags=["admin"])

    @router.post("/seed")
    async def seed_route(
        body: Optional[SeedBody] = None,
        request: Request = None,
        creds: Optional[HTTPAuthorizationCredentials] = Depends(_security),
    ):
        """Destructive wipe-and-reseed of demo data (Security Patch 2E hardened)."""
        role = None
        user = None
        if creds is not None:
            try:
                user = await get_current_user(creds)
                role = user.get("role")
            except HTTPException:
                role = None  # invalid/expired token → treat as non-admin
        confirm_ok = bool(body and body.confirm == "SEED")
        allowed, code, detail = evaluate_seed_access(
            is_prod=is_production(),
            allow_route=allow_seed_route(),
            authenticated=creds is not None,
            role=role,
            confirm_ok=confirm_ok,
        )
        await audit.record(
            action="admin.seed.attempt", request=request, user=user, actor_role=role,
            resource_type="system", resource_id="seed",
            outcome=("success" if allowed else "denied"),
            status_code=(200 if allowed else code),
            metadata={"is_production": is_production(), "role": role,
                      "confirm_ok": confirm_ok, "code": code},
        )
        if not allowed:
            raise HTTPException(status_code=code, detail=detail)
        return await run_seed(db)

    @router.post("/admin/tenant-reset")
    async def tenant_reset(body: TenantResetBody, request: Request,
                            user=Depends(get_current_user)):
        require(user, "admin:access")
        if body.confirm != "RESET":
            raise HTTPException(400, "Confirmation token required (send confirm=\"RESET\")")
        cleared: Dict[str, int] = {}
        if body.scope == "onboarding":
            r = await db.onboarding_progress.delete_many({})
            cleared["onboarding_progress"] = r.deleted_count
        elif body.scope == "all_setup_data":
            for c in ["onboarding_progress", "barn", "locations", "feed_templates",
                      "inventory", "recurring_schedules", "staff_invites", "invites"]:
                r = await db[c].delete_many({})
                cleared[c] = r.deleted_count
        else:
            raise HTTPException(400, "Unknown scope")
        await track("tenant.reset", {"scope": body.scope, "cleared": cleared}, user["id"])
        await audit.record(
            action="admin.tenant_reset", request=request, user=user,
            resource_type="barn", resource_id=resolve_barn_id(user),
            metadata={"scope": body.scope, "cleared": cleared},
        )
        return {"ok": True, "cleared": cleared}

    return router
