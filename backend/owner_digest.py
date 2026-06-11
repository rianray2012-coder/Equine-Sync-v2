"""
Owner daily digest — Phase-C (Feb 20 2026).

Composes calm, wellness-oriented summaries for horse owners. Designed
around the user's editorial direction:
  - reassuring · thoughtful · operationally aware · emotionally calm
  - concise summaries · meaningful updates · soft hierarchy
Exclusions are explicit (per OWNER_VISIBLE_CATEGORIES in task_engine):
  no stall cleaning, no turnout-only, no internal staffing chatter.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import List, Dict, Optional

from routes.owner import _friendly_title  # DRY: shared owner-facing title humanizer (added in 7D-2)

logger = logging.getLogger(__name__)

OWNER_DIGEST_CATEGORIES = {"medication", "farrier", "vet", "rehab", "feed"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%A, %b %-d") if hasattr(dt, "strftime") else str(dt)


def _fmt_short(dt: datetime) -> str:
    return dt.strftime("%b %-d") if hasattr(dt, "strftime") else str(dt)


def _parse(s: str) -> datetime:
    if not s:
        return _now()
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Pure composition helpers (testable in isolation, no DB)
# ---------------------------------------------------------------------------

def _vet_phrase(events: List[dict], horse_name: str) -> Optional[str]:
    completed = [e for e in events if e["event_type"] == "task.completed" and e.get("category") == "vet"]
    if not completed:
        return None
    e = completed[0]
    snap = e.get("payload_snapshot") or {}
    vet = snap.get("vet_name")
    title = snap.get("title") or "Vet visit"
    if vet:
        return f"{horse_name} had a {title.lower()} with {vet} today."
    return f"{horse_name} completed a {title.lower()} today."


def _farrier_phrase(events: List[dict], horse_name: str) -> Optional[str]:
    completed = [e for e in events if e["event_type"] == "task.completed" and e.get("category") == "farrier"]
    if not completed:
        return None
    e = completed[0]
    snap = e.get("payload_snapshot") or {}
    farrier = snap.get("farrier_name")
    if farrier:
        return f"{horse_name} had a farrier visit completed with {farrier}."
    return f"{horse_name} had a farrier visit completed today."


def _medication_phrase(events: List[dict], horse_name: str, window_label: str = "today") -> Optional[str]:
    completed = [e for e in events
                 if e.get("category") == "medication" and e["event_type"] == "task.completed"]
    skipped = [e for e in events
               if e.get("category") == "medication" and e["event_type"] == "task.skipped"]
    if not completed and not skipped:
        return None
    if completed and not skipped:
        if len(completed) == 1:
            snap = completed[0].get("payload_snapshot") or {}
            name = snap.get("title") or "medication"
            return f"{horse_name} received {name} {window_label}."
        return f"{horse_name} completed all scheduled medications {window_label}."
    if skipped:
        # Wellness-oriented framing — never alarm; surface as info, not red.
        snap = skipped[0].get("payload_snapshot") or {}
        outcome = snap.get("outcome") or "skipped"
        med = snap.get("title") or "a dose"
        if outcome == "refused":
            return f"{horse_name} declined {med} earlier — your team made a note for the vet."
        return f"{horse_name}'s {med} was rescheduled {window_label}."
    return None


def _rehab_phrase(events: List[dict], horse_name: str) -> Optional[str]:
    completed = [e for e in events if e.get("category") == "rehab" and e["event_type"] == "task.completed"]
    if not completed:
        return None
    if len(completed) == 1:
        return f"{horse_name} completed a rehab session today."
    return f"{horse_name} completed {len(completed)} rehab sessions today."


def _upcoming_phrase(tasks: List[dict], horse_name: str) -> Optional[str]:
    """Tasks within the next 7 days. Soft, anticipatory phrasing."""
    if not tasks:
        return None
    # Group by category, then describe the soonest
    by_cat: Dict[str, list] = defaultdict(list)
    for t in tasks:
        by_cat[t.get("category", "custom")].append(t)
    lines = []
    if by_cat.get("vet"):
        next_v = by_cat["vet"][0]
        when = _parse(next_v["scheduled_at"])
        # Humanize the title so an engine token (e.g. "Follow-up: vetfu-<uuid>")
        # never reaches an owner. _friendly_title returns the human-entered text
        # verbatim, or a clean category/follow-up label when it's empty/id-like.
        raw_title = (next_v.get("title") or (next_v.get("payload") or {}).get("title") or "").strip()
        friendly = _friendly_title(raw_title, "vet")
        if friendly == raw_title and raw_title:
            # Genuine human title (e.g. "Spring Vaccines") — keep natural plural phrasing.
            lines.append(f"{friendly} are scheduled for {_fmt_date(when)}.")
        else:
            # Sanitized/label fallback — calm singular phrasing, no raw id.
            lines.append(f"A {friendly.lower()} is scheduled for {_fmt_date(when)}.")
    if by_cat.get("farrier"):
        next_f = by_cat["farrier"][0]
        when = _parse(next_f["scheduled_at"])
        lines.append(f"Farrier visit for {horse_name} scheduled for {_fmt_date(when)}.")
    return " ".join(lines) if lines else None


def compose_horse_section(horse: dict, events_24h: List[dict],
                          events_7d_meds: List[dict],
                          upcoming_7d: List[dict],
                          events_7d_all: Optional[List[dict]] = None) -> Optional[dict]:
    """Returns {horse_name, lines: [string], muted: bool} or None if nothing meaningful.

    If `events_7d_all` is provided, an optional calm 7-day pulse line may
    be appended via wellness_pulse.compose_pulse — strictly observational,
    only when confidence is high enough.
    """
    horse_name = horse.get("name") or "Your horse"
    lines: List[str] = []

    # Recent care (last 24h)
    for getter in (_vet_phrase, _farrier_phrase, _rehab_phrase):
        line = getter(events_24h, horse_name)
        if line:
            lines.append(line)

    # Medications: roll up the last 24h
    med_line = _medication_phrase(events_24h, horse_name, window_label="today")
    if med_line:
        lines.append(med_line)

    # Weekly medication adherence as a soft signal (only if it's a positive)
    if not med_line:
        weekly = _medication_phrase(events_7d_meds, horse_name, window_label="this week")
        if weekly and "completed all" in weekly:
            lines.append(weekly)

    # Upcoming (soft anticipatory phrasing)
    up = _upcoming_phrase(upcoming_7d, horse_name)
    if up:
        lines.append(up)

    if not lines:
        return None

    # Optional wellness-pulse line (observational, restrained — only added
    # when there's something meaningful to say AND the section already has
    # at least one care line to anchor it).
    if events_7d_all is not None:
        try:
            from wellness_pulse import compose_pulse
            pulse = compose_pulse(horse_name, events_7d_all)
            if pulse:
                lines.append(pulse)
        except Exception:
            logger.exception("wellness pulse composition failed for horse=%s", horse.get("id"))

    return {"horse_id": horse.get("id"), "horse_name": horse_name, "lines": lines}


# ---------------------------------------------------------------------------
# Composition with DB context
# ---------------------------------------------------------------------------

async def build_digest_for_owner(db, owner_user_id: str,
                                  now: Optional[datetime] = None) -> Optional[dict]:
    """Build the full digest payload. Returns None if owner has no horses or
    no meaningful updates worth sending.
    """
    now = now or _now()
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)
    until_7d = now + timedelta(days=7)

    # 1. Find horses owned by this user
    horses = await db.horses.find(
        {"owner_id": owner_user_id}, {"_id": 0, "id": 1, "name": 1, "barn_id": 1},
    ).to_list(50)
    if not horses:
        return None
    horse_ids = [h["id"] for h in horses]
    owner_barn = horses[0].get("barn_id", "primary")

    # 2. Events in last 24h for those horses (curated categories only)
    events_24h_cursor = db.task_events.find(
        {
            "barn_id": owner_barn,
            "subject_horse_ids": {"$in": horse_ids},
            "category": {"$in": list(OWNER_DIGEST_CATEGORIES)},
            "event_type": {"$in": ["task.completed", "task.skipped"]},
            "occurred_at": {"$gte": _iso(since_24h)},
        },
        {"_id": 0},
    ).sort("occurred_at", -1)
    events_24h = await events_24h_cursor.to_list(500)

    # 3. Medication events over the last 7d for the "completed all this week" line
    events_7d_meds = await db.task_events.find(
        {
            "barn_id": owner_barn,
            "subject_horse_ids": {"$in": horse_ids},
            "category": "medication",
            "event_type": {"$in": ["task.completed", "task.skipped"]},
            "occurred_at": {"$gte": _iso(since_7d)},
        },
        {"_id": 0},
    ).to_list(2000)

    # 3b. Broader 7d window across all curated categories — feeds the
    # optional wellness-pulse observation. Kept lightweight: projection
    # is just event_type + category + subject_horse_ids.
    events_7d_all = await db.task_events.find(
        {
            "barn_id": owner_barn,
            "subject_horse_ids": {"$in": horse_ids},
            "category": {"$in": list(OWNER_DIGEST_CATEGORIES) + ["turnout_out", "turnout_in"]},
            "event_type": {"$in": ["task.completed", "task.skipped"]},
            "occurred_at": {"$gte": _iso(since_7d)},
        },
        {"_id": 0, "category": 1, "event_type": 1, "subject_horse_ids": 1},
    ).to_list(5000)

    # 4. Upcoming curated tasks in the next 7 days
    upcoming = await db.tasks.find(
        {
            "barn_id": owner_barn,
            "linked_horse_ids": {"$in": horse_ids},
            "category": {"$in": ["vet", "farrier"]},
            "status": {"$nin": ["completed", "skipped", "cancelled"]},
            "scheduled_at": {"$gte": _iso(now), "$lte": _iso(until_7d)},
        },
        {"_id": 0},
    ).sort("scheduled_at", 1).to_list(200)

    # 5. Compose per-horse sections
    sections = []
    for h in horses:
        e24 = [e for e in events_24h if h["id"] in (e.get("subject_horse_ids") or [])]
        e7 = [e for e in events_7d_meds if h["id"] in (e.get("subject_horse_ids") or [])]
        e7_all = [e for e in events_7d_all if h["id"] in (e.get("subject_horse_ids") or [])]
        up = [t for t in upcoming if h["id"] in (t.get("linked_horse_ids") or [])]
        sec = compose_horse_section(h, e24, e7, up, events_7d_all=e7_all)
        if sec:
            sections.append(sec)

    if not sections:
        return None  # caller should skip sending an empty digest

    return {
        "owner_user_id": owner_user_id,
        "generated_at": _iso(now),
        "for_date": now.date().isoformat(),
        "sections": sections,
        "horse_count": len(horses),
        "updates_count": sum(len(s["lines"]) for s in sections),
    }


# ---------------------------------------------------------------------------
# Render — minimal, calm HTML & text
# ---------------------------------------------------------------------------

DIGEST_CSS = """
  body { background:#f7f3ee; margin:0; padding:0; font-family:'Georgia',ui-serif,serif; color:#2a2730; }
  .wrap { max-width:560px; margin:0 auto; padding:36px 28px; }
  .eyebrow { font-family:ui-sans-serif,system-ui,sans-serif; letter-spacing:.22em; text-transform:uppercase; font-size:10.5px; color:#857d6f; }
  h1 { font-size:28px; line-height:1.15; margin:6px 0 18px; color:#2a2730; font-weight:400; }
  .horse { padding:18px 0; border-top:1px solid #eae3d4; }
  .horse-name { font-family:ui-sans-serif,system-ui,sans-serif; font-size:11px; letter-spacing:.18em; text-transform:uppercase; color:#857d6f; margin-bottom:6px; }
  p { margin:6px 0; font-size:15.5px; line-height:1.55; color:#2a2730; }
  .footer { margin-top:32px; padding-top:18px; border-top:1px solid #eae3d4; font-size:11.5px; color:#857d6f; font-family:ui-sans-serif,system-ui,sans-serif; }
  a.prefs { color:#857d6f; text-decoration:underline; }
  /* ---- Phase 8D brand presence (additive; warm calm bg preserved) ---- */
  .brandhead { margin-bottom:14px; }
  .brand-mark { display:block; width:48px; height:48px; border:0; margin-bottom:10px; }
  .brand { font-family:'Cormorant Garamond','Georgia',serif; font-size:25px; line-height:1; letter-spacing:.005em; }
  .brand .eq { color:#232734; }
  .brand .sync { color:#6E5A99; }
  .tagline { font-family:ui-sans-serif,system-ui,sans-serif; letter-spacing:.18em; text-transform:uppercase; font-size:9px; color:#667085; margin-top:7px; }
  .signoff { font-family:'Cormorant Garamond','Georgia',serif; font-size:16px; color:#232734; margin-bottom:5px; }
  .signoff .sync { color:#6E5A99; }
"""


def _brand_header_html(app_base_url: str, section_label: str) -> str:
    """Email-safe brand lockup: hosted horse mark when PUBLIC_APP_URL is set,
    always followed by the CSS wordmark + tagline (renders even if images are blocked)."""
    base = (app_base_url or "").rstrip("/")
    mark = (
        f'<img class="brand-mark" src="{base}/icon-192.png" width="48" height="48" alt="Equine-Sync" />'
        if base else ""
    )
    return (
        f'<div class="brandhead">{mark}'
        f'<div class="brand"><span class="eq">Equine-</span><span class="sync">Sync</span></div>'
        f'<div class="tagline">Every Horse. Every Task. In Sync.</div></div>'
        f'<div class="eyebrow">{section_label}</div>'
    )


def render_digest_html(payload: dict, app_base_url: str = "") -> str:
    parts = ['<!DOCTYPE html><html><head><meta charset="utf-8"><style>',
             DIGEST_CSS, '</style></head><body><div class="wrap">']
    parts.append(_brand_header_html(app_base_url, "Daily Care"))
    parts.append('<h1>Today at the barn</h1>')
    for sec in payload["sections"]:
        parts.append('<div class="horse">')
        parts.append(f'<div class="horse-name">{sec["horse_name"]}</div>')
        for line in sec["lines"]:
            parts.append(f'<p>{line}</p>')
        parts.append('</div>')
    settings_url = (app_base_url.rstrip("/") + "/settings") if app_base_url else "/settings"
    parts.append(
        f'<div class="footer">'
        f'<div class="signoff">Equine-<span class="sync">Sync</span></div>'
        f'You receive this digest because your horse is in care at the barn. '
        f'<a class="prefs" href="{settings_url}">Manage preferences</a>.'
        f'</div></div></body></html>'
    )
    return "".join(parts)


def render_digest_text(payload: dict) -> str:
    out = ["Equine-Sync", "Every Horse. Every Task. In Sync.", "",
           "Today at the barn", "=" * 32, ""]
    for sec in payload["sections"]:
        out.append(sec["horse_name"].upper())
        for line in sec["lines"]:
            out.append(f"  {line}")
        out.append("")
    out.append("Manage preferences in Settings → Notifications.")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

async def send_digest_to_owner(db, mailer, owner_user_id: str,
                                now: Optional[datetime] = None,
                                dry_run: bool = False) -> dict:
    payload = await build_digest_for_owner(db, owner_user_id, now=now)
    if not payload:
        return {"sent": False, "reason": "no_updates"}
    owner = await db.users.find_one({"id": owner_user_id}, {"_id": 0, "email": 1, "full_name": 1})
    if not owner:
        return {"sent": False, "reason": "owner_not_found"}
    html = render_digest_html(payload, app_base_url=os.environ.get("PUBLIC_APP_URL", ""))
    text = render_digest_text(payload)
    if dry_run:
        return {"sent": False, "reason": "dry_run", "preview": {"html": html, "text": text, "payload": payload}}
    subject = f"Equine-Sync · Today's update on {'your horses' if payload['horse_count'] > 1 else payload['sections'][0]['horse_name']}"
    try:
        send_res = mailer["send"](to=owner["email"], subject=subject, html=html, text=text)
        await db.notification_digest_log.insert_one({
            "id": __import__("uuid").uuid4().hex,
            "owner_user_id": owner_user_id,
            "sent_at": _iso(_now()),
            "for_date": payload["for_date"],
            "updates_count": payload["updates_count"],
            "result": send_res,
        })
        return {"sent": True, "updates_count": payload["updates_count"], "result": send_res}
    except Exception:
        logger.exception("digest send failed for owner=%s", owner_user_id)
        return {"sent": False, "reason": "send_error"}


async def already_sent_today(db, owner_user_id: str, for_date: str) -> bool:
    rec = await db.notification_digest_log.find_one(
        {"owner_user_id": owner_user_id, "for_date": for_date},
        {"_id": 0, "id": 1},
    )
    return bool(rec)


async def run_daily_digest_pass(db, mailer) -> dict:
    """Run a pass: send to any owner who has digest_enabled=true and hasn't
    received today's digest yet. Idempotent — safe to call multiple times.
    """
    today_str = _now().date().isoformat()
    owners = await db.users.find({"role": "horse_owner"}, {"_id": 0, "id": 1}).to_list(500)
    sent = 0
    skipped = 0
    for o in owners:
        prefs = await db.notification_preferences.find_one(
            {"user_id": o["id"]}, {"_id": 0},
        )
        if prefs and prefs.get("digest_enabled") is False:
            skipped += 1
            continue
        if await already_sent_today(db, o["id"], today_str):
            skipped += 1
            continue
        res = await send_digest_to_owner(db, mailer, o["id"])
        if res.get("sent"):
            sent += 1
        else:
            skipped += 1
    return {"sent": sent, "skipped": skipped, "for_date": today_str}


async def ensure_digest_indexes(db):
    await db.notification_digest_log.create_index([("owner_user_id", 1), ("for_date", 1)], unique=True)
    await db.notification_digest_log.create_index(
        [("owner_user_id", 1), ("for_week", 1)],
        unique=True,
        partialFilterExpression={"for_week": {"$exists": True}},
    )


# ---------------------------------------------------------------------------
# Weekly recap — lightweight, calm Sunday-evening summary
# ---------------------------------------------------------------------------

def _iso_week_key(dt: datetime) -> str:
    """Return ISO 8601 year-week (e.g. '2026-W08') used as idempotency key."""
    iso = dt.isocalendar()
    return f"{iso.year:04d}-W{iso.week:02d}"


def _weekly_compose_section(horse: dict, events_7d: List[dict],
                              upcoming_7d: List[dict]) -> Optional[dict]:
    """Compose a calm per-horse weekly section. Limits itself to ≤ 3 lines
    so the email stays scannable and reassuring.
    """
    horse_name = horse.get("name") or "Your horse"
    lines: List[str] = []

    # Medications — only surface positive adherence or notable refusal once.
    med_completed = [e for e in events_7d
                     if e.get("category") == "medication" and e["event_type"] == "task.completed"]
    med_skipped = [e for e in events_7d
                   if e.get("category") == "medication" and e["event_type"] == "task.skipped"]
    if med_completed and not med_skipped:
        lines.append(f"{horse_name} completed all scheduled medications this week.")
    elif med_skipped:
        # Frame softly — no operational guilt.
        n = len(med_skipped)
        lines.append(
            f"{horse_name} had {n} medication{'s' if n != 1 else ''} rescheduled — "
            f"the team has noted it for the vet."
        )

    # Farrier — single positive line if any completed visit
    farrier = [e for e in events_7d
               if e.get("category") == "farrier" and e["event_type"] == "task.completed"]
    if farrier:
        snap = farrier[0].get("payload_snapshot") or {}
        if snap.get("farrier_name"):
            lines.append(f"{horse_name} had a successful farrier visit with {snap['farrier_name']}.")
        else:
            lines.append(f"{horse_name} had a successful farrier follow-up.")

    # Vet — single line if any completed visit
    vet = [e for e in events_7d
           if e.get("category") == "vet" and e["event_type"] == "task.completed"]
    if vet:
        snap = vet[0].get("payload_snapshot") or {}
        title = (snap.get("title") or "vet visit").lower()
        lines.append(f"{horse_name} had a {title} this week.")

    # Rehab — single positive line
    rehab = [e for e in events_7d
             if e.get("category") == "rehab" and e["event_type"] == "task.completed"]
    if rehab:
        lines.append(f"{horse_name} completed {len(rehab)} rehab session{'s' if len(rehab) != 1 else ''}.")

    if not lines:
        return None

    # Cap at 3 lines per horse to preserve calm signal-to-noise.
    lines = lines[:3]
    return {"horse_id": horse.get("id"), "horse_name": horse_name, "lines": lines}


async def build_weekly_recap_for_owner(db, owner_user_id: str,
                                         now: Optional[datetime] = None) -> Optional[dict]:
    """Compose a calm weekly recap. Returns None if there's nothing meaningful."""
    now = now or _now()
    since_7d = now - timedelta(days=7)
    until_7d = now + timedelta(days=7)

    horses = await db.horses.find(
        {"owner_id": owner_user_id}, {"_id": 0, "id": 1, "name": 1, "barn_id": 1},
    ).to_list(50)
    if not horses:
        return None
    horse_ids = [h["id"] for h in horses]
    owner_barn = horses[0].get("barn_id", "primary")

    events_7d = await db.task_events.find(
        {
            "barn_id": owner_barn,
            "subject_horse_ids": {"$in": horse_ids},
            "category": {"$in": list(OWNER_DIGEST_CATEGORIES)},
            "event_type": {"$in": ["task.completed", "task.skipped"]},
            "occurred_at": {"$gte": _iso(since_7d)},
        },
        {"_id": 0},
    ).sort("occurred_at", -1).to_list(2000)

    upcoming = await db.tasks.find(
        {
            "barn_id": owner_barn,
            "linked_horse_ids": {"$in": horse_ids},
            "category": {"$in": ["vet", "farrier", "rehab"]},
            "status": {"$nin": ["completed", "skipped", "cancelled"]},
            "scheduled_at": {"$gte": _iso(now), "$lte": _iso(until_7d)},
        },
        {"_id": 0},
    ).sort("scheduled_at", 1).to_list(200)

    sections: List[dict] = []
    for h in horses:
        e7 = [e for e in events_7d if h["id"] in (e.get("subject_horse_ids") or [])]
        up = [t for t in upcoming if h["id"] in (t.get("linked_horse_ids") or [])]
        sec = _weekly_compose_section(h, e7, up)
        if sec:
            sections.append(sec)

    upcoming_total = len(upcoming)

    # Only send if at least one section OR there's meaningful upcoming activity.
    if not sections and upcoming_total == 0:
        return None

    return {
        "owner_user_id": owner_user_id,
        "kind": "weekly",
        "generated_at": _iso(now),
        "for_week": _iso_week_key(now),
        "sections": sections,
        "horse_count": len(horses),
        "upcoming_count": upcoming_total,
        "updates_count": sum(len(s["lines"]) for s in sections) + (1 if upcoming_total else 0),
    }


def render_weekly_recap_html(payload: dict, app_base_url: str = "") -> str:
    """Render the weekly recap with the same calm visual language as the daily digest."""
    parts = ['<!DOCTYPE html><html><head><meta charset="utf-8"><style>',
             DIGEST_CSS, '</style></head><body><div class="wrap">']
    parts.append(_brand_header_html(app_base_url, "Weekly Recap"))
    parts.append('<h1>This week at the barn</h1>')
    for sec in payload["sections"]:
        parts.append('<div class="horse">')
        parts.append(f'<div class="horse-name">{sec["horse_name"]}</div>')
        for line in sec["lines"]:
            parts.append(f'<p>{line}</p>')
        parts.append('</div>')
    if payload.get("upcoming_count"):
        n = payload["upcoming_count"]
        parts.append('<div class="horse">')
        parts.append('<div class="horse-name">Looking ahead</div>')
        parts.append(
            f'<p>{n} upcoming care appointment{"s" if n != 1 else ""} '
            f'scheduled in the next 7 days.</p>'
        )
        parts.append('</div>')
    settings_url = (app_base_url.rstrip("/") + "/settings") if app_base_url else "/settings"
    parts.append(
        f'<div class="footer">'
        f'<div class="signoff">Equine-<span class="sync">Sync</span></div>'
        f'A short Sunday update from the barn. '
        f'<a class="prefs" href="{settings_url}">Manage preferences</a>.'
        f'</div></div></body></html>'
    )
    return "".join(parts)


def render_weekly_recap_text(payload: dict) -> str:
    out = ["Equine-Sync", "Every Horse. Every Task. In Sync.", "",
           "This week at the barn", "=" * 36, ""]
    for sec in payload["sections"]:
        out.append(sec["horse_name"].upper())
        for line in sec["lines"]:
            out.append(f"  {line}")
        out.append("")
    if payload.get("upcoming_count"):
        n = payload["upcoming_count"]
        out.append("LOOKING AHEAD")
        out.append(f"  {n} upcoming care appointment{'s' if n != 1 else ''} scheduled in the next 7 days.")
        out.append("")
    out.append("Manage preferences in Settings → Notifications.")
    return "\n".join(out)


async def already_sent_this_week(db, owner_user_id: str, for_week: str) -> bool:
    rec = await db.notification_digest_log.find_one(
        {"owner_user_id": owner_user_id, "for_week": for_week},
        {"_id": 0, "id": 1},
    )
    return bool(rec)


async def send_weekly_recap_to_owner(db, mailer, owner_user_id: str,
                                       now: Optional[datetime] = None,
                                       dry_run: bool = False) -> dict:
    payload = await build_weekly_recap_for_owner(db, owner_user_id, now=now)
    if not payload:
        return {"sent": False, "reason": "no_updates"}
    owner = await db.users.find_one({"id": owner_user_id}, {"_id": 0, "email": 1, "full_name": 1})
    if not owner:
        return {"sent": False, "reason": "owner_not_found"}
    html = render_weekly_recap_html(payload, app_base_url=os.environ.get("PUBLIC_APP_URL", ""))
    text = render_weekly_recap_text(payload)
    if dry_run:
        return {"sent": False, "reason": "dry_run",
                "preview": {"html": html, "text": text, "payload": payload}}
    subject = "Equine-Sync · This week at the barn"
    try:
        send_res = mailer["send"](to=owner["email"], subject=subject, html=html, text=text)
        await db.notification_digest_log.insert_one({
            "id": __import__("uuid").uuid4().hex,
            "owner_user_id": owner_user_id,
            "sent_at": _iso(_now()),
            "for_week": payload["for_week"],
            "kind": "weekly",
            "updates_count": payload["updates_count"],
            "result": send_res,
        })
        return {"sent": True, "updates_count": payload["updates_count"], "result": send_res}
    except Exception:
        logger.exception("weekly recap send failed for owner=%s", owner_user_id)
        return {"sent": False, "reason": "send_error"}


async def run_weekly_recap_pass(db, mailer, now: Optional[datetime] = None) -> dict:
    """Run a weekly recap pass. Idempotent on (owner, ISO-week). Respects
    digest_enabled toggle (shared with daily digest — one preference governs both).
    """
    now = now or _now()
    week_key = _iso_week_key(now)
    owners = await db.users.find({"role": "horse_owner"}, {"_id": 0, "id": 1}).to_list(500)
    sent = 0
    skipped = 0
    for o in owners:
        prefs = await db.notification_preferences.find_one(
            {"user_id": o["id"]}, {"_id": 0},
        )
        if prefs and prefs.get("digest_enabled") is False:
            skipped += 1
            continue
        if await already_sent_this_week(db, o["id"], week_key):
            skipped += 1
            continue
        res = await send_weekly_recap_to_owner(db, mailer, o["id"], now=now)
        if res.get("sent"):
            sent += 1
        else:
            skipped += 1
    return {"sent": sent, "skipped": skipped, "for_week": week_key, "kind": "weekly"}
