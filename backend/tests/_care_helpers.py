"""Shared helpers for the care-records integration tests (Phase 6D).

Consolidates the env-reading, Mongo client, API base-URL, and admin-login
boilerplate that was previously copy-pasted across the care test modules
(`test_care_integrity.py`, `test_care_state_guards.py`, `test_care_filtering.py`,
`test_care_scoping.py`, `test_care_routes.py`). Behavior is identical to the
inlined versions it replaces — this is a pure dedup, no test contract change.

Mirrors the existing `_test_creds.py` shared-fixture precedent.
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
    `sub` is the path under that root (e.g. ".env" or "frontend/.env").
    """
    envf = pathlib.Path(__file__).resolve().parents[root_index] / sub
    for line in envf.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def base_url() -> str:
    return (os.environ.get("REACT_APP_BACKEND_URL")
            or read_env("REACT_APP_BACKEND_URL", 2, "frontend/.env")).rstrip("/")


# Canonical `/api` root used by every care test module.
API = f"{base_url()}/api"


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
