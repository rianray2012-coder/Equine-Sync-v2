"""routes/audit.py — Phase 5D audit log read API.

`GET /api/audit-logs` — admin/barn_manager only, **barn-scoped**, paginated +
filtered. Read-only: the `audit_log` collection stays append-only (no write or
delete here). Each request records exactly one `audit_logs.view` event — no
recursion, because audit writes are *inserts*, never reads.

Authorization is checked **inline** (not via `core.permissions.require()`) so a
denied read emits exactly one `audit_logs.view(denied)` event rather than a
separate `permission.denied`.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from core.permissions import has_capability, _DENY_MESSAGES
from core.tenancy import barn_filter
from core import audit

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200


def build_router(*, db, get_current_user) -> APIRouter:
    router = APIRouter(tags=["audit"])

    @router.get("/audit-logs")
    async def list_audit_logs(
        request: Request,
        action: Optional[str] = None,
        outcome: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 50,
        offset: int = Query(0, ge=0),
        user=Depends(get_current_user),
    ):
        # Hard-cap the page size (clamp, never error); offset rejects negatives.
        limit = min(max(limit, 1), _MAX_LIMIT)
        # Echoed filter set for the success audit event. Intentionally excludes
        # actor_email — no raw emails in audit metadata.
        echoed = {
            "action": action, "actor_user_id": actor_user_id,
            "resource_type": resource_type, "resource_id": resource_id,
            "outcome": outcome, "from_ts": start, "to_ts": end,
        }
        echoed = {k: v for k, v in echoed.items() if v is not None}

        # Inline authz so a denied read writes exactly one audit_logs.view(denied).
        if not has_capability(user, "audit:read"):
            await audit.record(
                action="audit_logs.view", user=user, request=request,
                resource_type="audit_log", outcome="denied", status_code=403,
                metadata={"reason": "insufficient_role"},
            )
            raise HTTPException(403, _DENY_MESSAGES["audit:read"])

        # Build the query from allow-listed, typed params only (no NoSQL injection).
        q: Dict[str, Any] = {}
        if action is not None:
            q["action"] = action
        if outcome is not None:
            q["outcome"] = outcome
        if actor_user_id is not None:
            q["actor_user_id"] = actor_user_id
        if actor_email is not None:
            q["actor_email"] = actor_email.lower()
        if resource_type is not None:
            q["resource_type"] = resource_type
        if resource_id is not None:
            q["resource_id"] = resource_id
        ts: Dict[str, str] = {}
        if start is not None:
            ts["$gte"] = start
        if end is not None:
            ts["$lte"] = end
        if ts:
            q["ts"] = ts

        # barn_filter forces barn_id last — caller can never escape their barn.
        scoped = barn_filter(user, q)
        total = await db.audit_log.count_documents(scoped)
        items = await (
            db.audit_log.find(scoped, {"_id": 0})
            .sort("ts", -1).skip(offset).limit(limit).to_list(length=limit)
        )

        await audit.record(
            action="audit_logs.view", user=user, request=request,
            resource_type="audit_log", outcome="success", status_code=200,
            metadata={"filters": echoed, "result_count": len(items), "total": total},
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    return router
