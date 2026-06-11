"""Phase 10B — health/observability hardening.

Unit tests (no live server) drive the system router handlers directly with a
dummy DB to prove:
  * /health/live never touches Mongo (works even when ping raises) and is 200
  * /health/ready degrades to 503 when the DB is down, still carrying the
    additive runtime fields
Live integration tests assert the happy-path shapes, that /api/health stayed
byte-compatible (no additive fields), and that no secret leaks into any payload.
"""
import asyncio
import json
import os

import requests

from routes.system import build_router
from ._api_helpers import API

_HEALTH_KEYS = {"status", "service", "version", "database", "config", "dependencies"}
_ADDITIVE_KEYS = {"started_at", "uptime_seconds", "indexes_ensured"}


# ----------------------------------------------------------------- unit harness

class _DummyDB:
    async def command(self, *a, **k):
        raise RuntimeError("db down")


def _endpoint(path):
    router = build_router(_DummyDB())
    return next(r.endpoint for r in router.routes if r.path == path)


def test_liveness_never_touches_db_and_is_200():
    res = asyncio.run(_endpoint("/health/live")())
    assert res == {"status": "alive", "service": "equinesync-api"}


def test_readiness_degrades_gracefully_with_additive_fields():
    resp = asyncio.run(_endpoint("/health/ready")())  # JSONResponse
    assert resp.status_code == 503
    body = json.loads(resp.body)
    assert body["status"] == "degraded" and body["database"] == "unreachable"
    assert _ADDITIVE_KEYS.issubset(body.keys())


def test_health_does_not_inherit_additive_fields_unit():
    resp = asyncio.run(_endpoint("/health")())
    body = json.loads(resp.body)
    assert set(body.keys()) == _HEALTH_KEYS
    assert not (_ADDITIVE_KEYS & set(body.keys()))


# ----------------------------------------------------------------- live integration

_SECRET_VALUES = [
    v for v in (os.environ.get("MONGO_URL"), os.environ.get("JWT_SECRET")) if v
]


def test_live_endpoint_live():
    r = requests.get(f"{API}/health/live", timeout=30)
    assert r.status_code == 200
    assert r.json() == {"status": "alive", "service": "equinesync-api"}


def test_ready_endpoint_superset_live():
    r = requests.get(f"{API}/health/ready", timeout=30)
    assert r.status_code in (200, 503)
    body = r.json()
    assert _HEALTH_KEYS.issubset(body.keys())
    assert _ADDITIVE_KEYS.issubset(body.keys())


def test_health_unchanged_live():
    r = requests.get(f"{API}/health", timeout=30)
    body = r.json()
    assert set(body.keys()) == _HEALTH_KEYS  # no additive fields leaked in


def test_no_secret_leak_in_health_payloads_live():
    for path in ("/health", "/health/live", "/health/ready"):
        txt = requests.get(f"{API}{path}", timeout=30).text
        for secret in _SECRET_VALUES:
            assert secret not in txt, f"secret leaked in {path}"
