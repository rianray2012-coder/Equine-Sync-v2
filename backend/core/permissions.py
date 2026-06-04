"""Centralized permission capability map (Phase 4A).

Lightweight RBAC: a *capability* is a ``"resource:action"`` string mapped to the
set of roles allowed to perform it. ``require()`` raises 403 when the capability
is missing; unknown capabilities fail **closed** (deny).

Phase 4A scope: this module is DEFINED + unit-tested, and ``require_setup_role``
is re-expressed through it (behavior-IDENTICAL: admin/barn_manager => "barn:manage").
Broad wiring into routes and any tightening of policy is deferred to Phase 4C.
Do NOT add restrictions here that would change current behavior.
"""
from __future__ import annotations

from typing import Any, Dict, Set

from fastapi import HTTPException

# Setup/management capability — matches today's require_setup_role gate exactly
# (Stable Owner / Admin / Barn Manager edit barn-level setup).
SETUP_ROLES: Set[str] = {"admin", "barn_manager"}

CAPABILITIES: Dict[str, Set[str]] = {
    "barn:manage": set(SETUP_ROLES),
}

# Per-capability denial messages preserve the exact wording used by the existing
# guards so swapping them in later (Phase 4C) is behavior-identical.
_DENY_MESSAGES: Dict[str, str] = {
    "barn:manage": "Owner / Barn Manager access required",
}


def has_capability(user: Dict[str, Any], capability: str) -> bool:
    allowed = CAPABILITIES.get(capability)
    if allowed is None:
        return False  # fail closed on unknown capability
    return user.get("role") in allowed


def require(user: Dict[str, Any], capability: str) -> None:
    if not has_capability(user, capability):
        raise HTTPException(
            status_code=403,
            detail=_DENY_MESSAGES.get(capability, "Insufficient permissions"),
        )


def require_setup_role(user: Dict[str, Any]) -> None:
    """Behavior-identical re-expression of the existing setup-role guard."""
    require(user, "barn:manage")
