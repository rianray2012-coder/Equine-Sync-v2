"""Tenancy helpers (Phase 4A) — canonical barn-scoping primitives.

Pure and dependency-light: NO database access and NO import from ``server.py``.
These establish the FOUNDATION for multi-tenancy — a single canonical barn id,
a legacy-safe resolver (missing => primary), a query-filter builder, and a
document stamper. **Phase 4A does NOT yet apply these to route reads/writes**
(that is Phase 4B); they live here to be unit-tested and adopted incrementally.

Source-of-truth rule: the user DOCUMENT's ``barn_id`` is authoritative for any
authorization/scoping decision — never the JWT claim (the claim is forward-compat
only).

Task-engine alias note: the task engine + ``media`` collection use
``tenant_id="default"`` which maps to canonical ``barn_id="primary"`` for the
founder/demo barn. That reconciliation is deferred to the dedicated Phase 4B
task-engine sub-phase; nothing here touches ``tenant_id``.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

PRIMARY_BARN_ID = "primary"


def resolve_barn_id(user: Optional[Dict[str, Any]]) -> str:
    """Authoritative barn id for a user document.

    Missing/empty => ``PRIMARY_BARN_ID`` so legacy/backfilled users are never
    locked out (mirrors the ``email_verified`` "missing => verified" pattern).
    """
    if not user:
        return PRIMARY_BARN_ID
    return user.get("barn_id") or PRIMARY_BARN_ID


def barn_filter(user: Optional[Dict[str, Any]], extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build a Mongo filter scoped to the user's barn, merged with ``extra``.

    Hardening (Phase 4A): caller-provided ``extra`` can NEVER replace the
    resolved barn scope. ``extra`` is merged first, then the authoritative
    ``barn_id`` is set last so a conflicting ``extra["barn_id"]`` is ignored.
    """
    q: Dict[str, Any] = {}
    if extra:
        q.update(extra)
    q["barn_id"] = resolve_barn_id(user)
    return q


def stamp_barn(user: Optional[Dict[str, Any]], doc: Dict[str, Any]) -> Dict[str, Any]:
    """Stamp the caller's barn id onto a document destined for insert.

    Normalizes to the caller's barn (a document must never be written into
    another barn via this helper). Returns the same dict for chaining.
    """
    doc["barn_id"] = resolve_barn_id(user)
    return doc
