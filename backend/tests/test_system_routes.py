"""Phase 3B — routes/system.py extraction tests.

Covers GET /api/ (root) and GET /api/health, including the additive
`dependencies` booleans block and a no-secret-leak assertion.
"""
import os
import pathlib

import requests

from routes.system import dependencies_snapshot


def _read_env_value(key):
    env = pathlib.Path(__file__).resolve().parents[1] / ".env"
    if not env.exists():
        return ""
    for line in env.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


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


def test_root_banner():
    r = requests.get(f"{API}/", timeout=30)
    assert r.status_code == 200
    assert r.json() == {"app": "EquineSync", "status": "ok"}


def test_health_shape_and_dependencies():
    r = requests.get(f"{API}/health", timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert body["config"]["jwt_configured"] is True
    # Additive Phase 3B dependencies block — booleans only.
    deps = body["dependencies"]
    expected = {
        "mailer_configured", "email_verification_enforced",
        "rate_limiting_enabled", "auto_seed_enabled", "seed_route_enabled",
    }
    assert set(deps.keys()) == expected
    for k, v in deps.items():
        assert isinstance(v, bool), f"{k} must be a boolean, got {type(v)}"
    # Posture sanity in this dev environment.
    assert deps["seed_route_enabled"] is False


def test_health_does_not_leak_secrets():
    r = requests.get(f"{API}/health", timeout=30)
    text = r.text
    # Generic secret markers must never appear.
    for marker in ("mongodb://", "JWT_SECRET", "RESEND_API_KEY", "EMERGENT_LLM_KEY", "re_", "sk-"):
        assert marker not in text, f"health response leaked marker: {marker}"
    # Actual configured secret VALUES must never appear.
    for key in ("JWT_SECRET", "MONGO_URL", "RESEND_API_KEY", "EMERGENT_LLM_KEY"):
        val = _read_env_value(key)
        if val:
            assert val not in text, f"health response leaked {key} value"


def test_seed_route_enabled_reports_effective_availability():
    # Production is ALWAYS off, even with the flag on (mirrors the seed-route
    # access policy: production is never reachable).
    prod = dependencies_snapshot({"APP_ENV": "production", "ALLOW_SEED_ROUTE": "true",
                                  "RESEND_API_KEY": "x"})
    assert prod["seed_route_enabled"] is False
    # Dev + flag on → on; dev + flag off → off.
    assert dependencies_snapshot({"APP_ENV": "development", "ALLOW_SEED_ROUTE": "true"})["seed_route_enabled"] is True
    assert dependencies_snapshot({"APP_ENV": "development"})["seed_route_enabled"] is False


def test_dependencies_snapshot_booleans_only():
    snap = dependencies_snapshot({"APP_ENV": "production", "ALLOW_SEED_ROUTE": "true"})
    expected = {
        "mailer_configured", "email_verification_enforced",
        "rate_limiting_enabled", "auto_seed_enabled", "seed_route_enabled",
    }
    assert set(snap.keys()) == expected
    for k, v in snap.items():
        assert isinstance(v, bool), f"{k} must be boolean"
    # Production posture: auto-seed and seed-route both hard-off.
    assert snap["auto_seed_enabled"] is False
    assert snap["seed_route_enabled"] is False
