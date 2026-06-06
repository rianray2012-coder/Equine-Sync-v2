"""core/audit.py — Phase 5 immutable audit logging service (write-side).

An append-only operational/security audit trail written to the ``audit_log``
collection. Deliberately mirrors the analytics ``_track`` pattern:

* **Fail-open.** A write failure NEVER propagates to the caller and never
  blocks the primary action — audit is observational, not load-bearing.
* **Barn-stamped.** Every entry carries ``barn_id`` so the trail inherits the
  Phase-4 multi-tenant isolation guarantees (reads, when added in 5D, scope
  via ``barn_filter``).
* **PII-minimized.** A redaction pass strips sensitive keys (passwords, tokens,
  hashes, secrets) from ``metadata`` as defense-in-depth even though call-sites
  are expected to pass minimal, non-sensitive metadata.

v1 is **WRITE-ONLY**: there is no read/list API (deferred to Phase 5D, which
will also audit reads of the audit log itself). Retention is **indefinite** in
v1 — no TTL index. See ``docs/AUDIT_LOGGING.md``.
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import Request

from core.db import db
from core.tenancy import PRIMARY_BARN_ID, resolve_barn_id

logger = logging.getLogger(__name__)

# Sensitive-data redaction. A metadata key is redacted when its normalized form
# (lowercased, separators/camelCase boundaries collapsed to alphanumerics) either
# (a) contains any sensitive *fragment* — so variants like `resetToken`,
# `verificationToken`, `authorization_header`, `apiKey`, `secretKey`, `jwt`,
# `session_token_id`, `password_hash` are all caught — or (b) exactly matches a
# token-bearing key whose name has no obvious fragment (e.g. accept/reset/verify
# URLs that embed a raw token).
_SENSITIVE_FRAGMENTS = (
    "password", "passwd", "token", "secret", "authorization",
    "credential", "apikey", "jwt", "hash",
)
_SENSITIVE_EXACT = {
    "devaccepturl", "accepturl", "reseturl", "verifyurl",
}
_MAX_STR = 500          # truncate over-long metadata strings
_MAX_LIST = 50          # cap metadata list length
_MAX_DEPTH = 6          # guard against pathological nesting

# Strong refs to fire-and-forget denial tasks so they aren't GC'd mid-flight.
_bg_tasks: set = set()


def _collapse_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _is_sensitive_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    collapsed = _collapse_key(key)
    if collapsed in _SENSITIVE_EXACT:
        return True
    return any(frag in collapsed for frag in _SENSITIVE_FRAGMENTS)


def _redact(value: Any, _depth: int = 0) -> Any:
    if _depth > _MAX_DEPTH:
        return "…"
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            if _is_sensitive_key(k):
                out[k] = "[redacted]"
            else:
                out[k] = _redact(v, _depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [_redact(v, _depth + 1) for v in list(value)[:_MAX_LIST]]
    if isinstance(value, str) and len(value) > _MAX_STR:
        return value[:_MAX_STR] + "…"
    return value


def _client_meta(request: Optional[Request]) -> Tuple[Optional[str], Optional[str]]:
    if request is None:
        return None, None
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    return ua, ip


def build_entry(
    *,
    action: str,
    user: Optional[Dict[str, Any]] = None,
    actor_email: Optional[str] = None,
    actor_role: Optional[str] = None,
    barn_id: Optional[str] = None,
    request: Optional[Request] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    outcome: str = "success",
    status_code: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a single immutable audit entry (pure — no DB I/O)."""
    ua, ip = _client_meta(request)
    actor_user_id = None
    if user is not None:
        actor_user_id = user.get("id")
        if actor_email is None:
            actor_email = user.get("email")
        if actor_role is None:
            actor_role = user.get("role")
        if barn_id is None:
            barn_id = resolve_barn_id(user)
    if barn_id is None:
        barn_id = PRIMARY_BARN_ID
    return {
        "id": str(uuid.uuid4()),
        "ts": datetime.now(timezone.utc).isoformat(),
        "barn_id": barn_id,
        "actor_user_id": actor_user_id,
        "actor_email": (actor_email.lower() if isinstance(actor_email, str) and actor_email else None),
        "actor_role": actor_role,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "outcome": outcome,
        "status_code": status_code,
        "ip": ip,
        "user_agent": ua,
        "metadata": _redact(metadata or {}),
    }


async def record(
    *,
    action: str,
    user: Optional[Dict[str, Any]] = None,
    actor_email: Optional[str] = None,
    actor_role: Optional[str] = None,
    barn_id: Optional[str] = None,
    request: Optional[Request] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    outcome: str = "success",
    status_code: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    _db: Any = None,
) -> None:
    """Append one audit entry. **Fail-open** — never raises to the caller."""
    try:
        entry = build_entry(
            action=action, user=user, actor_email=actor_email,
            actor_role=actor_role, barn_id=barn_id, request=request,
            resource_type=resource_type, resource_id=resource_id,
            outcome=outcome, status_code=status_code, metadata=metadata,
        )
        await (_db if _db is not None else db).audit_log.insert_one(entry)
    except Exception:
        logger.exception("audit.record failed (fail-open) action=%s", action)


def record_denial(user: Dict[str, Any], capability: str, message: str) -> None:
    """Sync entrypoint for ``core.permissions.require()`` denials.

    Schedules a fire-and-forget audit write on the running event loop so the
    403 path stays synchronous + behavior-identical. A no-op when there is no
    running loop (e.g. pure unit tests), so ``require()`` is never affected.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    try:
        task = loop.create_task(record(
            action="permission.denied", user=user, resource_type="capability",
            resource_id=capability, outcome="denied", status_code=403,
            metadata={"capability": capability, "message": message},
        ))
        _bg_tasks.add(task)
        task.add_done_callback(_bg_tasks.discard)
    except Exception:  # pragma: no cover - scheduling must never break require()
        logger.debug("record_denial scheduling failed", exc_info=True)


async def ensure_audit_indexes(database: Any = None) -> None:
    """Additive, idempotent indexes for the (future) read API + retention work."""
    d = database if database is not None else db
    try:
        await d.audit_log.create_index([("barn_id", 1), ("ts", -1)])
        await d.audit_log.create_index([("action", 1), ("ts", -1)])
        await d.audit_log.create_index([("actor_user_id", 1), ("ts", -1)])
    except Exception:
        logger.exception("ensure_audit_indexes failed (non-fatal)")
