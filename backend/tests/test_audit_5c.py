"""Phase 5C — audit instrumentation integration tests (barn/invite lifecycle +
service-request approve/decline + invoice paid).

Live API + Mongo. Mirrors the 5B harness: `_capture()` polls bounded by this
run's start timestamp (so an assertion can only match a row from THIS run) and
teardown deletes audit rows by the exact ids captured. Service requests and
invoices are seeded directly into Mongo (barn=primary) so the tests own and
delete every record they touch; the founder barn settings are never mutated
(a throwaway barn is used for `barn.settings.updated`).

Guardrails proven: responses/status/messages unchanged; metadata stays minimal
and non-PII (role only / field names only / reason boolean / numeric amount).
"""
import os
import pathlib
import time
import uuid
from datetime import datetime, timezone

import pymongo
import requests

from ._test_creds import ADMIN

PW = "Passw0rd!9"


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


STATE = {
    "audit_ids": set(), "emails": set(), "barn_ids": set(),
    "invite_ids": set(), "sr_ids": set(), "invoice_ids": set(), "start_ts": None,
}


def setup_module(module):
    STATE["start_ts"] = datetime.now(timezone.utc).isoformat()


def teardown_module(module):
    db = mongo()
    if STATE["audit_ids"]:
        db.audit_log.delete_many({"id": {"$in": list(STATE["audit_ids"])}})
    if STATE["invite_ids"]:
        db.invites.delete_many({"id": {"$in": list(STATE["invite_ids"])}})
    if STATE["sr_ids"]:
        db.service_requests.delete_many({"id": {"$in": list(STATE["sr_ids"])}})
    if STATE["invoice_ids"]:
        db.invoices.delete_many({"id": {"$in": list(STATE["invoice_ids"])}})
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
        db.audit_log.delete_many({"resource_id": bid, "ts": {"$gte": STATE["start_ts"]}})


def _capture(query, timeout=6.0):
    q = dict(query)
    q["ts"] = {"$gte": STATE["start_ts"]}
    db = mongo()
    deadline = time.time() + timeout
    while time.time() < deadline:
        doc = db.audit_log.find_one(q, sort=[("ts", -1)])
        if doc:
            STATE["audit_ids"].add(doc["id"])
            return doc
        time.sleep(0.2)
    return None


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    out = r.json()
    _capture({"action": "auth.login.success", "actor_email": email.lower()})
    return out


