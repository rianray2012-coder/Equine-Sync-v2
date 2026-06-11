"""Phase 10A — structured logging + request correlation.

Unit tests (no live server) for the request-id sanitizer, redaction filter, and
JSON formatter, plus pure-ASGI middleware tests (driven directly with
asyncio.run, mirroring test_dispatch_retry.py — no pytest-asyncio dependency)
that prove:
  * an additive X-Request-ID header (valid incoming echoed, bad incoming -> generated)
  * the request-completion log for an AUTHENTICATED request carries user_id/barn_id
    set downstream (proves contextvar propagation through pure ASGI)
  * an unauthenticated request does NOT inherit prior user/barn context (no leak)
"""
import asyncio
import json
import logging

from core import logging_config as lc
from core.middleware import RequestContextMiddleware


# ----------------------------------------------------------------- unit: sanitize

def test_sanitize_request_id_accepts_valid():
    assert lc.sanitize_request_id("abc-123_DEF.4") == "abc-123_DEF.4"


def test_sanitize_request_id_rejects_invalid_and_generates():
    for bad in ["has spaces", "a" * 65, "bad/slash", "", None, 123]:
        out = lc.sanitize_request_id(bad)
        assert lc._REQUEST_ID_RE.match(out)  # always a safe id
        assert out != bad


# ----------------------------------------------------------------- unit: redaction

def test_redaction_scrubs_msg_kv():
    rec = logging.LogRecord("n", logging.INFO, "p", 1, "user token=abc123secret done", None, None)
    lc.RedactionFilter().filter(rec)
    assert "abc123secret" not in rec.getMessage()
    assert "[REDACTED]" in rec.getMessage()


def test_redaction_scrubs_args_bearer_and_jwt():
    rec = logging.LogRecord("n", logging.INFO, "p", 1, "auth %s", ("Bearer eyJabcDEF1234567890",), None)
    lc.RedactionFilter().filter(rec)
    out = rec.getMessage()
    assert "eyJabcDEF1234567890" not in out
    assert "[REDACTED]" in out


# ----------------------------------------------------------------- unit: formatter

def test_json_formatter_includes_fields():
    rec = logging.LogRecord("n", logging.INFO, "p", 1, "hi", None, None)
    rec.request_id, rec.user_id, rec.barn_id = "r1", "u1", "b1"
    rec.method, rec.path, rec.status_code, rec.duration_ms = "GET", "/x", 200, 1.23
    out = json.loads(lc.JsonFormatter().format(rec))
    assert out["request_id"] == "r1" and out["user_id"] == "u1" and out["barn_id"] == "b1"
    assert out["method"] == "GET" and out["path"] == "/x" and out["status_code"] == 200


def test_resolve_log_format_override():
    assert lc.resolve_log_format({"LOG_FORMAT": "json"}) == "json"
    assert lc.resolve_log_format({"LOG_FORMAT": "plain"}) == "plain"
    assert lc.resolve_log_format({"APP_ENV": "development"}) == "plain"


# ----------------------------------------------------------------- middleware harness

class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.addFilter(lc.ContextFilter())  # so records carry the contextvars
        self.records = []

    def emit(self, record):
        self.records.append(record)


def _drive(app_inner, incoming_id=None):
    """Run one HTTP request through the middleware; return (sent_messages, records)."""
    headers = [(b"x-request-id", incoming_id.encode())] if incoming_id else []
    scope = {"type": "http", "method": "GET", "path": "/x", "headers": headers}
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    cap = _Capture()
    mw_logger = logging.getLogger("equinesync.request")
    mw_logger.addHandler(cap)
    old_level = mw_logger.level
    mw_logger.setLevel(logging.INFO)
    try:
        asyncio.run(RequestContextMiddleware(app_inner)(scope, receive, send))
    finally:
        mw_logger.removeHandler(cap)
        mw_logger.setLevel(old_level)
    return sent, cap.records


async def _app_authed(scope, receive, send):
    # Simulate get_current_user setting correlation context downstream.
    lc.set_user_context(user_id="u-123", barn_id="barn-A")
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


async def _app_anon(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def _header(sent, name):
    start = next(m for m in sent if m["type"] == "http.response.start")
    for k, v in start["headers"]:
        if k.lower() == name.encode():
            return v.decode()
    return None


def _completion(records):
    return next(r for r in records if r.getMessage() == "request completed")


def test_x_request_id_generated_when_absent():
    sent, _ = _drive(_app_anon)
    rid = _header(sent, "x-request-id")
    assert rid and lc._REQUEST_ID_RE.match(rid)


def test_x_request_id_echoed_when_valid():
    sent, _ = _drive(_app_anon, incoming_id="client-req-42")
    assert _header(sent, "x-request-id") == "client-req-42"


def test_x_request_id_regenerated_when_bad():
    sent, _ = _drive(_app_anon, incoming_id="bad id")  # space -> invalid
    rid = _header(sent, "x-request-id")
    assert rid != "bad id" and lc._REQUEST_ID_RE.match(rid)


def test_authenticated_completion_log_has_user_and_barn():
    _, records = _drive(_app_authed)
    rec = _completion(records)
    assert rec.user_id == "u-123"
    assert rec.barn_id == "barn-A"
    assert rec.request_id and rec.status_code == 200 and rec.method == "GET"


def test_unauthenticated_request_does_not_inherit_prior_context():
    # Authenticated request first (sets user/barn), then an anonymous one.
    _drive(_app_authed)
    _, records = _drive(_app_anon)
    rec = _completion(records)
    assert rec.user_id is None and rec.barn_id is None
