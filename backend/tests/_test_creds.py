"""Shared test-credential fixtures.

Centralises the demo accounts referenced by every backend integration test
so the demo password lives in exactly one place. Reads from environment
when present (so CI or a different demo seed can override) and falls back
to the documented demo values from `/app/memory/test_credentials.md`.

NB: these are demo seed accounts, not secrets. They exist precisely so the
testing harness can reach the platform.
"""
from __future__ import annotations

import os

DEMO_PASSWORD = os.environ.get("EQUINESYNC_DEMO_PASSWORD", "demo1234")

ADMIN = {
    "email": os.environ.get("EQUINESYNC_TEST_ADMIN_EMAIL", "admin@equinesync.com"),
    "password": DEMO_PASSWORD,
}
OWNER = {
    "email": os.environ.get("EQUINESYNC_TEST_OWNER_EMAIL", "owner@equinesync.com"),
    "password": DEMO_PASSWORD,
}
GROOM = {
    "email": os.environ.get("EQUINESYNC_TEST_GROOM_EMAIL", "groom@equinesync.com"),
    "password": DEMO_PASSWORD,
}
