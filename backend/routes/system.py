"""routes/system.py — System probes (root + readiness health).

Extracted from server.py (Phase 3B). No API behavior change except an
**additive** ``dependencies`` block on ``/api/health`` (booleans only — never
exposes secret values, URLs, tokens, or keys).
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.config import (
    is_production,
    enforce_email_verification,
    rate_limit_enabled,
    auto_seed_enabled,
    allow_seed_route,
)
from core import runtime_state

logger = logging.getLogger(__name__)

SERVICE_NAME = "equinesync-api"


def dependencies_snapshot(env=None) -> dict:
    """Booleans-only posture of cross-cutting subsystems for /api/health.

    Pure + env-injectable for testing. Never exposes secret values, URLs, or
    keys — only derived booleans. ``seed_route_enabled`` reports **effective**
    route availability (production is always off, regardless of the flag),
    mirroring the actual seed-route access policy without changing it.
    """
    e = os.environ if env is None else env
    return {
        "mailer_configured": bool((e.get("RESEND_API_KEY") or "").strip()),
        "email_verification_enforced": enforce_email_verification(e),
        "rate_limiting_enabled": rate_limit_enabled(e),
        "auto_seed_enabled": auto_seed_enabled(e),
        "seed_route_enabled": (not is_production(e)) and allow_seed_route(e),
    }


def build_router(db) -> APIRouter:
    router = APIRouter(tags=["system"])

    async def _build_health():
        """Shared readiness body + status (Mongo ping + booleans-only posture).

        Returns a freshly-built dict each call so callers can safely extend
        their own copy without mutating anyone else's response.
        """
        db_ok = False
        try:
            await db.command("ping")
            db_ok = True
        except Exception:
            logger.exception("health: database ping failed")

        body = {
            "status": "ok" if db_ok else "degraded",
            "service": SERVICE_NAME,
            "version": os.environ.get("APP_VERSION", "0.1.0"),
            "database": "connected" if db_ok else "unreachable",
            "config": {
                "jwt_configured": bool(os.environ.get("JWT_SECRET", "").strip()),
                "cors_configured": bool(os.environ.get("CORS_ORIGINS", "").strip()),
                "environment": "production" if is_production() else "development",
            },
            # Additive (Phase 3B): booleans only — no secrets/URLs/keys/values.
            "dependencies": dependencies_snapshot(),
        }
        return body, (200 if db_ok else 503)

    @router.get("/")
    async def root():
        return {"app": "EquineSync", "status": "ok"}

    @router.get("/health")
    async def health():
        """Legacy readiness probe (Phase 3B) — kept byte-compatible.

        Reports config validity + DB connectivity. Never exposes secret values.
        """
        body, status = await _build_health()
        return JSONResponse(body, status_code=status)

    @router.get("/health/live")
    async def health_live():
        """Liveness probe (Phase 10B). Process-up only — NEVER touches Mongo or
        any external service. Always 200 so a transient DB blip can't trigger a
        restart of an otherwise-healthy process."""
        return {"status": "alive", "service": SERVICE_NAME}

    @router.get("/health/ready")
    async def health_ready():
        """Readiness probe (Phase 10B). Same dependency check as /health, plus
        additive, no-secret runtime fields. A defensive copy is made so /health
        can never inherit these by mutation."""
        body, status = await _build_health()
        ready_body = dict(body)  # copy before extending — /health stays clean
        ready_body.update(runtime_state.snapshot())
        return JSONResponse(ready_body, status_code=status)

    return router
