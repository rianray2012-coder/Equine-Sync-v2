"""routes/reports.py — Setup health, nudge candidates, admin send-nudges.

Phase-F extraction. Routes depend on:
- db (Mongo handle)
- get_current_user (FastAPI dep)
- require_setup_role (callable)
- onboarding_steps (constant list — passed in so server.py remains source of truth)
- mailer_send (async callable matching mailer.send signature)
- track (async analytics emitter)
- base_url_from_request (callable Optional[Request] -> str)
- iso, now_utc (datetime helpers)
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel


class SendNudgesBody(BaseModel):
    min_days: int = 3
    cooldown_hours: int = 24
    user_ids: Optional[List[str]] = None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def build_reports_module(*, db, onboarding_steps: List[dict], mailer_send, track,
                          base_url_from_request, require_setup_role):
    """Returns (router, setup_health_payload, nudge_candidates, send_nudges)
    so the startup scheduler in server.py can also invoke `send_nudges` directly.
    """

    async def setup_health_payload() -> Dict[str, Any]:
        total_progress = await db.onboarding_progress.count_documents({})
        completed_progress = await db.onboarding_progress.count_documents({"completed": True})

        progresses = await db.onboarding_progress.find(
            {},
            {"_id": 0, "steps": 1, "data": 1, "updated_at": 1, "created_at": 1,
             "completed": 1, "completed_at": 1, "user_id": 1},
        ).to_list(2000)
        funnel = {s["id"]: {"label": s["label"], "complete": 0, "in_progress": 0,
                            "skipped": 0, "pending": 0} for s in onboarding_steps}
        durations: List[float] = []
        for p in progresses:
            for sid, status in (p.get("steps") or {}).items():
                if sid in funnel and status in funnel[sid]:
                    funnel[sid][status] += 1
            if p.get("completed") and p.get("created_at") and p.get("completed_at"):
                try:
                    a = datetime.fromisoformat(p["created_at"])
                    b = datetime.fromisoformat(p["completed_at"])
                    if a.tzinfo is None: a = a.replace(tzinfo=timezone.utc)
                    if b.tzinfo is None: b = b.replace(tzinfo=timezone.utc)
                    durations.append((b - a).total_seconds() / 3600.0)
                except Exception:
                    pass

        def _median(xs):
            if not xs: return None
            xs = sorted(xs); n = len(xs)
            return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2

        median_hours = _median(durations)

        total_invites = await db.invites.count_documents({})
        accepted = await db.invites.count_documents({"status": "accepted"})
        pending_invites = await db.invites.count_documents({"status": "pending"})
        revoked = await db.invites.count_documents({"status": "revoked"})
        expired = await db.invites.count_documents({"status": "expired"})
        acceptance_rate = round(100 * accepted / total_invites) if total_invites else 0

        return {
            "total_setups": total_progress,
            "completed_setups": completed_progress,
            "in_progress_setups": total_progress - completed_progress,
            "completion_rate": round(100 * completed_progress / total_progress) if total_progress else 0,
            "median_hours_to_launch": round(median_hours, 1) if median_hours else None,
            "median_days_to_launch": round(median_hours / 24, 1) if median_hours else None,
            "funnel": [{"step": sid, **counts} for sid, counts in funnel.items()],
            "invites": {
                "total": total_invites, "accepted": accepted, "pending": pending_invites,
                "revoked": revoked, "expired": expired, "acceptance_rate": acceptance_rate,
            },
        }

    async def nudge_candidates(min_days: int = 3) -> List[Dict[str, Any]]:
        cutoff = _now_utc() - timedelta(days=min_days)
        rows = await db.onboarding_progress.find(
            {"completed": {"$ne": True}}, {"_id": 0},
        ).to_list(2000)
        out: List[Dict[str, Any]] = []
        for p in rows:
            try:
                updated = datetime.fromisoformat(p.get("updated_at") or p.get("created_at"))
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if updated > cutoff:
                continue
            u = await db.users.find_one(
                {"id": p["user_id"]},
                {"_id": 0, "email": 1, "full_name": 1, "role": 1},
            )
            if not u or not u.get("email"):
                continue
            steps = p.get("steps") or {}
            completed = sum(1 for v in steps.values() if v == "complete")
            next_step = next(
                (s for s in onboarding_steps if steps.get(s["id"]) not in ("complete", "skipped")),
                None,
            )
            days_stalled = max(1, int((_now_utc() - updated).total_seconds() / 86400))
            out.append({
                "user_id": p["user_id"],
                "email": u["email"],
                "full_name": u.get("full_name", ""),
                "role": u.get("role"),
                "percent_done": round(100 * completed / len(onboarding_steps)),
                "next_step": next_step["id"] if next_step else "review",
                "next_step_label": next_step["label"] if next_step else "Review & Launch",
                "days_stalled": days_stalled,
                "updated_at": p.get("updated_at"),
                "current_step": p.get("current_step"),
                "last_nudged_at": p.get("last_nudged_at"),
            })
        return out

    async def send_nudges(request: Optional[Request], inviter_name: str,
                           min_days: int = 3, cooldown_hours: int = 24,
                           user_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        candidates = await nudge_candidates(min_days)
        if user_ids is not None:
            wanted = set(user_ids)
            candidates = [c for c in candidates if c["user_id"] in wanted]
        barn = await db.barn.find_one({"id": "primary"}, {"_id": 0, "name": 1}) or {}
        sent = 0; skipped = 0; errors = 0; detail: List[Dict[str, Any]] = []
        cooldown = _now_utc() - timedelta(hours=cooldown_hours)
        base = base_url_from_request(request) if request else (
            os.environ.get("APP_BASE_URL", "").rstrip("/")
            or "https://herd-hub-19.emergent.host"
        )
        for c in candidates:
            last = c.get("last_nudged_at")
            if last:
                try:
                    dt = datetime.fromisoformat(last)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt > cooldown:
                        skipped += 1
                        detail.append({"email": c["email"], "result": "cooldown"})
                        continue
                except Exception:
                    pass
            mail = await mailer_send(
                to=c["email"],
                subject=f"Pick up where you left off at {barn.get('name') or 'EquineSync'}",
                template="onboarding_nudge",
                variables={
                    "barn_name": barn.get("name") or "EquineSync",
                    "invitee_name": (c["full_name"].split(" ")[0]
                                     if c["full_name"] else c["email"].split("@")[0]),
                    "days_stalled": c["days_stalled"],
                    "percent_done": c["percent_done"],
                    "next_step_label": c["next_step_label"],
                    "resume_url": f"{base}/onboarding",
                    "ttl_days": 7,
                },
            )
            sent_ok = mail.get("status") in ("sent", "sandbox", "dev_logged")
            if mail.get("status") == "sent":
                sent += 1
                detail.append({"email": c["email"], "result": "sent"})
            elif mail.get("dev"):
                skipped += 1
                detail.append({"email": c["email"], "result": mail.get("status")})
            else:
                errors += 1
                detail.append({"email": c["email"], "result": "error",
                               "error": mail.get("error", "")[:120]})
            if sent_ok:
                await db.onboarding_progress.update_one(
                    {"user_id": c["user_id"]},
                    {"$set": {"last_nudged_at": _iso(_now_utc())},
                     "$inc": {"nudges_sent": 1}},
                )
            await track(
                "onboarding.nudge_sent",
                {"user_id": c["user_id"], "days_stalled": c["days_stalled"],
                 "result": mail.get("status")},
                None,
            )
        return {"candidates": len(candidates), "sent": sent, "skipped": skipped,
                "errors": errors, "detail": detail}

    # ---------------- helpers exported for both routes and startup scheduler ----------------
    return {
        "setup_health_payload": setup_health_payload,
        "nudge_candidates": nudge_candidates,
        "send_nudges": send_nudges,
    }


def build_router(*, db, get_current_user, onboarding_steps, mailer_send, track,
                  base_url_from_request, require_setup_role) -> APIRouter:
    helpers = build_reports_module(
        db=db,
        onboarding_steps=onboarding_steps,
        mailer_send=mailer_send,
        track=track,
        base_url_from_request=base_url_from_request,
        require_setup_role=require_setup_role,
    )
    setup_health_payload = helpers["setup_health_payload"]
    nudge_candidates_fn = helpers["nudge_candidates"]
    send_nudges_fn = helpers["send_nudges"]

    router = APIRouter(tags=["reports"])

    @router.get("/reports/setup-health")
    async def setup_health(user=Depends(get_current_user)):
        require_setup_role(user)
        return await setup_health_payload()

    @router.get("/reports/nudge-candidates")
    async def list_nudge_candidates(min_days: int = 3, user=Depends(get_current_user)):
        require_setup_role(user)
        return await nudge_candidates_fn(min_days)

    @router.post("/admin/send-nudges")
    async def admin_send_nudges(body: SendNudgesBody, request: Request,
                                  user=Depends(get_current_user)):
        require_setup_role(user)
        result = await send_nudges_fn(request, user["full_name"], body.min_days,
                                       body.cooldown_hours, body.user_ids)
        await track(
            "admin.nudges_run",
            {"trigger": "manual", **{k: v for k, v in result.items() if k != "detail"}},
            user["id"],
        )
        return result

    # Expose helpers on the router so server.py can re-use send_nudges from
    # the startup scheduler without re-implementing it.
    router._reports_helpers = helpers  # type: ignore[attr-defined]
    return router
