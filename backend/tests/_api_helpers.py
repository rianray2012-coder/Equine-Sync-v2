"""Shared API base-URL helper for the cross-cutting integration suites (Phase 10D).

Resolves `REACT_APP_BACKEND_URL` (env first, then a `frontend/.env` fallback)
and exposes `BASE` / `API`. Raises a clear error if it is unset — never points
at a dead default. This consolidates the identical `_base_url()` that the
non-domain suites previously each inlined.

Domain suites keep their own richer helpers (`_billing_helpers.py`,
`_owner_helpers.py`, `_care_helpers.py`); this module is intentionally tiny and
only owns base-URL resolution for suites that don't belong to a domain helper.
"""
from __future__ import annotations

import os
import pathlib


def base_url() -> str:
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    env = pathlib.Path(__file__).resolve().parents[2] / "frontend" / ".env"
    if env.is_file():
        for line in env.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


BASE = base_url()
API = f"{BASE}/api"
