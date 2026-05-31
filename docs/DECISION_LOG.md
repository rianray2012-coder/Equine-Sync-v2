# DECISION_LOG.md
# Decision Log

## Purpose
Track important architectural and product decisions. Document: decision, reason, risks, alternatives considered, review date.

## Template
```
Date:
Decision:
Reason:
Alternatives Considered:
Risks:
Review Date:
Status:
```

---

## Entries

### 2026-05-30 — Use MongoDB for initial scaling
- **Decision:** Use MongoDB as the primary datastore for the initial platform.
- **Reason:** Flexible schema during rapid product development and growth.
- **Alternatives Considered:** PostgreSQL (relational).
- **Risks:** Complex reporting and relational joins later (see `KNOWN_TECH_DEBT.md` → "Scaling MongoDB Relationships").
- **Review Date:** 2027-Q1
- **Status:** Active

### 2026-05-30 — Brand Guide is the authoritative visual source of truth
- **Decision:** `BRAND_AND_LOGO_GUIDE.md` (Brand Guide 22) is the single source of truth for palette and typography. `DESIGN_TOKENS.md` reconciled to match: Midnight Graphite `#232734`, Slate Navy `#2E3550`, Frost White `#F7F8FA`, Smoky Lilac `#B8AECF`; Cormorant Garamond (display) + Inter (UI); identity line "Every Horse. Every Task. In Sync."
- **Reason:** The earlier `DESIGN_TOKENS.md` (Warm Ivory / Saddle Brown / Muted Gold) conflicted with the Brand Guide and UI System. One authoritative palette is required before any UI work.
- **Alternatives Considered:** Keeping the Warm Ivory/Saddle Brown palette; merging the two.
- **Risks:** Live frontend currently uses a sibling palette and will need reconciliation in Phase 8 (UI). The deprecated warm palette may be reintroduced later only as an explicit secondary seasonal/accent palette.
- **Review Date:** Phase 8 (Mobile/UI optimization)
- **Status:** Active

### 2026-05-30 — Governance docs live at project-root /docs (/app/docs)
- **Decision:** The in-repo source-of-truth documentation lives at the project-root `/docs`, physically `/app/docs` in this Emergent workspace. `MASTER_INDEX.md` and `EMERGENT_START_PROMPT.md` note the path equivalence.
- **Reason:** Matches the Start Prompt's `/docs` reference; the existing `/app/memory` folder holds historical founder-beta artifacts and is retained for reference.
- **Alternatives Considered:** Consolidating into `/app/memory`.
- **Risks:** Two doc locations (`/app/docs` governance vs `/app/memory` history) — mitigated by `MASTER_INDEX.md` being the single entry point.
- **Review Date:** Phase 10
- **Status:** Active

### 2026-05-30 — Phase 3A: core package (config/security helpers)
- **Decision:** Created `backend/core/` and moved `config.py`, `rate_limit.py`, `auth_tokens.py`, `login_attempts.py` into it via `git mv` (history preserved). Updated all importers (`server.py`, `routes/auth.py`, 4 test files, internal `core.rate_limit`→`core.config`). `/api/health` gained a non-breaking `version` field (`APP_VERSION`, default `0.1.0`). No API/frontend behavior change.
- **Reason:** First safe step of Phase 3 modularization (see `PHASE3_MODULARIZATION_MAP.md`); establishes a clean cross-cutting `core` package before splitting `server.py`.
- **Alternatives Considered:** Leaving re-export shims at the old paths (rejected — anti-pattern); moving routes first (rejected — higher blast radius).
- **Risks:** Import-path churn — mitigated by a contained import graph (only 6 importers) and a full regression run (235 passed, 1 skipped).
- **Review Date:** Phase 3G
- **Status:** Active

