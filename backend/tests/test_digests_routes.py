"""Phase 3E — routes/digests.py extraction tests (lightweight).

Covers route registration, auth/role gates, and basic response shape for the
6 owner digest/recap HTTP routes. Intentionally NOT a digest-content suite
(content logic lives in owner_digest.py and is unchanged by 3E).
"""
import pytest
import requests

from ._owner_helpers import API, BASE, auth_headers as _h
from ._test_creds import ADMIN, OWNER, GROOM

DIGEST_PATHS = [
    "/api/notifications/digest/preview",
    "/api/notifications/digest/send-me",
    "/api/admin/digest/run-now",
    "/api/notifications/weekly-recap/preview",
    "/api/notifications/weekly-recap/send-me",
    "/api/admin/weekly-recap/run-now",
]

PREVIEW_PATHS = [
    "/notifications/digest/preview",
    "/notifications/weekly-recap/preview",
]
SEND_ME_PATHS = [
    "/notifications/digest/send-me",
    "/notifications/weekly-recap/send-me",
]
ADMIN_RUN_PATHS = [
    "/admin/digest/run-now",
    "/admin/weekly-recap/run-now",
]


def test_digest_routes_registered():
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
    missing = [p for p in DIGEST_PATHS if p not in paths]
    assert not missing, f"missing registered digest routes: {missing}"


def test_all_digest_routes_require_auth():
    for p in DIGEST_PATHS:
        # OpenAPI keys already include /api
        r = requests.post(f"{BASE}{p}", timeout=30)
        assert r.status_code == 401, f"{p} should require auth, got {r.status_code}"


def test_preview_returns_shape_under_auth():
    h = _h(OWNER)
    for p in PREVIEW_PATHS:
        r = requests.post(f"{API}{p}", headers=h, timeout=30)
        assert r.status_code == 200, f"{p} -> {r.status_code}: {r.text}"
        body = r.json()
        assert "empty" in body and isinstance(body["empty"], bool)
        if body["empty"] is False:
            assert {"payload", "html", "text"}.issubset(body.keys())


def test_send_me_owner_only():
    owner_h, groom_h = _h(OWNER), _h(GROOM)
    for p in SEND_ME_PATHS:
        assert requests.post(f"{API}{p}", headers=groom_h, timeout=30).status_code == 403
        assert requests.post(f"{API}{p}", headers=owner_h, timeout=30).status_code == 200


def test_admin_run_now_admin_only():
    admin_h, groom_h = _h(ADMIN), _h(GROOM)
    for p in ADMIN_RUN_PATHS:
        assert requests.post(f"{API}{p}", headers=groom_h, timeout=30).status_code == 403
        r = requests.post(f"{API}{p}", headers=admin_h, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), dict)
