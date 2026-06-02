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

### 2026-06-02 — Phase 3C: Horse-profile route extraction
- **Decision:** Extracted the four horse-profile CRUD endpoints (`GET/POST /horses`, `GET/PATCH /horses/{id}`) and the `HorseIn` model from `routes/care.py` into a dedicated **`routes/horses.py`** (`build_router` factory, same injected deps). Behavior-preserving: identical paths, bodies, response shapes, status codes, and auth; **no new validation or permission logic**. `GET /horses/{id}/timeline` was **intentionally left in `task_engine.py`** because it is a task-event projection/aggregation, not horse-profile CRUD. Owners, riders, and clinical records (medications/feed/vet/farrier/injuries/wellness) remain in `care.py` (owners slated for 3E).
- **Reason:** The horse is the central domain entity; a dedicated module matches the modularization map and de-clutters the `care.py` grab-bag. Verified `HorseIn` was used nowhere else before moving it.
- **Alternatives Considered:** Re-homing the timeline under the horses router by delegating to the task engine (rejected — would entangle task-engine internals for no client benefit; the URL is unchanged either way); moving riders along with horses (rejected — riders are not horse-profile routes; kept 3C tightly scoped).
- **Risks:** Very low — mechanical move of 4 handlers + 1 model + one `include_router` wiring; removed now-dead `care.py` imports (`HTTPException`, `Any`, `Dict`). No schema/data/index changes; no frontend changes. New `tests/test_horses_routes.py`; existing horse-touching tests (`test_care_routes`, `test_task_engine`, etc.) unchanged and green. Full suite **271 passed, 3 skipped** (one pre-existing flaky `test_dispatch_retry` passed on clean re-run — shared-DB isolation issue, unrelated to 3C).
- **Review Date:** Phase 3D.
- **Status:** Active

