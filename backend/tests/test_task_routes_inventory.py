"""Phase 3D — lightweight care/task route inventory guard.

Verifies that the expected task-engine and care endpoints remain REGISTERED
and are basically available under auth. This is a regression net so a future
refactor cannot silently drop a route — it is intentionally NOT a behavioral
test (those live in test_task_engine.py / test_care_routes.py).
"""
import os
import pathlib

import pytest
import requests

from ._test_creds import ADMIN


def _base_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    env = pathlib.Path(__file__).resolve().parents[2] / "frontend" / ".env"
    for line in env.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


BASE = _base_url()
API = f"{BASE}/api"


def _token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


# Routes that must stay registered (OpenAPI keys include the /api prefix).
TASK_ENGINE_PATHS = [
    "/api/task-templates", "/api/task-templates/{tpl_id}",
    "/api/tasks", "/api/tasks/today", "/api/tasks/{task_id}",
    "/api/tasks/{task_id}/complete", "/api/tasks/bulk-complete",
    "/api/tasks/{task_id}/skip", "/api/tasks/{task_id}/void",
    "/api/tasks/{task_id}/reassign", "/api/tasks/materialize",
    "/api/tasks/analytics/summary", "/api/staff/{user_id}/activity",
    "/api/horses/{horse_id}/timeline",  # intentionally in task_engine.py
]
CARE_PATHS = [
    "/api/medications", "/api/medication-logs",
    "/api/feed-tasks", "/api/feed-tasks/{task_id}/complete",
    "/api/vet-records", "/api/farrier-history",
    "/api/injuries", "/api/wellness", "/api/riders",
]

# GET list endpoints that should respond 200 under auth.
AUTHED_GET_LIST = [
    "/tasks", "/tasks/today", "/task-templates", "/tasks/analytics/summary",
    "/medications", "/medication-logs", "/feed-tasks", "/vet-records",
    "/farrier-history", "/injuries", "/wellness", "/riders",
]


def test_expected_task_and_care_routes_are_registered():
    # The OpenAPI spec is served at the backend root ("/openapi.json"), which is
    # NOT under the "/api" ingress prefix — externally that path routes to the
    # frontend. Fetch it directly from the backend's internal port instead.
    spec = None
    for url in ("http://localhost:8001/openapi.json", f"{BASE}/openapi.json"):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200 and "application/json" in r.headers.get("content-type", ""):
                spec = r.json()
                break
        except requests.RequestException:
            continue
    if spec is None:
        pytest.skip("OpenAPI spec not reachable in this environment")
    paths = set(spec.get("paths", {}).keys())
    missing = [p for p in (TASK_ENGINE_PATHS + CARE_PATHS) if p not in paths]
    assert not missing, f"missing registered routes: {missing}"


def test_authed_get_lists_available():
    headers = {"Authorization": f"Bearer {_token()}"}
    for path in AUTHED_GET_LIST:
        r = requests.get(f"{API}{path}", headers=headers, timeout=30)
        assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text}"


def test_get_lists_require_auth():
    # Representative auth-gate check (not exhaustive).
    for path in ("/tasks", "/medications", "/feed-tasks"):
        r = requests.get(f"{API}{path}", timeout=30)
        assert r.status_code == 401, f"{path} should require auth, got {r.status_code}"