def _seed_sr(type_="feed_change"):
    sr_id = str(uuid.uuid4())
    STATE["sr_ids"].add(sr_id)
    mongo().service_requests.insert_one({
        "id": sr_id, "barn_id": "primary", "status": "pending", "type": type_,
        "title": "Audit5C SR", "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return sr_id


def _seed_invoice(total=250.0):
    inv_id = str(uuid.uuid4())
    STATE["invoice_ids"].add(inv_id)
    mongo().invoices.insert_one({
        "id": inv_id, "barn_id": "primary", "status": "open", "total": total,
        "owner_id": "audit5c-owner", "items": [], "due_date": "2026-12-31",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return inv_id


# --------------------------------------------------------------------------
# Invite lifecycle
# --------------------------------------------------------------------------
def test_invite_create_resend_revoke_audited():
    admin = _login(ADMIN["email"], ADMIN["password"])
    email = f"audit5c_{uuid.uuid4().hex[:10]}@ex.com"
    cr = requests.post(f"{API}/invites", json={"email": email, "role": "groom", "full_name": "G"},
                       headers=_headers(admin["token"]), timeout=30)
    assert cr.status_code == 200, cr.text
    invite_id = cr.json()["id"]
    STATE["invite_ids"].add(invite_id)

    row = _capture({"action": "invite.created", "resource_id": invite_id})
    assert row and row["resource_type"] == "invite" and row["metadata"] == {"role": "groom"}
    assert email not in str(row["metadata"])  # invitee email omitted

    rs = requests.post(f"{API}/invites/{invite_id}/resend", headers=_headers(admin["token"]), timeout=30)
    assert rs.status_code == 200
    assert _capture({"action": "invite.resent", "resource_id": invite_id})

    rv = requests.post(f"{API}/invites/{invite_id}/revoke", headers=_headers(admin["token"]), timeout=30)
    assert rv.status_code == 200 and rv.json() == {"ok": True}
    assert _capture({"action": "invite.revoked", "resource_id": invite_id})


def test_invite_accept_audited():
    admin = _login(ADMIN["email"], ADMIN["password"])
    email = f"audit5c_acc_{uuid.uuid4().hex[:10]}@ex.com"
    STATE["emails"].add(email)
    cr = requests.post(f"{API}/invites", json={"email": email, "role": "horse_owner", "full_name": "O"},
                       headers=_headers(admin["token"]), timeout=30)
    assert cr.status_code == 200, cr.text
    invite_id = cr.json()["id"]
    STATE["invite_ids"].add(invite_id)
    accept_url = cr.json().get("dev_accept_url")
    assert accept_url, "expected dev_accept_url in dev mode"
    token = accept_url.split("token=", 1)[1]

    ac = requests.post(f"{API}/invites/accept",
                       json={"token": token, "password": PW, "full_name": "Owner C"}, timeout=30)
    assert ac.status_code == 200, ac.text
    row = _capture({"action": "invite.accepted", "resource_id": invite_id})
    assert row and row["metadata"] == {"role": "horse_owner"}
    assert row["actor_user_id"] == ac.json()["user"]["id"]


def test_barn_settings_updated_audited():
    admin = _login(ADMIN["email"], ADMIN["password"])
    admin_email = f"audit5c_barn_{uuid.uuid4().hex[:10]}@ex.com"
    STATE["emails"].add(admin_email)
    cb = requests.post(f"{API}/barns", json={
        "name": "Audit5C Barn " + uuid.uuid4().hex[:6],
        "admin_email": admin_email, "admin_full_name": "Audit5C Admin", "admin_password": PW,
    }, headers=_headers(admin["token"]), timeout=30)
    assert cb.status_code in (200, 201), cb.text
    barn_id = cb.json()["barn"]["id"]
    STATE["barn_ids"].add(barn_id)

    barn_admin = _login(admin_email, PW)
    up = requests.put(f"{API}/barn", json={"name": "Renamed Barn", "timezone": "America/Chicago"},
                      headers=_headers(barn_admin["token"]), timeout=30)
    assert up.status_code == 200
    row = _capture({"action": "barn.settings.updated", "resource_id": barn_id})
    assert row and row["resource_type"] == "barn"
    assert row["metadata"] == {"updated_fields": ["name", "timezone"]}


# --------------------------------------------------------------------------
# Service requests
# --------------------------------------------------------------------------
def test_service_request_approve_audited():
    admin = _login(ADMIN["email"], ADMIN["password"])
    sr_id = _seed_sr("feed_change")
    r = requests.post(f"{API}/service-requests/{sr_id}/approve",
                      headers=_headers(admin["token"]), timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "approved"
    row = _capture({"action": "service_request.approved", "resource_id": sr_id})
    assert row and row["metadata"] == {"type": "feed_change"}


def test_service_request_decline_audited_with_and_without_reason():
    admin = _login(ADMIN["email"], ADMIN["password"])

    # with reason -> reason_provided True; reason text NOT in audit metadata
    sr1 = _seed_sr()
    r1 = requests.post(f"{API}/service-requests/{sr1}/decline",
                       json={"reason": "stall unavailable this week"},
                       headers=_headers(admin["token"]), timeout=30)
    assert r1.status_code == 200 and r1.json()["status"] == "declined"
    row1 = _capture({"action": "service_request.declined", "resource_id": sr1})
    assert row1 and row1["metadata"] == {"reason_provided": True}
    assert "stall unavailable" not in str(row1).lower()
    # the actual reason still lives on the SR record
    assert mongo().service_requests.find_one({"id": sr1})["decline_reason"].startswith("stall")

    # without reason -> reason_provided False
    sr2 = _seed_sr()
    r2 = requests.post(f"{API}/service-requests/{sr2}/decline",
                       headers=_headers(admin["token"]), timeout=30)
    assert r2.status_code == 200
    row2 = _capture({"action": "service_request.declined", "resource_id": sr2})
    assert row2 and row2["metadata"] == {"reason_provided": False}


# --------------------------------------------------------------------------
# Billing
# --------------------------------------------------------------------------
def test_invoice_paid_audited():
    admin = _login(ADMIN["email"], ADMIN["password"])
    inv_id = _seed_invoice(312.5)
    r = requests.post(f"{API}/invoices/{inv_id}/pay", headers=_headers(admin["token"]), timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "paid"
    row = _capture({"action": "invoice.paid", "resource_id": inv_id})
    assert row and row["resource_type"] == "invoice"
    assert row["metadata"] == {"amount": 312.5}
