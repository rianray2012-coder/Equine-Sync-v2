"""Phase 3G — core.auth.get_current_user email-verification gate (Security Patch 2E).

Unit-tests the relocated ``get_current_user`` dependency in isolation (fake DB,
real JWT) to prove the Security Patch 2E defense-in-depth behavior is preserved
after moving out of ``server.py``:

  - ENFORCE_EMAIL_VERIFICATION on + ``email_verified=False`` -> 403 (blocked)
  - ENFORCE_EMAIL_VERIFICATION on + ``email_verified=True``  -> passes
  - ENFORCE_EMAIL_VERIFICATION on + field missing            -> passes (legacy-safe)
  - ENFORCE_EMAIL_VERIFICATION off + unverified              -> passes
  - missing credentials                                      -> 401
  - unknown user                                             -> 401
"""
import asyncio

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import core.auth as core_auth


class _FakeUsers:
    def __init__(self, user):
        self._user = user

    async def find_one(self, *args, **kwargs):
        return self._user


class _FakeDB:
    def __init__(self, user):
        self.users = _FakeUsers(user)


def _creds_for(user_id, role="horse_owner"):
    token = core_auth.create_token(user_id, role)
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _run(coro):
    return asyncio.run(coro)


def test_enforced_unverified_is_blocked(monkeypatch):
    monkeypatch.setenv("ENFORCE_EMAIL_VERIFICATION", "true")
    monkeypatch.setattr(core_auth, "db", _FakeDB(
        {"id": "u1", "role": "horse_owner", "email_verified": False}))
    with pytest.raises(HTTPException) as exc:
        _run(core_auth.get_current_user(_creds_for("u1")))
    assert exc.value.status_code == 403


def test_enforced_verified_passes(monkeypatch):
    monkeypatch.setenv("ENFORCE_EMAIL_VERIFICATION", "true")
    monkeypatch.setattr(core_auth, "db", _FakeDB(
        {"id": "u2", "role": "horse_owner", "email_verified": True}))
    out = _run(core_auth.get_current_user(_creds_for("u2")))
    assert out["id"] == "u2"


def test_enforced_missing_field_treated_verified(monkeypatch):
    monkeypatch.setenv("ENFORCE_EMAIL_VERIFICATION", "true")
    monkeypatch.setattr(core_auth, "db", _FakeDB({"id": "u3", "role": "groom"}))
    out = _run(core_auth.get_current_user(_creds_for("u3", "groom")))
    assert out["id"] == "u3"


def test_disabled_allows_unverified(monkeypatch):
    monkeypatch.setenv("ENFORCE_EMAIL_VERIFICATION", "false")
    monkeypatch.setattr(core_auth, "db", _FakeDB(
        {"id": "u4", "role": "rider", "email_verified": False}))
    out = _run(core_auth.get_current_user(_creds_for("u4", "rider")))
    assert out["id"] == "u4"


def test_no_credentials_401():
    with pytest.raises(HTTPException) as exc:
        _run(core_auth.get_current_user(None))
    assert exc.value.status_code == 401


def test_unknown_user_401(monkeypatch):
    monkeypatch.setattr(core_auth, "db", _FakeDB(None))
    with pytest.raises(HTTPException) as exc:
        _run(core_auth.get_current_user(_creds_for("ghost")))
    assert exc.value.status_code == 401


# ---------------- Phase 4A: barn_id is attached by both auth paths ----------------

def test_core_auth_attaches_default_barn_id(monkeypatch):
    monkeypatch.setattr(core_auth, "db", _FakeDB({"id": "u", "role": "groom"}))
    out = _run(core_auth.get_current_user(_creds_for("u", "groom")))
    assert out["barn_id"] == "primary"


def test_core_auth_attaches_explicit_barn_id(monkeypatch):
    monkeypatch.setattr(core_auth, "db", _FakeDB(
        {"id": "u", "role": "groom", "barn_id": "b9"}))
    out = _run(core_auth.get_current_user(_creds_for("u", "groom")))
    assert out["barn_id"] == "b9"


def test_routes_auth_path_attaches_barn_id():
    # The second auth implementation in routes/auth.py must mirror core.auth.
    from routes.auth import make_current_user_dependency, create_token as routes_create_token

    dep = make_current_user_dependency(_FakeDB({"id": "u", "role": "groom"}))
    token = routes_create_token("u", "groom")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    out = _run(dep(creds))
    assert out["barn_id"] == "primary"
