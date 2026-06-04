"""Phase 3G — `server.py` is app-assembly only.

Verifies the refactor that moved shared infrastructure into ``core/*``:
  - the FastAPI app + key routes are still registered;
  - the relocated symbols exposed by ``server`` are *identity-equal* to their
    ``core`` definitions (i.e. server imports them, it does not redefine them);
  - the dead auth duplicates were removed from ``server.py``.

This is an import-level unit test (no live server needed). Importing ``server``
does NOT trigger the startup loops (those fire on the ASGI ``startup`` event).
"""
import core.analytics as core_analytics
import core.auth as core_auth
import core.db as core_db
import core.helpers as core_helpers
import core.urls as core_urls
import server


def test_app_exists_and_titled():
    from fastapi import FastAPI

    assert isinstance(server.app, FastAPI)
    assert server.app.title == "EquineSync API"


def test_relocated_symbols_are_core_definitions():
    # server must IMPORT these from core, not redefine them inline.
    assert server.get_current_user is core_auth.get_current_user
    assert server.create_token is core_auth.create_token
    assert server.hash_pwd is core_auth.hash_pwd
    assert server.require_setup_role is core_auth.require_setup_role
    assert server._track is core_analytics._track
    assert server._base_url is core_urls._base_url
    assert server.new_id is core_helpers.new_id
    assert server.list_collection is core_helpers.list_collection
    assert server.db is core_db.db


def test_dead_auth_models_removed_from_server():
    # Dead duplicates (owned by routes/auth.py) were deleted in 3G.
    for sym in ("UserCreate", "LoginBody", "RefreshBody", "verify_pwd"):
        assert not hasattr(server, sym), f"{sym} should be removed from server.py"


def test_key_routes_registered():
    paths = {getattr(r, "path", "") for r in server.app.routes}
    assert "/api/health" in paths
    assert any(p.startswith("/api/horses") for p in paths)
    assert any(p.startswith("/api/invoices") for p in paths)
    assert any("/auth/login" in p for p in paths)


def test_lifecycle_handlers_registered():
    # register_lifecycle attached one startup and one shutdown handler.
    assert len(server.app.router.on_startup) >= 1
    assert len(server.app.router.on_shutdown) >= 1
