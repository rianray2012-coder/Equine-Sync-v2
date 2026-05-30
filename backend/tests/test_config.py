"""Unit tests for centralized config & startup validation (Phase 2A).

These are pure-function tests using explicit ``env`` mappings — they do not
touch the real process environment or hit the running server.
"""
import pytest

from config import (
    ConfigError,
    is_production,
    resolve_jwt_secret,
    validate_config,
)

STRONG_SECRET = "a" * 46  # mimics the 46-char production-style secret

BASE_ENV = {"MONGO_URL": "mongodb://localhost:27017", "DB_NAME": "equinesync"}


# ---------------- is_production ----------------

def test_is_production_defaults_to_development():
    assert is_production({}) is False
    assert is_production({"APP_ENV": "development"}) is False


@pytest.mark.parametrize("val", ["production", "PROD", " Production "])
def test_is_production_true_variants(val):
    assert is_production({"APP_ENV": val}) is True


# ---------------- resolve_jwt_secret ----------------

def test_resolve_returns_strong_secret_unchanged():
    env = {**BASE_ENV, "JWT_SECRET": STRONG_SECRET}
    assert resolve_jwt_secret(env) == STRONG_SECRET


@pytest.mark.parametrize("bad", ["", "change-me", "secret", "short", "dev"])
def test_resolve_rejects_insecure_secret_in_production(bad):
    env = {**BASE_ENV, "APP_ENV": "production", "JWT_SECRET": bad}
    with pytest.raises(ConfigError):
        resolve_jwt_secret(env)


def test_resolve_generates_ephemeral_secret_in_development():
    env = {**BASE_ENV, "JWT_SECRET": "change-me"}  # insecure but dev
    secret = resolve_jwt_secret(env)
    assert secret and secret != "change-me"
    assert len(secret) >= 16


def test_resolve_missing_secret_in_development_does_not_raise():
    env = dict(BASE_ENV)  # no JWT_SECRET
    secret = resolve_jwt_secret(env)
    assert len(secret) >= 16


# ---------------- validate_config ----------------

def test_validate_passes_with_valid_dev_env():
    validate_config({**BASE_ENV, "JWT_SECRET": STRONG_SECRET})


def test_validate_passes_with_valid_production_env():
    validate_config({**BASE_ENV, "APP_ENV": "production", "JWT_SECRET": STRONG_SECRET})


@pytest.mark.parametrize("missing", ["MONGO_URL", "DB_NAME"])
def test_validate_raises_when_required_var_missing(missing):
    env = {**BASE_ENV, "JWT_SECRET": STRONG_SECRET}
    env.pop(missing)
    with pytest.raises(ConfigError):
        validate_config(env)


def test_validate_production_requires_strong_jwt_secret():
    env = {**BASE_ENV, "APP_ENV": "production", "JWT_SECRET": "change-me"}
    with pytest.raises(ConfigError):
        validate_config(env)


def test_validate_production_requires_jwt_secret_present():
    env = {**BASE_ENV, "APP_ENV": "production"}  # no JWT_SECRET
    with pytest.raises(ConfigError):
        validate_config(env)
