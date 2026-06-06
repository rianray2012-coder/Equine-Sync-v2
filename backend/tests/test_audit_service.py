"""Phase 5A — unit tests for the audit logging service (core/audit.py).

Pure + fake-collection tests (no live Mongo, no live API). Proves:
  * build_entry stamps id/ts/barn/actor and is barn-scoped (Phase 4 carry-over)
  * metadata redaction strips sensitive keys (nested) + truncates/caps
  * record() is fail-open (an insert error never propagates)
  * record() happy path inserts exactly one well-formed entry
  * record_denial() is a safe no-op outside a running event loop
"""
import asyncio

import pytest

from core import audit
from core.tenancy import PRIMARY_BARN_ID


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------
class _FakeColl:
    def __init__(self, raise_on_insert=False):
        self.docs = []
        self.raise_on_insert = raise_on_insert

    async def insert_one(self, doc):
        if self.raise_on_insert:
            raise RuntimeError("simulated mongo failure")
        self.docs.append(doc)
        return type("R", (), {"inserted_id": doc.get("id")})()


class _FakeDB:
    def __init__(self, raise_on_insert=False):
        self.audit_log = _FakeColl(raise_on_insert)


# --------------------------------------------------------------------------
# build_entry — stamping + barn scope
# --------------------------------------------------------------------------
def test_build_entry_stamps_actor_and_barn_from_user():
    user = {"id": "u1", "email": "Admin@Barn.com", "role": "admin", "barn_id": "barn-9"}
    e = audit.build_entry(action="invoice.paid", user=user,
                          resource_type="invoice", resource_id="inv1",
                          metadata={"total": 100})
    assert e["action"] == "invoice.paid"
    assert e["actor_user_id"] == "u1"
    assert e["actor_email"] == "admin@barn.com"   # lowercased
    assert e["actor_role"] == "admin"
    assert e["barn_id"] == "barn-9"
    assert e["resource_type"] == "invoice" and e["resource_id"] == "inv1"
    assert e["outcome"] == "success"
    assert e["metadata"] == {"total": 100}
    assert e["id"] and e["ts"]


def test_build_entry_defaults_barn_primary_and_null_actor_when_no_user():
    e = audit.build_entry(action="auth.login.failure", actor_email="ghost@x.com",
                          outcome="failure", status_code=401)
    assert e["actor_user_id"] is None
    assert e["actor_email"] == "ghost@x.com"
    assert e["barn_id"] == PRIMARY_BARN_ID
    assert e["outcome"] == "failure" and e["status_code"] == 401


def test_build_entry_resolves_barn_from_legacy_user_without_barn_id():
    # resolve_barn_id treats a missing barn_id as the primary barn (legacy-safe).
    e = audit.build_entry(action="auth.logout", user={"id": "u2", "role": "groom"})
    assert e["barn_id"] == PRIMARY_BARN_ID


def test_explicit_barn_id_overrides_user():
    user = {"id": "u1", "role": "admin", "barn_id": "barn-a"}
    e = audit.build_entry(action="x", user=user, barn_id="barn-b")
    assert e["barn_id"] == "barn-b"


# --------------------------------------------------------------------------
# Redaction
# --------------------------------------------------------------------------
def test_redaction_strips_sensitive_keys_including_nested():
    meta = {
        "email": "ok@x.com",
        "password": "hunter2",
        "refresh_token": "abc",
        "nested": {"token_hash": "deadbeef", "keep": "yes"},
        "list": [{"api_key": "k"}, {"fine": 1}],
    }
    e = audit.build_entry(action="x", metadata=meta)
    m = e["metadata"]
    assert m["email"] == "ok@x.com"
    assert m["password"] == "[redacted]"
    assert m["refresh_token"] == "[redacted]"
    assert m["nested"]["token_hash"] == "[redacted]"
    assert m["nested"]["keep"] == "yes"
    assert m["list"][0]["api_key"] == "[redacted]"
    assert m["list"][1]["fine"] == 1


def test_redaction_truncates_long_strings_and_caps_lists():
    e = audit.build_entry(action="x", metadata={"big": "a" * 1000, "arr": list(range(200))})
    assert len(e["metadata"]["big"]) == 501 and e["metadata"]["big"].endswith("…")
    assert len(e["metadata"]["arr"]) == 50


