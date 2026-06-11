"""Phase 10A — centralized structured logging + request correlation.

Provides:
  * per-request correlation `contextvars` (`request_id`, `user_id`, `barn_id`)
  * a `ContextFilter` that injects those onto every `LogRecord`
  * a `RedactionFilter` that scrubs secrets/tokens from `record.msg` /
    `record.args` **before** formatting (backstop only — the primary defense is
    never passing sensitive data to loggers)
  * JSON (production default) and human-readable plain (dev default) formatters
  * `configure_logging()` to wire the root logger

This module is observability-only. It never persists anything, never writes the
`audit_log` collection, and emits no audit events — audit logging
(`core/audit.py`) remains the sole compliance trail.
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone

from core.config import is_production

# ---------------------------------------------------------------- context vars
request_id_var: contextvars.ContextVar = contextvars.ContextVar("request_id", default=None)
user_id_var: contextvars.ContextVar = contextvars.ContextVar("user_id", default=None)
barn_id_var: contextvars.ContextVar = contextvars.ContextVar("barn_id", default=None)

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def sanitize_request_id(raw) -> str:
    """Accept a caller-supplied id only if safely bounded; else generate one."""
    if isinstance(raw, str) and _REQUEST_ID_RE.match(raw):
        return raw
    return uuid.uuid4().hex


def set_user_context(user_id=None, barn_id=None) -> None:
    """Best-effort, exception-safe correlation setter (used by get_current_user).

    Stores ONLY the opaque user id + barn id — never email/token/headers/the
    full user document. Failures are swallowed so this can never affect auth.
    """
    try:
        if user_id is not None:
            user_id_var.set(user_id)
        if barn_id is not None:
            barn_id_var.set(barn_id)
    except Exception:
        pass


# ---------------------------------------------------------------- redaction
_SENSITIVE = "password|token|secret|authorization|credential|apikey|jwt|hash"
_KV_RE = re.compile(
    r"(?i)\b([A-Za-z0-9_-]*(?:" + _SENSITIVE + r")[A-Za-z0-9_-]*)\s*[=:]\s*\"?([^\s,;\"]+)\"?"
)
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9._\-]{10,}")
_REDACTED = "[REDACTED]"


def _redact_text(s: str) -> str:
    s = _KV_RE.sub(lambda m: f"{m.group(1)}={_REDACTED}", s)
    s = _BEARER_RE.sub("Bearer " + _REDACTED, s)
    s = _JWT_RE.sub(_REDACTED, s)
    return s


def _redact_value(v):
    return _redact_text(v) if isinstance(v, str) else v


class RedactionFilter(logging.Filter):
    """Scrub sensitive fragments from `record.msg` / `record.args` pre-format."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            if isinstance(record.msg, str):
                record.msg = _redact_text(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {k: _redact_value(v) for k, v in record.args.items()}
                else:
                    record.args = tuple(_redact_value(a) for a in record.args)
        except Exception:
            pass
        return True


class ContextFilter(logging.Filter):
    """Inject per-request correlation ids onto every record."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        record.barn_id = barn_id_var.get()
        return True


# ---------------------------------------------------------------- formatters
_EXTRA_FIELDS = ("method", "path", "status_code", "duration_ms")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "user_id": getattr(record, "user_id", None),
            "barn_id": getattr(record, "barn_id", None),
        }
        for f in _EXTRA_FIELDS:
            val = getattr(record, f, None)
            if val is not None:
                base[f] = val
        if record.exc_info:
            base["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            base["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(base, default=str)


class PlainFormatter(logging.Formatter):
    """Human-readable dev format that still surfaces correlation fields."""

    def __init__(self):
        super().__init__("%(asctime)s %(levelname)s %(name)s %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        extras = []
        rid = getattr(record, "request_id", None)
        if rid:
            extras.append(f"rid={rid}")
        uid = getattr(record, "user_id", None)
        if uid:
            extras.append(f"user={uid}")
        bid = getattr(record, "barn_id", None)
        if bid:
            extras.append(f"barn={bid}")
        for f in _EXTRA_FIELDS:
            v = getattr(record, f, None)
            if v is not None:
                extras.append(f"{f}={v}")
        return f"{msg} | {' '.join(extras)}" if extras else msg


def resolve_log_format(env=None) -> str:
    e = os.environ if env is None else env
    fmt = (e.get("LOG_FORMAT") or "").strip().lower()
    if fmt in ("json", "plain"):
        return fmt
    return "json" if is_production(e) else "plain"


def configure_logging() -> None:
    """Wire the root logger with context + redaction filters and a formatter."""
    level = (os.environ.get("LOG_LEVEL", "INFO") or "INFO").upper()
    formatter = JsonFormatter() if resolve_log_format() == "json" else PlainFormatter()

    handler = logging.StreamHandler()
    handler.addFilter(ContextFilter())
    handler.addFilter(RedactionFilter())
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
