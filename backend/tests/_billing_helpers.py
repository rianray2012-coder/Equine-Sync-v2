"""Shared helpers for the billing / invoice / recurring-charge integration tests (Phase 9D).

Self-contained (does NOT import from `_owner_helpers`/`_care_helpers`).
Consolidates the env / API base-URL / Mongo / login boilerplate that the billing
test modules (9A, 9B-1, 9B-2, 3F extraction, 4B-4 scoping, 7D-1 owner billing)
previously each redefined. Tests fail clearly if `REACT_APP_BACKEND_URL` /
`MONGO_URL` are not configured, rather than silently pointing at a dead host.

Mirrors the `_test_creds.py` / `_owner_helpers.py` / `_care_helpers.py`
shared-fixture precedent, but is owned by the billing domain so the owner/care
helpers stay untouched.
"""
from __future__ import annotations

import os
import pathlib

import pymongo
import requests

from ._test_creds import ADMIN


def read_env(key: str, root_index: int, sub: str) -> str:
    """Read a single KEY=value from a .env file relative to this tests dir.

    `root_index` walks up parents() from this file: 1 -> backend/, 2 -> repo root.
    """
    envf = pathlib.Path(__file__).resolve().parents[root_index] / sub
    for line in envf.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def base_url() -> str:
    # No live preview-host fallback: empty config fails clearly at request time.
    return (os.environ.get("REACT_APP_BACKEND_URL")
            or read_env("REACT_APP_BACKEND_URL", 2, "frontend/.env")).rstrip("/")


BASE = base_url()
API = f"{BASE}/api"


def mongo_db():
    url = os.environ.get("MONGO_URL") or read_env("MONGO_URL", 1, ".env")
    name = os.environ.get("DB_NAME") or read_env("DB_NAME", 1, ".env")
    return pymongo.MongoClient(url)[name]


def auth_headers(creds: dict = ADMIN) -> dict:
    """Log in (defaults to the demo ADMIN) and return a Bearer auth header."""
    r = requests.post(f"{API}/auth/login",
                      json={"email": creds["email"], "password": creds["password"]}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def cleanup_invoices(db, ids) -> None:
    """Captured-id teardown: delete invoices by id."""
    ids = list(ids or [])
    if ids:
        db.invoices.delete_many({"id": {"$in": ids}})


def cleanup_recurring(db, ids) -> None:
    """Captured-id teardown: delete recurring charges + their generated invoices."""
    ids = list(ids or [])
    if ids:
        db.invoices.delete_many({"recurring_charge_id": {"$in": ids}})
        db.recurring_charges.delete_many({"id": {"$in": ids}})
