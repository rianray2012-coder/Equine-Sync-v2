"""routes/invites.py — Magic-link invites + accept flow.

Phase-F extraction. All collaborators (mailer, token issuance, base-url
resolver, analytics tracker, role constants) are injected so this module
stays free of server.py imports.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr


class InviteCreate(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: str
    barn_id: Optional[str] = "primary"
    message: Optional[str] = None


class InviteAccept(BaseModel):
    token: str
    password: str
    full_name: Optional[str] = None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def hash_token(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def new_token_pair() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def build_router(
    *,
    db,
    get_current_user,
    require_setup_role,
    roles: List[str],
    role_labels: Dict[str, str],
    onboarding_steps: List[dict],
    mailer_send,
    track,
    base_url_from_request,
    create_token,
    hash_pwd,
    user_safe,
    client_meta,
    issue_refresh_token,
    jwt_exp_hours: int,
    new_id,
) -> APIRouter:
    router = APIRouter(prefix="/invites", tags=["invites"])

    @router.get("")
    async def list_invites_full(user=Depends(get_current_user)):
        require_setup_role(user)
        return await db.invites.find(
            {}, {"_id": 0, "token_hash": 0},
        ).sort("created_at", -1).to_list(500)

    @router.post("")
    async def create_invite_with_link(body: InviteCreate, request: Request,
                                       user=Depends(get_current_user)):
        require_setup_role(user)
        if body.role not in roles:
            raise HTTPException(400, "Invalid role")
        email_l = body.email.lower()
        if await db.users.find_one({"email": email_l}):
            raise HTTPException(409, "A user with this email already exists")
        existing = await db.invites.find_one({"email": email_l, "status": "pending"})
        if existing:
            raise HTTPException(409, "An invite for this email is already pending — resend or revoke it first")

        raw_token, token_hash = new_token_pair()
        ttl_days = int(os.environ.get("INVITE_TTL_DAYS", "7"))
        expires_at = _now_utc() + timedelta(days=ttl_days)
        barn = await db.barn.find_one({"id": body.barn_id or "primary"}, {"_id": 0, "name": 1}) or {}

        invite = {
            "id": new_id(),
            "email": email_l,
            "full_name": body.full_name,
            "role": body.role,
            "barn_id": body.barn_id or "primary",
            "token_hash": token_hash,
            "status": "pending",
            "message": body.message,
            "invited_by_id": user["id"],
            "invited_by_name": user["full_name"],
            "expires_at": _iso(expires_at),
            "created_at": _iso(_now_utc()),
            "sends": [],
        }
        await db.invites.insert_one(invite)

        accept_url = f"{base_url_from_request(request)}/accept-invite?token={raw_token}"
        mail = await mailer_send(
            to=email_l,
            subject=f"You're invited to {barn.get('name') or 'EquineSync'}",
            template="onboarding_invite",
            variables={
                "barn_name": barn.get("name") or "EquineSync",
                "invitee_name": (body.full_name or email_l.split('@')[0]).strip() or "rider",
                "inviter_name": user["full_name"],
                "role_label": role_labels.get(body.role, body.role.replace('_', ' ')),
                "accept_url": accept_url,
                "ttl_days": ttl_days,
            },
        )
        await db.invites.update_one(
            {"id": invite["id"]},
            {"$push": {"sends": {"at": _iso(_now_utc()),
                                  "status": mail.get("status"),
                                  "id": mail.get("id")}}},
        )
        await track("invite.sent",
                    {"invite_id": invite["id"], "role": body.role,
                     "dev_mode": mail.get("dev", False)},
                    user["id"])
        out = await db.invites.find_one({"id": invite["id"]}, {"_id": 0, "token_hash": 0})
        if mail.get("dev"):
            out["dev_accept_url"] = accept_url
        return out

    @router.post("/{invite_id}/resend")
    async def resend_invite(invite_id: str, request: Request, user=Depends(get_current_user)):
        require_setup_role(user)
        inv = await db.invites.find_one({"id": invite_id})
        if not inv:
            raise HTTPException(404, "Invite not found")
        if inv.get("status") != "pending":
            raise HTTPException(400, f"Invite is {inv.get('status')}")
        raw_token, token_hash = new_token_pair()
        ttl_days = int(os.environ.get("INVITE_TTL_DAYS", "7"))
        expires_at = _now_utc() + timedelta(days=ttl_days)
        await db.invites.update_one(
            {"id": invite_id},
            {"$set": {"token_hash": token_hash,
                      "expires_at": _iso(expires_at),
                      "updated_at": _iso(_now_utc())}},
        )

        barn = await db.barn.find_one({"id": inv.get("barn_id", "primary")}, {"_id": 0, "name": 1}) or {}
        accept_url = f"{base_url_from_request(request)}/accept-invite?token={raw_token}"
        mail = await mailer_send(
            to=inv["email"],
            subject=f"Reminder: your invitation to {barn.get('name') or 'EquineSync'}",
            template="onboarding_invite",
            variables={
                "barn_name": barn.get("name") or "EquineSync",
                "invitee_name": (inv.get("full_name") or inv["email"].split('@')[0]),
                "inviter_name": user["full_name"],
                "role_label": role_labels.get(inv["role"], inv["role"].replace('_', ' ')),
                "accept_url": accept_url,
                "ttl_days": ttl_days,
            },
        )
        await db.invites.update_one(
            {"id": invite_id},
            {"$push": {"sends": {"at": _iso(_now_utc()),
                                  "status": mail.get("status"),
                                  "id": mail.get("id"),
                                  "resend": True}}},
        )
        await track("invite.resent", {"invite_id": invite_id}, user["id"])
        out = await db.invites.find_one({"id": invite_id}, {"_id": 0, "token_hash": 0})
        if mail.get("dev"):
            out["dev_accept_url"] = accept_url
        return out

    @router.post("/{invite_id}/revoke")
    async def revoke_invite(invite_id: str, user=Depends(get_current_user)):
        require_setup_role(user)
        res = await db.invites.update_one(
            {"id": invite_id, "status": "pending"},
            {"$set": {"status": "revoked",
                      "revoked_at": _iso(_now_utc()),
                      "revoked_by": user["full_name"]}},
        )
        if res.matched_count == 0:
            raise HTTPException(404, "No pending invite found")
        await track("invite.revoked", {"invite_id": invite_id}, user["id"])
        return {"ok": True}

    @router.get("/verify")
    async def verify_invite(token: str):
        inv = await db.invites.find_one({"token_hash": hash_token(token)},
                                          {"_id": 0, "token_hash": 0})
        if not inv:
            raise HTTPException(404, "Invalid invitation link")
        if inv.get("status") != "pending":
            raise HTTPException(410, f"This invitation is {inv.get('status')}")
        try:
            exp = datetime.fromisoformat(inv["expires_at"])
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < _now_utc():
                await db.invites.update_one({"id": inv["id"]}, {"$set": {"status": "expired"}})
                raise HTTPException(410, "This invitation has expired")
        except KeyError:
            pass
        barn = await db.barn.find_one(
            {"id": inv.get("barn_id", "primary")},
            {"_id": 0, "name": 1, "facility_type": 1},
        ) or {}
        inv["barn"] = barn
        return inv

    @router.post("/accept")
    async def accept_invite(body: InviteAccept, request: Request):
        inv = await db.invites.find_one({"token_hash": hash_token(body.token)})
        if not inv:
            raise HTTPException(404, "Invalid invitation")
        if inv.get("status") != "pending":
            raise HTTPException(410, f"Invitation is {inv.get('status')}")
        exp = datetime.fromisoformat(inv["expires_at"])
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < _now_utc():
            await db.invites.update_one({"id": inv["id"]}, {"$set": {"status": "expired"}})
            raise HTTPException(410, "Invitation expired")
        if len(body.password) < 8:
            raise HTTPException(400, "Password must be at least 8 characters")
        if await db.users.find_one({"email": inv["email"]}):
            raise HTTPException(409, "A user already exists for this email — please sign in")

        full_name = (body.full_name or inv.get("full_name")
                     or inv["email"].split('@')[0]).strip()
        new_user = {
            "id": new_id(),
            "email": inv["email"],
            "full_name": full_name,
            "role": inv["role"],
            "password_hash": hash_pwd(body.password),
            "created_at": _iso(_now_utc()),
            "via_invite_id": inv["id"],
        }
        await db.users.insert_one(new_user)
        await db.invites.update_one(
            {"id": inv["id"]},
            {"$set": {"status": "accepted",
                      "accepted_at": _iso(_now_utc()),
                      "accepted_user_id": new_user["id"]}},
        )

        has_setup_role = inv["role"] in ("admin", "barn_manager")
        progress = {
            "user_id": new_user["id"],
            "steps": {s["id"]: "pending" for s in onboarding_steps},
            "current_step": onboarding_steps[0]["id"],
            "data": {},
            "completed": not has_setup_role,
            "auto_launch": has_setup_role,
            "created_at": _iso(_now_utc()),
            "updated_at": _iso(_now_utc()),
        }
        await db.onboarding_progress.insert_one(progress)

        token = create_token(new_user["id"], new_user["role"])
        ua, ip = await client_meta(request)
        refresh = await issue_refresh_token(db, new_user["id"], user_agent=ua, ip=ip)
        await track("invite.accepted",
                    {"invite_id": inv["id"], "role": inv["role"]},
                    new_user["id"])
        return {
            "token": token,
            "refresh_token": refresh,
            "expires_in_seconds": jwt_exp_hours * 3600,
            "user": user_safe(new_user),
            "auto_launch_onboarding": has_setup_role,
        }

    return router