def test_redaction_catches_sensitive_key_variants_nested():
    meta = {
        "outer": {
            "resetToken": "r",
            "verificationToken": "v",
            "authorization_header": "Bearer abc",
            "apiKey": "k",
            "secretKey": "s",
            "jwt": "e.y.z",
            "session_token_id": "sid",
            "password_hash": "h",
            # legitimate keys that must SURVIVE redaction:
            "photo_url": "https://x/p.png",
            "full_name": "Jane Doe",
            "count": 3,
        }
    }
    o = audit.build_entry(action="x", metadata=meta)["metadata"]["outer"]
    for k in ("resetToken", "verificationToken", "authorization_header", "apiKey",
              "secretKey", "jwt", "session_token_id", "password_hash"):
        assert o[k] == "[redacted]", f"{k} not redacted"
    assert o["photo_url"] == "https://x/p.png"
    assert o["full_name"] == "Jane Doe"
    assert o["count"] == 3


def test_redaction_catches_token_bearing_urls_by_exact_name():
    meta = {"accept_url": "https://app/accept?token=raw", "reset_url": "https://app/r?token=x",
            "verify_url": "https://app/v?token=y", "barn_url": "https://app/barn"}
    m = audit.build_entry(action="x", metadata=meta)["metadata"]
    assert m["accept_url"] == "[redacted]"
    assert m["reset_url"] == "[redacted]"
    assert m["verify_url"] == "[redacted]"
    assert m["barn_url"] == "https://app/barn"  # not token-bearing → kept


# --------------------------------------------------------------------------
# record() — fail-open + happy path
# --------------------------------------------------------------------------
def test_record_is_fail_open_on_insert_error():
    fake = _FakeDB(raise_on_insert=True)
    # Must NOT raise even though the underlying insert blows up.
    asyncio.run(audit.record(action="invoice.paid", barn_id="b1", _db=fake))
    assert fake.audit_log.docs == []


def test_record_happy_path_inserts_one_entry():
    fake = _FakeDB()
    user = {"id": "u1", "email": "a@b.com", "role": "admin", "barn_id": "b1"}
    asyncio.run(audit.record(action="service_request.approved", user=user,
                             resource_type="service_request", resource_id="sr1",
                             _db=fake))
    assert len(fake.audit_log.docs) == 1
    doc = fake.audit_log.docs[0]
    assert doc["action"] == "service_request.approved"
    assert doc["actor_user_id"] == "u1" and doc["barn_id"] == "b1"
    assert doc["resource_id"] == "sr1"


# --------------------------------------------------------------------------
# record_denial() — safe no-op without a running loop
# --------------------------------------------------------------------------
def test_record_denial_no_running_loop_is_noop():
    # No event loop running here → must return without raising.
    audit.record_denial({"id": "u1", "role": "groom", "barn_id": "b1"},
                        "admin:access", "Admin only")


def test_record_denial_schedules_write_on_running_loop():
    fake = _FakeDB()

    async def _run():
        # Patch the module db so the scheduled task writes to our fake.
        original = audit.db
        audit.__dict__["db"] = fake
        try:
            audit.record_denial({"id": "u1", "role": "groom", "barn_id": "b1"},
                                "admin:access", "Admin only")
            # Let the fire-and-forget task run.
            await asyncio.sleep(0.05)
        finally:
            audit.__dict__["db"] = original
        return fake.audit_log.docs

    docs = asyncio.run(_run())
    assert len(docs) == 1
    assert docs[0]["action"] == "permission.denied"
    assert docs[0]["outcome"] == "denied"
    assert docs[0]["resource_id"] == "admin:access"


# --------------------------------------------------------------------------
# ensure_audit_indexes() — requests the expected three indexes
# --------------------------------------------------------------------------
class _IdxColl:
    def __init__(self):
        self.requested = []

    async def create_index(self, spec):
        self.requested.append(spec)


class _IdxDB:
    def __init__(self):
        self.audit_log = _IdxColl()


def test_ensure_audit_indexes_requests_expected_three():
    fake = _IdxDB()
    asyncio.run(audit.ensure_audit_indexes(fake))
    assert fake.audit_log.requested == [
        [("barn_id", 1), ("ts", -1)],
        [("action", 1), ("ts", -1)],
        [("actor_user_id", 1), ("ts", -1)],
    ]
