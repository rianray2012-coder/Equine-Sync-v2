"""Unit tests for the rate-limit dependency (Phase 2B).

Builds a minimal app with the dependency factory from rate_limit.py and asserts
a 429 is returned once the limit is exceeded. Deterministic; does not touch the
live server (which runs a generous dev limit).
"""
from fastapi import Depends, FastAPI
from starlette.testclient import TestClient

from core.rate_limit import build_rate_limiter


def _app(limit: str, enabled: bool = True) -> FastAPI:
    app = FastAPI()
    dep = build_rate_limiter(limit, enabled=enabled)

    @app.post("/ping", dependencies=[Depends(dep)])
    async def ping():
        return {"ok": True}

    # A body-bearing route proves the dependency does not break Pydantic bodies.
    from pydantic import BaseModel

    class Body(BaseModel):
        value: str

    @app.post("/echo", dependencies=[Depends(dep)])
    async def echo(body: Body):
        return {"value": body.value}

    return app


def test_returns_429_after_limit_exceeded():
    client = TestClient(_app("2/minute"))
    assert client.post("/ping").status_code == 200
    assert client.post("/ping").status_code == 200
    assert client.post("/ping").status_code == 429


def test_disabled_limiter_never_429():
    client = TestClient(_app("1/minute", enabled=False))
    for _ in range(3):
        assert client.post("/ping").status_code == 200


def test_dependency_preserves_request_body():
    client = TestClient(_app("10/minute"))
    r = client.post("/echo", json={"value": "hello"})
    assert r.status_code == 200
    assert r.json() == {"value": "hello"}
