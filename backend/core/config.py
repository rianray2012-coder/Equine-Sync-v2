"""Centralized environment configuration & validation.

Phase 2A security hardening (see /app/docs/PHASED_EXECUTION_PLAN.md and
/app/docs/KNOWN_TECH_DEBT.md item #1 "JWT Secret Fallback").

Single source of truth for security-critical settings. Behaviour:

- **Production** (`APP_ENV=production`): startup FAILS FAST when required
  variables are missing or when JWT_SECRET is missing/insecure. No fallbacks.
- **Development** (default): preserves usability. If JWT_SECRET is missing or
  insecure, an EPHEMERAL per-process secret is generated and a clear warning
  is logged (tokens won't survive a restart).

The helper functions accept an explicit ``env`` mapping so they can be unit
tested without mutating the real process environment.
"""
from __future__ import annotations

import logging
import os
import secrets
from typing import Mapping, Optional

logger = logging.getLogger("equinesync.config")

JWT_ALG = "HS256"

# Required in every environment — the app cannot function without these.
REQUIRED_VARS = ("MONGO_URL", "DB_NAME")
# Additionally required when running in production.
PRODUCTION_REQUIRED_VARS = ("JWT_SECRET",)

# Values that must never be accepted as a real signing secret.
_INSECURE_SECRETS = {
    "", "change-me", "changeme", "secret", "dev", "development", "test", "password",
}
_MIN_SECRET_LEN = 16


class ConfigError(RuntimeError):
    """Raised when configuration is invalid or unsafe for the environment."""


def _env(env: Optional[Mapping[str, str]]) -> Mapping[str, str]:
    return os.environ if env is None else env


def is_production(env: Optional[Mapping[str, str]] = None) -> bool:
    e = _env(env)
    return (e.get("APP_ENV") or "development").strip().lower() in ("production", "prod")


def _is_insecure_secret(raw: str) -> bool:
    s = raw.strip()
    return s.lower() in _INSECURE_SECRETS or len(s) < _MIN_SECRET_LEN


def resolve_jwt_secret(env: Optional[Mapping[str, str]] = None) -> str:
    """Resolve the JWT signing secret.

    - Returns the configured ``JWT_SECRET`` when present and strong.
    - Production: raises :class:`ConfigError` if missing/insecure (fail fast).
    - Development: returns an ephemeral per-process secret with a warning.
    """
    e = _env(env)
    raw = (e.get("JWT_SECRET") or "").strip()
    if not _is_insecure_secret(raw):
        return raw
    if is_production(e):
        raise ConfigError(
            "JWT_SECRET is missing or insecure. Set a strong JWT_SECRET "
            "(>= 16 chars, not a placeholder like 'change-me') before starting "
            "EquineSync in production."
        )
    logger.warning(
        "JWT_SECRET is missing or insecure in development; using an EPHEMERAL "
        "secret generated for this process only. Sessions will be invalidated "
        "on restart. Set JWT_SECRET in backend/.env for stable dev sessions."
    )
    return secrets.token_urlsafe(48)


def validate_config(env: Optional[Mapping[str, str]] = None) -> None:
    """Validate required configuration; raise :class:`ConfigError` on fatal issues.

    Call once at application startup. In production this also enforces JWT
    secret strength (delegating to :func:`resolve_jwt_secret`) and rejects a
    wildcard CORS policy (delegating to :func:`get_cors_origins`).
    """
    e = _env(env)
    missing = [v for v in REQUIRED_VARS if not (e.get(v) or "").strip()]
    if missing:
        raise ConfigError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
    if is_production(e):
        prod_missing = [
            v for v in PRODUCTION_REQUIRED_VARS if not (e.get(v) or "").strip()
        ]
        if prod_missing:
            raise ConfigError(
                "Missing required production environment variables: "
                f"{', '.join(prod_missing)}"
            )
        # Raises in production if the secret is weak/placeholder.
        resolve_jwt_secret(e)
        # Raises in production if CORS is unset or wildcard.
        get_cors_origins(e)
    logger.info("Configuration validated (production=%s)", is_production(e))


