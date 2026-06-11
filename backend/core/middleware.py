"""Phase 10A — pure ASGI request-context + completion-log middleware.

Implemented as a **pure ASGI** middleware (not Starlette's BaseHTTPMiddleware)
so the per-request `contextvars` set here propagate cleanly into the downstream
handler AND any values the handler sets (e.g. `user_id`/`barn_id` from
`get_current_user`) remain visible when we emit the request-completion log —
which BaseHTTPMiddleware's task-hopping would lose.

Strictly additive:
  * adds an `X-Request-ID` response header (never overwrites an existing one)
  * logs one INFO completion line (or ERROR on unhandled exception) per request
  * never reads/logs request bodies, headers, or the query string
  * re-raises exceptions unchanged (response body/status are untouched)
  * resets all contextvars in `finally` so nothing leaks between requests
"""
from __future__ import annotations

import logging
import time

from core.logging_config import (
    request_id_var,
    user_id_var,
    barn_id_var,
    sanitize_request_id,
)

logger = logging.getLogger("equinesync.request")


class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        incoming = None
        for k, v in scope.get("headers", []):
            if k == b"x-request-id":
                try:
                    incoming = v.decode("latin-1")
                except Exception:
                    incoming = None
                break
        rid = sanitize_request_id(incoming)

        t_rid = request_id_var.set(rid)
        t_uid = user_id_var.set(None)
        t_bid = barn_id_var.set(None)

        status_holder = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                if not any(k.lower() == b"x-request-id" for k, _ in headers):
                    headers.append((b"x-request-id", rid.encode("latin-1")))
                status_holder["code"] = message["status"]
            await send(message)

        method = scope.get("method")
        path = scope.get("path")  # path only — never the query string
        start = time.perf_counter()
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception(
                "request failed",
                extra={"method": method, "path": path, "status_code": 500, "duration_ms": duration_ms},
            )
            raise
        else:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "request completed",
                extra={"method": method, "path": path,
                       "status_code": status_holder["code"], "duration_ms": duration_ms},
            )
        finally:
            request_id_var.reset(t_rid)
            user_id_var.reset(t_uid)
            barn_id_var.reset(t_bid)
