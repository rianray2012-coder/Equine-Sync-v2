"""Shared helpers for the Owner-Trust / owner-facing integration tests (Phase 7D-3).

Self-contained (does NOT import from `_care_helpers`). Consolidates the env /
API base-URL / Mongo / login boilerplate that the owner test modules previously
each redefined — several with a **stale hardcoded preview-host fallback**. Tests
now fail clearly if `REACT_APP_BACKEND_URL` / `MONGO_URL` are not configured,
instead of silently pointing at a dead preview URL.

Mirrors the `_test_creds.py` / `_care_helpers.py` shared-fixture precedent, but is
owned by the owner-trust domain so the care helpers stay untouched.
"""
from __future__ import annotations

import os
import pathlib

import pymongo
import requests

from ._test_creds import ADMIN, DEMO_PASSWORD


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


def login_headers(email: str, password: str = DEMO_PASSWORD) -> dict:
    """Email/password convenience wrapper around `auth_headers`."""
    return auth_headers({"email": email, "password": password})
