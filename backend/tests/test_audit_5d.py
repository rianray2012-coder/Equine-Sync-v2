"""Phase 5D — audit log read API tests (GET /api/audit-logs).

Live API + Mongo. Proves access control (audit:read = admin/barn_manager),
barn-scoped reads in BOTH directions, filtering, limit/offset pagination with
total, the single `audit_logs.view` event per request (no recursion / no
duplicate permission.denied on a denied read), and limit clamping.

Seeded rows carry metadata.test_run=RUN so teardown deletes exactly them; all
`audit_logs.view` rows in the run window are this file's (only this test hits
the endpoint) and are purged too.
"""
import os
import pathlib
import time
import uuid
from datetime import datetime, timezone, timedelta

import pymongo
import requests

from ._test_creds import ADMIN, OWNER, GROOM

PW = "Passw0rd!9"
RUN = uuid.uuid4().hex


def _read_env(key, parents, sub):
    envf = pathlib.Path(__file__).resolve().parents[parents] / sub
    for line in envf.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or _read_env("REACT_APP_BACKEND_URL", 2, "frontend/.env")).rstrip("/")
API = f"{BASE_URL}/api"


def mongo():
    url = os.environ.get("MONGO_URL") or _read_env("MONGO_URL", 1, ".env")
    name = os.environ.get("DB_NAME") or _read_env("DB_NAME", 1, ".env")
    return pymongo.MongoClient(url)[name]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


STATE = {"emails": set(), "barn_ids": set(), "invite_ids": set(), "start_ts": None, "ts": []}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    return r.json()


def _seed(barn_id, action, **fields):
    doc = {
        "id": str(uuid.uuid4()),
        "ts": fields.pop("ts", datetime.now(timezone.utc).isoformat()),
        "barn_id": barn_id,
        "actor_user_id": fields.pop("actor_user_id", "u-5d"),
        "actor_email": fields.pop("actor_email", None),
        "actor_role": "admin",
        "action": action,
        "resource_type": fields.pop("resource_type", "thing"),
        "resource_id": fields.pop("resource_id", "res-1"),
        "outcome": fields.pop("outcome", "success"),
        "status_code": 200,
        "ip": None, "user_agent": None,
        "metadata": {"test_run": RUN},
    }
    mongo().audit_log.insert_one(doc)
    return doc["id"]


def setup_module(module):
    STATE["start_ts"] = datetime.now(timezone.utc).isoformat()
    base = datetime.now(timezone.utc)
    ts = [(base + timedelta(seconds=i)).isoformat() for i in range(6)]
    STATE["ts"] = ts
    # primary: 6 alpha (res-1, u-5d), 2 beta (failure, u-5d-2, res-2), 1 gamma (actor_email)
    for i in range(6):
        _seed("primary", "test5d.alpha", ts=ts[i])
    for _ in range(2):
        _seed("primary", "test5d.beta", outcome="failure", actor_user_id="u-5d-2", resource_id="res-2")
    _seed("primary", "test5d.gamma", actor_email="filterme5d@ex.com")


def teardown_module(module):
    db = mongo()
    db.audit_log.delete_many({"metadata.test_run": RUN})
    db.audit_log.delete_many({"action": "audit_logs.view", "ts": {"$gte": STATE["start_ts"]}})
    if STATE["invite_ids"]:
        inv_ids = list(STATE["invite_ids"])
        db.invites.delete_many({"id": {"$in": inv_ids}})
        # invite lifecycle audit rows (actor = shared admin) keyed by invite id
        db.audit_log.delete_many({"resource_id": {"$in": inv_ids}, "ts": {"$gte": STATE["start_ts"]}})
    emails = list(STATE["emails"])
    if emails:
        uids = [u["id"] for u in db.users.find({"email": {"$in": emails}}, {"_id": 0, "id": 1})]
        if uids:
            db.onboarding_progress.delete_many({"user_id": {"$in": uids}})
        db.users.delete_many({"email": {"$in": emails}})
        db.audit_log.delete_many({"actor_email": {"$in": emails}, "ts": {"$gte": STATE["start_ts"]}})
    for bid in STATE["barn_ids"]:
        db.barn.delete_many({"id": bid})
        db.users.delete_many({"barn_id": bid})
        db.onboarding_progress.delete_many({"barn_id": bid})


def _get(token, **params):
    return requests.get(f"{API}/audit-logs", params=params, headers=_headers(token), timeout=30)


def _accept_invite_user(role):
    """Create a real user with `role` via admin invite + accept; return login json."""
    admin = _login(ADMIN["email"], ADMIN["password"])
    email = f"audit5d_{role}_{uuid.uuid4().hex[:8]}@ex.com"
    STATE["emails"].add(email)
    cr = requests.post(f"{API}/invites", json={"email": email, "role": role, "full_name": role},
                       headers=_headers(admin["token"]), timeout=30)
    assert cr.status_code == 200, cr.text
    STATE["invite_ids"].add(cr.json()["id"])
    token = cr.json()["dev_accept_url"].split("token=", 1)[1]
    ac = requests.post(f"{API}/invites/accept",
                       json={"token": token, "password": PW, "full_name": role}, timeout=30)
    assert ac.status_code == 200, ac.text
    return ac.json()


# --------------------------------------------------------------------------
# Access control
# --------------------------------------------------------------------------
def test_admin_and_barn_manager_can_read():
    admin = _login(ADMIN["email"], ADMIN["password"])
    assert _get(admin["token"], action="test5d.alpha").status_code == 200
    bm = _accept_invite_user("barn_manager")
    assert _get(bm["token"], action="test5d.alpha").status_code == 200


