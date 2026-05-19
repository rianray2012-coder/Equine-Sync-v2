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


def render(template: str, variables: Dict[str, Any]) -> str:
    """Render a named HTML template with simple {var} substitution wrapped in a brand layout."""
    body = _load_template(template).format_map(SafeDict(variables or {}))
    base = _load_template("_base")
    merged = {**(variables or {}), "content": body}
    return base.format_map(SafeDict(merged))


async def send(
    to: str,
    subject: str,
    template: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    html: Optional[str] = None,
    text: Optional[str] = None,
) -> Dict[str, Any]:
    """Send a transactional email. Returns {status, id?, dev?}."""
    if template:
        html = render(template, variables or {})

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
        logger.exception("Resend send failed")
        return {"status": "error", "error": str(e), "dev": False}
