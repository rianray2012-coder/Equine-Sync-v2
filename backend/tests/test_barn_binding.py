"""Phase 4D — registration & invite barn-binding (live integration).

Option A (invite-only / founder-provisioned):
- founder (primary) admin can create a barn + its first admin;
- non-admins and non-primary admins cannot create barns;
- a barn-2 admin's invites bind to barn 2; accepting binds the new user +
  onboarding progress to barn 2;
- a missing/deleted invite barn falls back to primary (legacy-safe);
- public registration stays bound to primary with role horse_owner (2E).
"""
import hashlib
import os
import pathlib
import uuid
from datetime import datetime, timezone, timedelta

import pymongo
import requests

from ._test_creds import ADMIN, OWNER, GROOM

PW = "Passw0rd!9"


def _read_env(key, root_index, sub):
    envf = pathlib.Path(__file__).resolve().parents[root_index] / sub
    for line in envf.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _base_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    return _read_env("REACT_APP_BACKEND_URL", 2, "frontend/.env").rstrip("/")


API = f"{_base_url()}/api"


def _mongo():
    url = os.environ.get("MONGO_URL") or _read_env("MONGO_URL", 1, ".env")
    name = os.environ.get("DB_NAME") or _read_env("DB_NAME", 1, ".env")
    return pymongo.MongoClient(url)[name]


