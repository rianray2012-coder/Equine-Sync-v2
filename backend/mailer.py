"""
Email layer for EquineSync.

Design goals:
- Single send() entry-point usable from any endpoint.
- Provider-agnostic: today Resend, tomorrow could be SES/Postmark.
- Dev mode (no RESEND_API_KEY) logs the message body so the flow still works
  end-to-end without external dependencies.
- Templates live in /app/backend/email_templates/*.html and are simple
  str.format_map(SafeDict()) substitutions to avoid template engine overhead.
- Branded base layout wraps every email for a consistent luxury aesthetic.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("equinesync.mailer")

TEMPLATES_DIR = Path(__file__).parent / "email_templates"


class SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _load_template(name: str) -> str:
    fp = TEMPLATES_DIR / f"{name}.html"
    if not fp.exists():
        raise FileNotFoundError(f"Template not found: {name}")
    return fp.read_text(encoding="utf-8")


def render(template: str, variables: Dict[str, Any], base: str = "_base") -> str:
    """Render a named HTML template with simple {var} substitution wrapped in a brand layout.

    ``base`` selects the wrapping layout (default ``_base``; auth/transactional
    emails use ``_base_auth`` which has a neutral, non-invite footer).
    """
    body = _load_template(template).format_map(SafeDict(variables or {}))
    base_tpl = _load_template(base)
    merged = {**(variables or {}), "content": body}
    return base_tpl.format_map(SafeDict(merged))


async def send(
    to: str,
    subject: str,
    template: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    html: Optional[str] = None,
    text: Optional[str] = None,
    base: str = "_base",
) -> Dict[str, Any]:
    """Send a transactional email. Returns {status, id?, dev?}."""
    if template:
        html = render(template, variables or {}, base=base)

    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    sender = os.environ.get("RESEND_FROM", "EquineSync <onboarding@resend.dev>")

    if not api_key:
        logger.warning(
            "[mailer:DEV] Email NOT sent (RESEND_API_KEY missing). to=%s subject=%s preview=%s",
            to, subject, (html or "")[:160].replace("\n", " ") + "…",
        )
        return {"status": "dev_logged", "dev": True}

    import resend  # local import keeps optional dep light
    resend.api_key = api_key
    params = {"from": sender, "to": [to], "subject": subject}
    if html: params["html"] = html
    if text: params["text"] = text

    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        return {"status": "sent", "id": result.get("id"), "dev": False}
    except Exception as e:
        msg = str(e)
        logger.warning("Resend send failed: %s", msg)
        # Sandbox mode: API works but recipient not allowed. Treat like dev mode so the
        # caller surfaces the magic link to the inviter for manual sharing.
        sandbox = "verify a domain" in msg.lower() or "testing emails" in msg.lower()
        return {"status": "sandbox" if sandbox else "error", "error": msg, "dev": sandbox}
