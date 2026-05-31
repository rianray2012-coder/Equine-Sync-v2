"""Unit tests for one-time auth token logic (Phase 2C).

Uses an in-memory fake db so token generation, single-use, expiry, wrong-purpose
and invalid-token handling are tested deterministically without MongoDB.
"""
import asyncio

import pytest

from core.auth_tokens import (
    PURPOSE_EMAIL_VERIFY,
    PURPOSE_PASSWORD_RESET,
    consume_token,
    issue_token,
)


class _FakeCollection:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def find_one(self, query, projection=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                return dict(d)
        return None

    async def update_one(self, query, update):
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                d.update(update.get("$set", {}))
                return


class _FakeDB:
    def __init__(self):
        self.auth_tokens = _FakeCollection()


def _run(coro):
    return asyncio.run(coro)


def test_issue_and_consume_success():
    db = _FakeDB()
    raw = _run(issue_token(db, "u1", PURPOSE_PASSWORD_RESET, 1))
    rec = _run(consume_token(db, raw, PURPOSE_PASSWORD_RESET))
    assert rec is not None
    assert rec["user_id"] == "u1"


def test_token_is_single_use():
    db = _FakeDB()
    raw = _run(issue_token(db, "u1", PURPOSE_PASSWORD_RESET, 1))
    assert _run(consume_token(db, raw, PURPOSE_PASSWORD_RESET)) is not None
    # second use rejected
    assert _run(consume_token(db, raw, PURPOSE_PASSWORD_RESET)) is None


def test_expired_token_rejected():
    db = _FakeDB()
    raw = _run(issue_token(db, "u1", PURPOSE_PASSWORD_RESET, -1))  # already expired
    assert _run(consume_token(db, raw, PURPOSE_PASSWORD_RESET)) is None


def test_wrong_purpose_rejected():
    db = _FakeDB()
    raw = _run(issue_token(db, "u1", PURPOSE_EMAIL_VERIFY, 1))
    assert _run(consume_token(db, raw, PURPOSE_PASSWORD_RESET)) is None


@pytest.mark.parametrize("bad", ["", "not-a-real-token"])
def test_invalid_token_rejected(bad):
    db = _FakeDB()
    assert _run(consume_token(db, bad, PURPOSE_PASSWORD_RESET)) is None


def test_tokens_are_hashed_at_rest():
    db = _FakeDB()
    raw = _run(issue_token(db, "u1", PURPOSE_EMAIL_VERIFY, 1))
    stored = db.auth_tokens.docs[0]
    assert raw not in stored.values()
    assert stored["token_hash"] != raw
