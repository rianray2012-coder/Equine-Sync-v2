"""Generic, dependency-light helpers shared across routers (Phase 3G).

Pure time/id helpers plus thin Mongo listing utilities. No business logic.
Relocated verbatim from ``server.py`` during the app-assembly refactor.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request

from core.db import db


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def clean(doc):
    if not doc:
        return doc
    doc.pop("_id", None)
    return doc


async def list_collection(coll, query=None, sort_field=None, limit=500):
    q = query or {}
    cursor = db[coll].find(q, {"_id": 0})
    if sort_field:
        cursor = cursor.sort(sort_field, -1)
    return await cursor.to_list(limit)


def _user_safe(user: dict) -> dict:
    return {k: v for k, v in user.items() if k not in ("password_hash", "_id")}


async def _client_meta(request: Optional[Request]):
    ua = request.headers.get("user-agent") if request else None
    ip = request.client.host if request and request.client else None
    return ua, ip
