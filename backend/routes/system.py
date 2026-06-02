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

logger = logging.getLogger(__name__)


def build_router(db) -> APIRouter:
    router = APIRouter(tags=["system"])

    @router.get("/")
    async def root():
        return {"app": "EquineSync", "status": "ok"}

    @router.get("/health")
    async def health():
        """Lightweight readiness probe. Reports config validity + DB connectivity.

        Never exposes secret values — only booleans/derived status. The
        ``dependencies`` block reports posture of cross-cutting subsystems.
        """
        db_ok = False
        try:
            await db.command("ping")
            db_ok = True
        except Exception:
            logger.exception("health: database ping failed")

        body = {
            "status": "ok" if db_ok else "degraded",
            "service": "equinesync-api",
            "version": os.environ.get("APP_VERSION", "0.1.0"),
            "database": "connected" if db_ok else "unreachable",
            "config": {
                "jwt_configured": bool(os.environ.get("JWT_SECRET", "").strip()),
                "cors_configured": bool(os.environ.get("CORS_ORIGINS", "").strip()),
                "environment": "production" if is_production() else "development",
            },
            # Additive (Phase 3B): booleans only — no secrets/URLs/keys/values.
            "dependencies": {
                "mailer_configured": bool(os.environ.get("RESEND_API_KEY", "").strip()),
                "email_verification_enforced": enforce_email_verification(),
                "rate_limiting_enabled": rate_limit_enabled(),
                "auto_seed_enabled": auto_seed_enabled(),
                "seed_route_enabled": allow_seed_route(),
            },
        }
        return JSONResponse(body, status_code=200 if db_ok else 503)

    return router
