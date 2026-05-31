"""IP-based rate limiting for auth-sensitive endpoints (Phase 2B).

Implemented as a FastAPI **dependency** using the `limits` library (in-process
memory store), applied via ``dependencies=[Depends(auth_rate_limiter)]``.

A dependency is used rather than slowapi's decorator: slowapi's decorator is
incompatible with FastAPI 0.110 + Pydantic v2 request-body models (it drops the
body, yielding spurious 422s). The dependency approach preserves endpoint
signatures.

Limits are environment-driven (see ``config``): strict in production, generous
in development so local use and the HTTP integration suite are not throttled.
Toggle entirely with ``RATE_LIMIT_ENABLED``.

NOTE: the memory store is per-process. The current single-uvicorn deployment is
fine; a multi-replica deployment would need a shared store (e.g. Redis/memcached
via a limits storage URI) — tracked in /app/docs/KNOWN_TECH_DEBT.md.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import HTTPException, Request
from limits import parse
from limits.storage import storage_from_string
from limits.strategies import MovingWindowRateLimiter

from core.config import auth_rate_limit, rate_limit_enabled


def build_rate_limiter(
    limit_str: str,
    *,
    enabled: bool = True,
    storage_uri: str = "memory://",
) -> Callable[[Request], Awaitable[None]]:
    """Return a FastAPI dependency that throttles per client IP + request path."""
    limit = parse(limit_str)
    limiter = MovingWindowRateLimiter(storage_from_string(storage_uri))

    async def _dependency(request: Request) -> None:
        if not enabled:
            return
        ip = request.client.host if request.client else "unknown"
        if not limiter.hit(limit, "auth", request.url.path, ip):
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please slow down and try again shortly.",
            )

    return _dependency


# Default dependency used by the auth router, resolved from env at import time
# (after server.py has loaded .env).
auth_rate_limiter = build_rate_limiter(
    auth_rate_limit(), enabled=rate_limit_enabled()
)
