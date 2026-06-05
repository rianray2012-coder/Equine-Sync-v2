"""routes/digests.py — owner daily-digest + weekly-recap HTTP routes.

Extracted from server.py (Phase 3E). On-demand preview / send-me / admin
run-now endpoints for the owner daily digest and weekly recap. Behavior is
identical to the previous inline handlers (pure lift-and-shift).

Single source of truth: these HTTP routes and the background schedulers in
server.py (which remain there until Phase 3G) both delegate to the same
`owner_digest.py` domain functions — no duplicated logic.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends

from core.permissions import require
from mailer import send as send_email, render as render_email
from owner_digest import (
    build_digest_for_owner,
    render_digest_html,
    render_digest_text,
    send_digest_to_owner,
    run_daily_digest_pass,
    build_weekly_recap_for_owner,
    render_weekly_recap_html,
    render_weekly_recap_text,
    send_weekly_recap_to_owner,
    run_weekly_recap_pass,
)


def build_router(*, db, get_current_user) -> APIRouter:
    router = APIRouter(tags=["digests"])

    # ---------------- Owner daily digest (Phase-C) ----------------

    @router.post("/notifications/digest/preview")
    async def digest_preview(user=Depends(get_current_user)):
        """Owner: see what their next daily digest would look like."""
        payload = await build_digest_for_owner(db, user["id"])
        if not payload:
            return {"empty": True, "reason": "no_updates_today"}
        return {
            "empty": False,
            "payload": payload,
            "html": render_digest_html(payload, app_base_url=os.environ.get("PUBLIC_APP_URL", "")),
            "text": render_digest_text(payload),
        }

    @router.post("/notifications/digest/send-me")
    async def digest_send_me(user=Depends(get_current_user)):
        """Owner: trigger their own digest now (useful pre-domain-verification)."""
        require(user, "digest:read_own")
        mailer_handle = {"send": send_email, "render": render_email}
        res = await send_digest_to_owner(db, mailer_handle, user["id"])
        return res

    @router.post("/admin/digest/run-now")
    async def digest_run_now(user=Depends(get_current_user)):
        """Admin: force-run today's digest pass (idempotent — won't double-send)."""
        require(user, "digest:admin")
        mailer_handle = {"send": send_email, "render": render_email}
        return await run_daily_digest_pass(db, mailer_handle)

    # ---------------- Owner weekly recap (lightweight Sunday update) ----------------

    @router.post("/notifications/weekly-recap/preview")
    async def weekly_recap_preview(user=Depends(get_current_user)):
        """Owner: preview this week's recap. Returns {empty:true} if nothing meaningful."""
        payload = await build_weekly_recap_for_owner(db, user["id"])
        if not payload:
            return {"empty": True, "reason": "no_updates_this_week"}
        return {
            "empty": False,
            "payload": payload,
            "html": render_weekly_recap_html(payload, app_base_url=os.environ.get("PUBLIC_APP_URL", "")),
            "text": render_weekly_recap_text(payload),
        }

    @router.post("/notifications/weekly-recap/send-me")
    async def weekly_recap_send_me(user=Depends(get_current_user)):
        """Owner: trigger their own weekly recap now."""
        require(user, "digest:read_own")
        mailer_handle = {"send": send_email, "render": render_email}
        return await send_weekly_recap_to_owner(db, mailer_handle, user["id"])

    @router.post("/admin/weekly-recap/run-now")
    async def weekly_recap_run_now(user=Depends(get_current_user)):
        """Admin: force-run this week's recap pass (idempotent on ISO week key)."""
        require(user, "digest:admin")
        mailer_handle = {"send": send_email, "render": render_email}
        return await run_weekly_recap_pass(db, mailer_handle)

    return router
