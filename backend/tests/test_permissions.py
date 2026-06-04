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