def _headers(creds):
    r = requests.post(f"{API}/auth/login",
                      json={"email": creds["email"], "password": creds["password"]}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _detail(resp):
    try:
        return resp.json().get("detail")
    except Exception:
        return None


def _invite_token(out):
    url = out.get("dev_accept_url") or ""
    return url.split("token=")[-1] if "token=" in url else None


def _provision_barn(H, name):
    email = f"barnadmin_{uuid.uuid4().hex[:10]}@example.com"
    r = requests.post(f"{API}/barns", headers=H, json={
        "name": name, "facility_type": "boarding",
        "admin_email": email, "admin_full_name": "Barn Admin",
        "admin_password": PW,
    }, timeout=30)
    return r, email


# --------------------------------------------------------------------------
# POST /barns authorization
# --------------------------------------------------------------------------
def test_create_barn_denied_for_non_admins():
    for creds in (GROOM, OWNER):
        r = requests.post(f"{API}/barns", headers=_headers(creds), json={
            "name": "Nope", "admin_email": f"x_{uuid.uuid4().hex[:8]}@e.com",
            "admin_full_name": "X", "admin_password": PW,
        }, timeout=30)
        assert r.status_code == 403, r.text
        assert _detail(r) == "Admin access required to create barns"


def test_create_barn_denied_for_non_primary_admin():
    db = _mongo()
    H = _headers(ADMIN)
    r, admin2_email = _provision_barn(H, "Barn Non-Primary " + uuid.uuid4().hex[:6])
    assert r.status_code == 200, r.text
    barn2 = r.json()["barn"]["id"]
    try:
        # The new barn-2 admin tries to create yet another barn → founder-gate 403.
        H2 = _headers({"email": admin2_email, "password": PW})
        r2 = requests.post(f"{API}/barns", headers=H2, json={
            "name": "Child", "admin_email": f"c_{uuid.uuid4().hex[:8]}@e.com",
            "admin_full_name": "C", "admin_password": PW,
        }, timeout=30)
        assert r2.status_code == 403, r2.text
        assert _detail(r2) == "Only the founder barn can create new barns"
    finally:
        db.barn.delete_many({"id": barn2})
        db.users.delete_many({"email": admin2_email})
        db.onboarding_progress.delete_many({"barn_id": barn2})


def test_primary_admin_creates_barn_and_first_admin():
    db = _mongo()
    H = _headers(ADMIN)
    r, admin2_email = _provision_barn(H, "Founder-Made Barn " + uuid.uuid4().hex[:6])
    assert r.status_code == 200, r.text
    body = r.json()
    barn2 = body["barn"]["id"]
    try:
        assert barn2 != "primary"
        assert body["admin"]["email"] == admin2_email
        assert body["admin"]["role"] == "admin"
        assert body["admin"]["barn_id"] == barn2
        assert "password_hash" not in body["admin"]
        # the provisioned admin can log in (email_verified=True)
        lr = requests.post(f"{API}/auth/login",
                           json={"email": admin2_email, "password": PW}, timeout=30)
        assert lr.status_code == 200, lr.text
    finally:
        db.barn.delete_many({"id": barn2})
        db.users.delete_many({"email": admin2_email})
        db.onboarding_progress.delete_many({"barn_id": barn2})


# --------------------------------------------------------------------------
# Invite binding to a second barn
# --------------------------------------------------------------------------
def test_second_barn_invite_accept_binds_to_barn2():
    db = _mongo()
    H = _headers(ADMIN)
    r, admin2_email = _provision_barn(H, "Barn2 " + uuid.uuid4().hex[:6])
    assert r.status_code == 200, r.text
    barn2 = r.json()["barn"]["id"]
    invitee_email = f"member_{uuid.uuid4().hex[:10]}@example.com"
    try:
        H2 = _headers({"email": admin2_email, "password": PW})
        # barn-2 admin invites → invite must bind to barn 2
        ir = requests.post(f"{API}/invites", headers=H2, json={
            "email": invitee_email, "role": "groom", "full_name": "Member Two",
        }, timeout=30)
        assert ir.status_code in (200, 201), ir.text
        out = ir.json()
        assert out["barn_id"] == barn2, "invite did not bind to barn 2"
        token = _invite_token(out)
        assert token, f"no dev accept token in {out}"
        # accept → new user + onboarding progress bound to barn 2
        ar = requests.post(f"{API}/invites/accept",
                           json={"token": token, "password": PW, "full_name": "Member Two"}, timeout=30)
        assert ar.status_code == 200, ar.text
        new_uid = ar.json()["user"]["id"]
        u = db.users.find_one({"id": new_uid})
        assert u["barn_id"] == barn2, "accepted user not bound to barn 2"
        prog = db.onboarding_progress.find_one({"user_id": new_uid})
        assert prog["barn_id"] == barn2, "onboarding progress not bound to barn 2"
    finally:
        db.barn.delete_many({"id": barn2})
        db.users.delete_many({"email": {"$in": [admin2_email, invitee_email]}})
        db.invites.delete_many({"email": invitee_email})
        db.onboarding_progress.delete_many({"barn_id": barn2})


def test_barn2_admin_invites_only_into_barn2():
    db = _mongo()
    H = _headers(ADMIN)
    r, admin2_email = _provision_barn(H, "Barn2Scope " + uuid.uuid4().hex[:6])
    barn2 = r.json()["barn"]["id"]
    invitee_email = f"scoped_{uuid.uuid4().hex[:10]}@example.com"
    try:
        H2 = _headers({"email": admin2_email, "password": PW})
        ir = requests.post(f"{API}/invites", headers=H2, json={
            "email": invitee_email, "role": "groom",
        }, timeout=30)
        assert ir.status_code in (200, 201), ir.text
        assert ir.json()["barn_id"] == barn2
        # barn-2 admin's invite list shows only barn-2 invites (not primary's)
        lr = requests.get(f"{API}/invites", headers=H2, timeout=30)
        assert lr.status_code == 200
        assert all(inv.get("barn_id") == barn2 for inv in lr.json()), "barn-2 admin saw foreign invites"
        # the primary admin should NOT see the barn-2 invite in their list
        lp = requests.get(f"{API}/invites", headers=H, timeout=30)
        assert invitee_email not in [inv.get("email") for inv in lp.json()], "primary saw barn-2 invite"
    finally:
        db.barn.delete_many({"id": barn2})
        db.users.delete_many({"email": admin2_email})
        db.invites.delete_many({"email": invitee_email})
        db.onboarding_progress.delete_many({"barn_id": barn2})


# --------------------------------------------------------------------------
# Legacy-safe fallback + public registration
# --------------------------------------------------------------------------
def test_invite_with_missing_barn_falls_back_to_primary():
    db = _mongo()
    raw = uuid.uuid4().hex + uuid.uuid4().hex
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    email = f"ghostbarn_{uuid.uuid4().hex[:10]}@example.com"
    db.invites.insert_one({
        "id": "ginv_" + uuid.uuid4().hex, "email": email, "role": "groom",
        "barn_id": "ghostbarn_does_not_exist", "status": "pending",
        "token_hash": token_hash,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        r = requests.post(f"{API}/invites/accept",
                          json={"token": raw, "password": PW}, timeout=30)
        assert r.status_code == 200, r.text
        uid = r.json()["user"]["id"]
        u = db.users.find_one({"id": uid})
        assert u["barn_id"] == "primary", "deleted-barn invite did not fall back to primary"
    finally:
        db.invites.delete_many({"email": email})
        db.users.delete_many({"email": email})
        db.onboarding_progress.delete_many({"user_id": r.json().get("user", {}).get("id")})


def test_public_registration_stays_primary_horse_owner():
    db = _mongo()
    email = f"selfserve_{uuid.uuid4().hex[:10]}@example.com"
    try:
        r = requests.post(f"{API}/auth/register", json={
            "email": email, "full_name": "Self Serve", "password": PW,
        }, timeout=30)
        assert r.status_code == 200, r.text
        u = db.users.find_one({"email": email})
        assert u is not None
        assert u["barn_id"] == "primary", "public registrant not bound to primary"
        assert u["role"] == "horse_owner", "public registrant got a non-default role"
    finally:
        db.users.delete_many({"email": email})
        db.onboarding_progress.delete_many({"user_id": (db.users.find_one({"email": email}) or {}).get("id")})
