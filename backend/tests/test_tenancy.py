"""Phase 4A — core.tenancy helper unit tests (pure, no DB / no live server)."""
from core.tenancy import (
    PRIMARY_BARN_ID,
    barn_filter,
    resolve_barn_id,
    stamp_barn,
)


def test_primary_constant():
    assert PRIMARY_BARN_ID == "primary"


def test_resolve_present():
    assert resolve_barn_id({"barn_id": "b1"}) == "b1"


def test_resolve_missing_defaults_primary():
    assert resolve_barn_id({"id": "u", "role": "groom"}) == "primary"


def test_resolve_empty_defaults_primary():
    assert resolve_barn_id({"barn_id": ""}) == "primary"


def test_resolve_none_user_defaults_primary():
    assert resolve_barn_id(None) == "primary"


def test_barn_filter_merges_extra():
    assert barn_filter({"barn_id": "b1"}, {"status": "open"}) == {
        "barn_id": "b1", "status": "open"}


def test_barn_filter_extra_cannot_override_barn_id():
    # Hardening: a conflicting extra["barn_id"] must be ignored, not honored.
    out = barn_filter({"barn_id": "b1"}, {"barn_id": "evil", "status": "open"})
    assert out["barn_id"] == "b1"
    assert out["status"] == "open"


def test_barn_filter_extra_override_with_missing_user_barn():
    # Even when the user has no barn (=> primary), extra cannot replace it.
    out = barn_filter({"role": "groom"}, {"barn_id": "evil"})
    assert out["barn_id"] == "primary"


def test_barn_filter_no_extra():
    assert barn_filter({"barn_id": "b2"}) == {"barn_id": "b2"}


def test_barn_filter_missing_user_barn():
    assert barn_filter({"role": "groom"}) == {"barn_id": "primary"}


def test_stamp_barn_sets_field():
    doc = {"name": "Valentino"}
    out = stamp_barn({"barn_id": "b1"}, doc)
    assert out is doc
    assert doc["barn_id"] == "b1"


def test_stamp_barn_normalizes_to_caller():
    doc = {"barn_id": "other"}
    stamp_barn({"barn_id": "b1"}, doc)
    assert doc["barn_id"] == "b1"


def test_stamp_barn_defaults_primary():
    doc = {}
    stamp_barn({"role": "admin"}, doc)
    assert doc["barn_id"] == "primary"
