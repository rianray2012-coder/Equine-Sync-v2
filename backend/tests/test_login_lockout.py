"""Tests for account-level brute-force lockout (Phase 2D).

Unit tests use an in-memory fake db so threshold, window-reset, expiration and
clear-on-success are deterministic. A small HTTP integration test confirms the
live endpoint locks after the threshold (using a unique throwaway email so no
shared/demo account is affected).
"""
import asyncio
import os
import pathlib
import time

import pytest
import requests

from core.login_attempts import check_lockout, clear_attempts, record_failure


# ---------------- in-memory fake db ----------------

class _FakeCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, query, projection=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                return dict(d)
        return None

    async def update_one(self, query, update, upsert=False):
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                d.update(update.get("$set", {}))
                return
        if upsert:
            self.docs.append(dict(update.get("$set", {})))

    async def delete_one(self, query):
        self.docs = [d for d in self.docs if not all(d.get(k) == v for k, v in query.items())]


class _FakeDB:
    def __init__(self):
        self.login_attempts = _FakeCollection()


def _run(coro):
    return asyncio.run(coro)


CFG = {"max_attempts": 3, "window_minutes": 15, "lockout_minutes": 15}


def test_failures_below_threshold_not_locked():
    db = _FakeDB()
    _run(record_failure(db, "a@x.com", **CFG))
    _run(record_failure(db, "a@x.com", **CFG))
    assert _run(check_lockout(db, "a@x.com")) is None


def test_threshold_triggers_lockout():
    db = _FakeDB()
    for _ in range(3):
        _run(record_failure(db, "a@x.com", **CFG))
    remaining = _run(check_lockout(db, "a@x.com"))
    assert remaining and remaining > 0


def test_success_clears_attempts():
    db = _FakeDB()
    for _ in range(3):
        _run(record_failure(db, "a@x.com", **CFG))
    _run(clear_attempts(db, "a@x.com"))
    assert _run(check_lockout(db, "a@x.com")) is None


def test_lockout_expires():
    db = _FakeDB()
    for _ in range(3):
        _run(record_failure(db, "a@x.com", **CFG))
    # Force the lock into the past.
    db.login_attempts.docs[0]["locked_until"] = "2000-01-01T00:00:00+00:00"
    assert _run(check_lockout(db, "a@x.com")) is None


def test_window_reset_does_not_accumulate_old_failures():
    db = _FakeDB()
    _run(record_failure(db, "a@x.com", **CFG))
    # Age the first failure beyond the window.
    db.login_attempts.docs[0]["first_failed_at"] = "2000-01-01T00:00:00+00:00"
    res = _run(record_failure(db, "a@x.com", **CFG))
    assert res["count"] == 1  # counter restarted


def test_lockout_is_case_insensitive():
    db = _FakeDB()
    for _ in range(3):
        _run(record_failure(db, "A@X.com", **CFG))
    assert _run(check_lockout(db, "a@x.com")) is not None


# ---------------- HTTP integration ----------------

def _base_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    env = pathlib.Path(__file__).resolve().parents[2] / "frontend" / ".env"
    for line in env.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


API = f"{_base_url()}/api"


def test_http_login_locks_after_threshold():
    email = f"lockout_{time.time_ns()}@example.com"  # unique, never a real account
    codes = []
    for _ in range(7):
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": "wrong"}, timeout=30)
        codes.append(r.status_code)
    # First failures are 401 (invalid creds); once locked, 423 appears.
    assert 423 in codes, codes
    assert codes[0] == 401


def test_http_admin_not_locked_out():
    # The demo admin must remain able to sign in (success clears any counter).
    r = requests.post(f"{API}/auth/login", json={"email": "admin@equinesync.com", "password": "demo1234"}, timeout=30)
    assert r.status_code == 200