def test_non_privileged_roles_denied_and_audited():
    groom = _login(GROOM["email"], GROOM["password"])
    r = _get(groom["token"])
    assert r.status_code == 403
    assert "Admin/Manager" in r.json()["detail"]
    # exactly one audit_logs.view(denied) for this groom; NO permission.denied(audit:read)
    db = mongo()
    deadline = time.time() + 5
    row = None
    while time.time() < deadline:
        row = db.audit_log.find_one({"action": "audit_logs.view", "outcome": "denied",
                                     "actor_email": GROOM["email"], "ts": {"$gte": STATE["start_ts"]}})
        if row:
            break
        time.sleep(0.2)
    assert row and row["resource_type"] == "audit_log"
    assert row["metadata"]["reason"] == "insufficient_role"
    assert db.audit_log.count_documents({"action": "permission.denied", "resource_id": "audit:read",
                                         "actor_email": GROOM["email"],
                                         "ts": {"$gte": STATE["start_ts"]}}) == 0
    # owner is denied too
    owner = _login(OWNER["email"], OWNER["password"])
    assert _get(owner["token"]).status_code == 403


# --------------------------------------------------------------------------
# Barn isolation (both directions)
# --------------------------------------------------------------------------
def test_reads_are_barn_scoped_both_directions():
    admin = _login(ADMIN["email"], ADMIN["password"])
    # throwaway barn with its own seeded alpha row
    bm_email = f"audit5d_barn_{uuid.uuid4().hex[:8]}@ex.com"
    STATE["emails"].add(bm_email)
    cb = requests.post(f"{API}/barns", json={
        "name": "Audit5D Barn " + uuid.uuid4().hex[:6],
        "admin_email": bm_email, "admin_full_name": "A", "admin_password": PW,
    }, headers=_headers(admin["token"]), timeout=30)
    assert cb.status_code in (200, 201), cb.text
    barn_b = cb.json()["barn"]["id"]
    STATE["barn_ids"].add(barn_b)
    _seed(barn_b, "test5d.alpha")

    # primary admin sees only the 6 primary alpha rows (never barn_b's)
    pr = _get(admin["token"], action="test5d.alpha", limit=200)
    assert pr.status_code == 200
    pj = pr.json()
    assert pj["total"] == 6
    assert all(it["barn_id"] == "primary" for it in pj["items"])

    # barn_b admin sees only its own alpha row (never the 6 primary)
    badmin = _login(bm_email, PW)
    br = _get(badmin["token"], action="test5d.alpha")
    bj = br.json()
    assert bj["total"] == 1 and bj["items"][0]["barn_id"] == barn_b


# --------------------------------------------------------------------------
# Filtering
# --------------------------------------------------------------------------
def test_filtering():
    admin = _login(ADMIN["email"], ADMIN["password"])["token"]
    assert _get(admin, action="test5d.beta", outcome="failure").json()["total"] == 2
    assert _get(admin, actor_user_id="u-5d-2").json()["total"] == 2
    assert _get(admin, resource_id="res-1", action="test5d.alpha").json()["total"] == 6
    # time window (inclusive) over alpha rows ts[2]..ts[4] -> 3
    win = _get(admin, action="test5d.alpha", start=STATE["ts"][2], end=STATE["ts"][4]).json()
    assert win["total"] == 3
    # actor_email filter is supported (case-insensitive) ...
    g = _get(admin, actor_email="FilterMe5D@ex.com")
    assert g.json()["total"] == 1 and g.json()["items"][0]["action"] == "test5d.gamma"


def test_actor_email_not_echoed_in_view_metadata():
    admin = _login(ADMIN["email"], ADMIN["password"])
    before = datetime.now(timezone.utc).isoformat()
    _get(admin["token"], actor_email="FilterMe5D@ex.com", action="test5d.gamma")
    db = mongo()
    time.sleep(0.4)
    row = db.audit_log.find_one({"action": "audit_logs.view", "outcome": "success",
                                 "actor_user_id": admin["user"]["id"], "ts": {"$gte": before}},
                                sort=[("ts", -1)])
    assert row, "expected an audit_logs.view success row"
    assert "actor_email" not in row["metadata"]["filters"]
    assert row["metadata"]["filters"]["action"] == "test5d.gamma"
    assert "result_count" in row["metadata"] and "total" in row["metadata"]


# --------------------------------------------------------------------------
# Pagination + clamp + single-event
# --------------------------------------------------------------------------
def test_pagination_and_limit_clamp():
    admin = _login(ADMIN["email"], ADMIN["password"])["token"]
    p1 = _get(admin, action="test5d.alpha", limit=2, offset=0).json()
    assert len(p1["items"]) == 2 and p1["total"] == 6 and p1["limit"] == 2
    p3 = _get(admin, action="test5d.alpha", limit=2, offset=4).json()
    assert len(p3["items"]) == 2 and p3["total"] == 6 and p3["offset"] == 4
    # newest-first: first item ts >= last item ts
    full = _get(admin, action="test5d.alpha", limit=200).json()
    tss = [it["ts"] for it in full["items"]]
    assert tss == sorted(tss, reverse=True)
    # limit clamp: request 500 -> effective 200
    clamped = _get(admin, action="test5d.alpha", limit=500).json()
    assert clamped["limit"] == 200
    # negative offset rejected
    assert _get(admin, offset=-1).status_code == 422


def test_single_view_event_no_recursion():
    admin = _login(ADMIN["email"], ADMIN["password"])
    before = datetime.now(timezone.utc).isoformat()
    _get(admin["token"], action="test5d.beta")
    time.sleep(0.5)
    db = mongo()
    n = db.audit_log.count_documents({"action": "audit_logs.view", "outcome": "success",
                                      "actor_user_id": admin["user"]["id"],
                                      "metadata.filters.action": "test5d.beta",
                                      "ts": {"$gte": before}})
    assert n == 1, f"expected exactly one view event, got {n}"
