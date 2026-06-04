"""Public base-URL resolution for building email/notification links (Phase 3G).

Honors ``APP_BASE_URL``; otherwise derives the user-facing origin from the
``x-forwarded-*`` headers (set by ingress) / request; otherwise falls back to
the documented production host. Relocated verbatim from ``server.py``.
"""
import os
from typing import Optional

from fastapi import Request


def _base_url(request: Optional[Request] = None) -> str:
    env_url = (os.environ.get("APP_BASE_URL") or "").strip().rstrip("/")
    if env_url:
        return env_url
    if request is not None:
        # Honor x-forwarded-* set by ingress so the link points to the user-facing origin
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme
        host = request.headers.get("x-forwarded-host") or request.headers.get("origin", "").replace("https://", "").replace("http://", "") or request.url.netloc
        host = host.split(",")[0].strip().rstrip("/")
        if host:
            return f"{proto}://{host}"
    return "https://herd-hub-19.emergent.host"