# ---------------- CORS ----------------

def get_cors_origins(env: Optional[Mapping[str, str]] = None) -> list[str]:
    """Resolve allowed CORS origins from ``CORS_ORIGINS`` (comma-separated).

    - Production: a wildcard (``*``) or empty value is rejected with
      :class:`ConfigError` — explicit origins are mandatory.
    - Development: defaults to ``["*"]`` when unset to preserve local usability.
    """
    e = _env(env)
    raw = (e.get("CORS_ORIGINS") or "").strip()
    if is_production(e):
        if not raw or raw == "*":
            raise ConfigError(
                "CORS_ORIGINS must be set to explicit origin(s) in production; "
                "'*' is not allowed (security)."
            )
        return [o.strip() for o in raw.split(",") if o.strip()]
    if not raw:
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


# ---------------- Rate limiting ----------------

def rate_limit_enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    """Whether request rate limiting is active (default: enabled)."""
    e = _env(env)
    return (e.get("RATE_LIMIT_ENABLED") or "true").strip().lower() in (
        "1", "true", "yes", "on",
    )


def auth_rate_limit(env: Optional[Mapping[str, str]] = None) -> str:
    """Rate-limit string for auth-sensitive endpoints (slowapi format).

    Honors an explicit ``AUTH_RATE_LIMIT`` override. Otherwise defaults to a
    strict limit in production and a generous one in development so local use
    and the HTTP integration test suite are not throttled.
    """
    e = _env(env)
    explicit = (e.get("AUTH_RATE_LIMIT") or "").strip()
    if explicit:
        return explicit
    return "5/minute" if is_production(e) else "1000/minute"


# Active signing secret, resolved at import time. server.py loads .env before
# importing this module, so os.environ is fully populated here.
JWT_SECRET = resolve_jwt_secret()


# ---------------- email verification & links (Phase 2C) ----------------

def app_base_url(env: Optional[Mapping[str, str]] = None) -> str:
    """Public base URL used to build email links (no trailing slash)."""
    e = _env(env)
    return (e.get("APP_BASE_URL") or e.get("PUBLIC_APP_URL") or "").strip().rstrip("/")


def enforce_email_verification(env: Optional[Mapping[str, str]] = None) -> bool:
    """Whether unverified users are blocked at login (default: False — no lockout)."""
    e = _env(env)
    return (e.get("ENFORCE_EMAIL_VERIFICATION") or "false").strip().lower() in (
        "1", "true", "yes", "on",
    )


def email_verify_ttl_hours(env: Optional[Mapping[str, str]] = None) -> int:
    e = _env(env)
    try:
        return int(e.get("EMAIL_VERIFY_TTL_HOURS") or "48")
    except ValueError:
        return 48


def password_reset_ttl_hours(env: Optional[Mapping[str, str]] = None) -> int:
    e = _env(env)
    try:
        return int(e.get("PASSWORD_RESET_TTL_HOURS") or "1")
    except ValueError:
        return 1


# ---------------- brute-force lockout (Phase 2D) ----------------

def login_lockout_enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    e = _env(env)
    return (e.get("LOGIN_LOCKOUT_ENABLED") or "true").strip().lower() in (
        "1", "true", "yes", "on",
    )


def login_max_attempts(env: Optional[Mapping[str, str]] = None) -> int:
    e = _env(env)
    try:
        return max(1, int(e.get("LOGIN_MAX_ATTEMPTS") or "5"))
    except ValueError:
        return 5


def login_lockout_minutes(env: Optional[Mapping[str, str]] = None) -> int:
    e = _env(env)
    try:
        return max(1, int(e.get("LOGIN_LOCKOUT_MINUTES") or "15"))
    except ValueError:
        return 15


def login_attempt_window_minutes(env: Optional[Mapping[str, str]] = None) -> int:
    e = _env(env)
    try:
        return max(1, int(e.get("LOGIN_ATTEMPT_WINDOW_MINUTES") or "15"))
    except ValueError:
        return 15