### 2026-05-31 — Phase 3B: System/Admin/Analytics route extraction
- **Decision:** Extracted three low-risk inline route groups from `server.py` into dedicated routers, behavior-preserving: `routes/system.py` (`GET /`, `GET /health`), `routes/admin.py` (`POST /seed` 2E-hardened + `POST /admin/tenant-reset`), `routes/analytics.py` (`POST /events`, `GET /events/onboarding-funnel`). The destructive seed routine was moved to a self-contained `seed_data.py::run_seed(db)` called by **both** the startup auto-seed and the guarded route. `GET /api/health` gained an **additive, booleans-only** `dependencies` block (`mailer_configured`, `email_verification_enforced`, `rate_limiting_enabled`, `auto_seed_enabled`, `seed_route_enabled`) — no secrets/URLs/keys. `server.py` 891 → 524 lines.
- **Reason:** Continue Phase 3 modularization; co-locating the 2E seed/admin guards in one auditable module reduces the chance of reintroducing an unguarded destructive route. The health booleans give ops read-only posture visibility.
- **Alternatives Considered:** Moving `_track` into analytics now (rejected — it's injected into 6+ routers; deferred to 3G as shared infra); keeping `run_seed` inside `admin.py` (rejected — a standalone module decouples it cleanly from both the route and app-assembly); moving the digest/recap admin run-now tools in 3B (rejected per approval — they move with the digest feature area in 3E).
- **Risks:** The only non-trivial move was `_run_seed` → `seed_data.run_seed` (two call sites updated in one change). No schema/data migration; no path/response/auth/status changes except the additive health field. Removed now-dead imports (`JSONResponse`, `is_production`, `allow_seed_route`, `evaluate_seed_access`, `enforce_email_verification`) from `server.py`. New tests: `test_system_routes.py` (incl. no-secret-leak), `test_admin_routes.py`, `test_analytics_routes.py`. Full suite **265 passed, 3 skipped**.
- **Review Date:** Phase 3G (app-assembly cleanup).
- **Status:** Active

### 2026-05-31 — Security Patch 2E hardening: prod-seed lockdown + verification defense-in-depth
- **Decision:** Final hardening pass on Patch 2E before GitHub save (scope held narrow; no Phase 3B). (1) **`POST /api/seed` is blocked entirely in production** (`404`) regardless of `ALLOW_SEED_ROUTE`; outside production it requires authenticated **admin** + explicit `{"confirm":"SEED"}` body. The decision is a pure, unit-tested function `core.config.evaluate_seed_access`. (2) **Startup auto-seed is disabled in production** via `core.config.auto_seed_enabled` (default off in prod, on in dev/test; `ALLOW_AUTO_SEED` overrides) so a fresh prod DB never auto-creates demo accounts. (3) **Email-verification enforcement is now also applied inside `get_current_user`** (both the `server.py` and `routes/auth.py` dependencies) via `core.config.user_verification_ok`: when `ENFORCE_EMAIL_VERIFICATION=true`, an unverified/pre-issued token is rejected with `403`; missing `email_verified` stays treated as verified for legacy users.
- **Reason:** Codex follow-up review flagged that (a) auto-seed could populate a production DB, (b) production should categorically refuse the destructive route, and (c) issuance-gating alone doesn't cover a token minted before enforcement was toggled on. Adding the dependency-level gate makes verification enforcement complete end-to-end.
- **Alternatives Considered:** Keeping admin-in-prod seed access (rejected — user preferred blocking prod entirely); enforcing verification only at login/register (rejected — leaves a window for pre-issued tokens); a DB migration to force-verify all users (unnecessary — missing-field-treated-as-verified already protects legacy users).
- **Risks:** Toggling enforcement on still won't retroactively *delete* sessions, but now every protected request re-checks `email_verified`, so unverified holders are blocked immediately. `ALLOW_AUTO_SEED`/`ALLOW_SEED_ROUTE` must stay unset in production. End-to-end proven (register→403→verify→200) and reverted; suite 250 passed / 3 skipped.
- **Review Date:** Phase 4 (centralized permissions).
- **Status:** Active

### 2026-05-31 — Security Patch 2E: seed lockdown + registration role escalation + verification gate
- **Decision:** Emergency security patch (out-of-band, before resuming Phase 3B) addressing a GitHub/Codex security review. Three changes: (1) `POST /api/seed` is gated by a new `ALLOW_SEED_ROUTE` env flag (default `false` → route returns `404`); when enabled it additionally requires an authenticated **admin** under `APP_ENV=production`. The destructive seed logic was split into an internal `_run_seed()` so the startup auto-seed is unchanged. (2) Public `POST /api/auth/register` no longer trusts a client `role` (it previously defaulted to `admin`) — it forces `PUBLIC_REGISTRATION_ROLE = "horse_owner"`. The `role` field is accepted-but-ignored to keep the request schema lenient. (3) Registration session issuance is gated by `should_issue_session_on_register(email_verified, enforce)` — when `ENFORCE_EMAIL_VERIFICATION=true`, an unverified registrant gets a `pending_verification` response with no tokens.
- **Reason:** A publicly reachable anonymous data-wipe route and a public path to mint `admin` accounts are critical pre-onboarding risks. Token-issuance gating is the correct enforcement point for stateless JWT (no token ⇒ no protected access).
- **Alternatives Considered:** Deleting `/api/seed` entirely (rejected — still useful for dev/demo reseed behind the flag); hard-rejecting any `role` in the body with 400 (rejected — chose silent-ignore so the existing lenient clients/tests don't break); adding an `email_verified` check inside `get_current_user` (deferred — gating issuance already prevents unverified sessions; a dependency-level check is a future defense-in-depth item).
- **Risks:** Toggling `ENFORCE_EMAIL_VERIFICATION` on does not retroactively invalidate already-issued tokens (4h TTL) — documented; not a concern while enforcement stays off by default. `ALLOW_SEED_ROUTE` must remain `false` (unset) in production.
- **Review Date:** Phase 4 (centralized permissions) — fold registration/role policy into the permission service.
- **Status:** Active

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