### 2026-05-30 — Phase 2D: Brute-force lockout + reset/verify frontend pages
- **Decision:** Added account-level brute-force lockout (`backend/login_attempts.py`, `login_attempts` collection): after `LOGIN_MAX_ATTEMPTS` (default 5) failures within `LOGIN_ATTEMPT_WINDOW_MINUTES`, login returns **423** for `LOGIN_LOCKOUT_MINUTES`; a successful login clears the counter. Built branded **Brand Guide 22** frontend pages `/reset-password` and `/verify-email` (token from URL, clear success/error states, resend option) and a minimal "Forgot password?" inline flow on Login. Added Cormorant Garamond + Inter weights.
- **Reason:** Closes the brute-force gap (KNOWN_TECH_DEBT #8) and makes the 2C reset/verify email links land on real, on-brand pages.
- **Alternatives Considered:** IP-only lockout (rejected — punishes shared NATs; per-account is the playbook approach); blocking-by-default email enforcement (still off). slowapi-style global limiter (already covered separately in 2B).
- **Risks:** Lockout is enabled in dev — verified the test suite's two single-failure admin tests stay well under the threshold and success clears the counter (admin remains able to sign in). Per-process `login_attempts` is in MongoDB (shared), so it works across replicas (unlike the in-memory rate limiter).
- **Review Date:** Phase 10 (scaling)
- **Status:** Active

### 2026-05-30 — Phase 2C: Password reset, email verification, /api/health
- **Decision:** Added password reset + email verification using **hashed, single-use, expiring** tokens (`backend/auth_tokens.py`, `auth_tokens` collection) and Resend templates (neutral `_base_auth` layout). Added `email_verified` to `User`. Email verification is **non-blocking by default**: existing users are backfilled to `email_verified=True` at startup, reads default missing→verified, and login enforcement is gated behind `ENFORCE_EMAIL_VERIFICATION` (default `false`). Forgot-password returns a uniform response (no email enumeration) and exposes a `dev_token` **only** when not production. Added `GET /api/health` readiness probe (DB + config booleans, no secrets).
- **Reason:** Completes the user-facing security flows (KNOWN_TECH_DEBT #8) without risking lockout of demo/admin/existing users.
- **Alternatives Considered:** Blocking login for unverified users by default (rejected — lockout risk); storing raw tokens (rejected — hash at rest); two separate token collections (rejected — single `auth_tokens` with `purpose`).
- **Risks:** Email links target frontend routes (`/reset-password`, `/verify-email`) not yet built — API is fully functional/testable via `dev_token`. `dev_token` must never be exposed in production (guarded by `is_production()`).
- **Review Date:** When frontend reset/verify pages are built.
- **Status:** Active

### 2026-05-30 — Phase 2B: Auth rate limiting + CORS tightening
- **Decision:** Added IP-based rate limiting to `/api/auth/login|register|refresh` and tightened CORS so production cannot use `*`. Rate limiting implemented as a FastAPI **dependency** using the `limits` library (`backend/rate_limit.py`), env-driven (`RATE_LIMIT_ENABLED`, `AUTH_RATE_LIMIT`; strict `5/minute` in prod, generous `1000/minute` in dev). CORS resolved via `config.get_cors_origins()`, validated at startup.
- **Reason:** Mitigates brute-force/credential-stuffing and removes the permissive `*` CORS in production (KNOWN_TECH_DEBT #8, partial).
- **Alternatives Considered:** slowapi decorator (rejected — incompatible with FastAPI 0.110 + Pydantic v2 bodies, produced spurious 422s); MongoDB `login_attempts` account lockout (deferred to 2D as a complementary layer).
- **Risks:** `limits` memory store is per-process — a multi-replica deployment would need a shared store (Redis). Production must set explicit `CORS_ORIGINS` or startup fails.
- **Review Date:** Phase 10 (scaling)
- **Status:** Active

### 2026-05-30 — Phase 2A: Centralized config + fail-fast JWT secret (no insecure fallback)
- **Decision:** Introduced `backend/config.py` as the single source of truth for security-critical settings. Removed the `JWT_SECRET='change-me'` fallback from `server.py` and `routes/auth.py`. `validate_config()` runs at startup: **production fails fast** if `JWT_SECRET`/`MONGO_URL`/`DB_NAME` are missing or if `JWT_SECRET` is insecure; **development** uses a logged ephemeral secret to preserve usability. Added `APP_ENV` toggle.
- **Reason:** Closes `KNOWN_TECH_DEBT.md` item #1 (Critical). Prevents token forgery / auth bypass from a default secret and eliminates secret drift between two modules.
- **Alternatives Considered:** Direct `os.environ["JWT_SECRET"]` everywhere (no dev ergonomics); a full `core/` package (deferred to Phase 3 modularization).
- **Risks:** Production deploys MUST set a strong `JWT_SECRET` or startup will (intentionally) fail. Dev ephemeral secret invalidates sessions on restart.
- **Review Date:** Phase 3 (when `config.py` moves into `core/`)
- **Status:** Active

### 2026-05-30 — Phase 1 is documentation-only (no runtime changes)
- **Decision:** The Phase 1 governance pass creates/reconciles documentation and saves brand assets only. No backend or frontend runtime behavior is changed.
- **Reason:** Establish a checkable source of truth before any code changes (Security Phase 2 next), per user directive.
- **Risks:** None to runtime; identified code gaps remain open until their sequenced phases.
- **Review Date:** Start of Phase 2
- **Status:** Active
