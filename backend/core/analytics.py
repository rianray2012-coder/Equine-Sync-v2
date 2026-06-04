"""Server-side analytics event recording (Phase 3G).

Thin event-insert helper shared by routers and background loops. Relocated
verbatim from ``server.py`` during the app-assembly refactor.
"""
import logging
from typing import Any, Dict, Optional

from core.db import db
from core.helpers import new_id, now_utc, iso

logger = logging.getLogger(__name__)


async def _track(name: str, props: Dict[str, Any], user_id: Optional[str] = None):
    """Internal: record an analytics event server-side."""
    try:
        await db.events.insert_one({
            "id": new_id(), "name": name, "props": props or {},
            "user_id": user_id, "at": iso(now_utc()),
        })
    except Exception:
        logger.exception("Failed to record event %s", name)
