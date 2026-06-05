"""Phase 4A — core.permissions capability-map unit tests (pure, no live server)."""
import pytest
from fastapi import HTTPException

from core.permissions import (
    CAPABILITIES,
    has_capability,
    require,
    require_setup_role,
)

SETUP_ROLES = ("admin", "barn_manager")
NON_SETUP_ROLES = ("trainer", "groom", "working_student", "horse_owner",
                    "rider", "parent", "veterinarian", "farrier")


def test_barn_manage_capability_exists():
    assert "barn:manage" in CAPABILITIES


def test_setup_roles_have_barn_manage():
    for r in SETUP_ROLES:
        assert has_capability({"role": r}, "barn:manage")


def test_non_setup_roles_lack_barn_manage():
    for r in NON_SETUP_ROLES:
        assert not has_capability({"role": r}, "barn:manage")


def test_unknown_capability_fails_closed():
    assert not has_capability({"role": "admin"}, "nonexistent:action")


def test_require_raises_403_when_denied():
    with pytest.raises(HTTPException) as exc:
        require({"role": "groom"}, "barn:manage")
    assert exc.value.status_code == 403


def test_require_passes_when_allowed():
    require({"role": "admin"}, "barn:manage")  # should not raise


def test_require_setup_role_parity_with_existing_guard():
    # admin/barn_manager pass; everyone else gets 403 — identical to today.
    for r in SETUP_ROLES:
        require_setup_role({"role": r})
    for r in NON_SETUP_ROLES:
        with pytest.raises(HTTPException) as exc:
            require_setup_role({"role": r})
        assert exc.value.status_code == 403
        assert exc.value.detail == "Owner / Barn Manager access required"


# ---------------- Phase 4C capabilities ----------------
ALL_ROLES = SETUP_ROLES + NON_SETUP_ROLES


def _assert_capability(capability, allowed_roles, message):
    allowed = set(allowed_roles)
    for r in allowed:
        require({"role": r}, capability)  # must not raise
        assert has_capability({"role": r}, capability)
    for r in [x for x in ALL_ROLES if x not in allowed]:
        assert not has_capability({"role": r}, capability)
        with pytest.raises(HTTPException) as exc:
            require({"role": r}, capability)
        assert exc.value.status_code == 403
        assert exc.value.detail == message


def test_phase4c_capabilities_registered():
    for cap in ["service_request:approve", "service_request:decline",
                "digest:read_own", "digest:admin", "admin:access"]:
        assert cap in CAPABILITIES


def test_service_request_approve_capability():
    _assert_capability("service_request:approve",
                       ("admin", "barn_manager", "trainer"),
                       "Insufficient role to approve service requests")


def test_service_request_decline_capability():
    _assert_capability("service_request:decline",
                       ("admin", "barn_manager", "trainer"),
                       "Insufficient role to decline service requests")


def test_digest_read_own_capability():
    _assert_capability("digest:read_own", ("horse_owner",), "Owner accounts only")


def test_digest_admin_capability():
    _assert_capability("digest:admin", ("admin", "barn_manager"), "Admin/Manager only")


def test_admin_access_capability():
    _assert_capability("admin:access", ("admin",), "Admin only")
