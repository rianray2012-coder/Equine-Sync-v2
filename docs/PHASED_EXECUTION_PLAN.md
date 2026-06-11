# PHASED_EXECUTION_PLAN.md
# EquineSync Refactor Execution Plan

> Production priority order (from `FEATURE_ROADMAP.md`): **Security & Stability → Mobile Workflows → Care Operations → Owner Trust → Billing Clarity → Reporting → AI Assistance → Ecosystem Expansion.**

## Phase 1: Documentation & Governance
**Status: ✅ Complete** (this pass)
Goals:
- Complete the `/docs` folder (in-repo source of truth)
- Add engineering rules
- Add architecture docs
- Add product vision
- Add permission matrix
- Add trust framework
- Reconcile stale/conflicting docs (DESIGN_TOKENS → Brand Guide)
- Create a code-grounded `KNOWN_TECH_DEBT.md`
- Save brand/logo assets

## Phase 2: Security Stabilization
**Status: ✅ Complete (2026-05-30)**
- **2A — ✅:** Removed unsafe JWT fallback; centralized config (`backend/config.py`) + fail-fast startup validation; dev-safe ephemeral secret; `tests/test_config.py`.
- **2B — ✅:** Rate limiting on auth endpoints (`backend/rate_limit.py`, `limits`) + CORS tightening (prod rejects `*`); `tests/test_rate_limit.py`.
- **2C — ✅:** Password reset + email verification (hashed single-use expiring tokens, `backend/auth_tokens.py`) + Resend templates; `email_verified` with safe backfill + off-by-default `ENFORCE_EMAIL_VERIFICATION`; `GET /api/health`; `tests/test_auth_tokens.py`, `tests/test_phase2c_auth.py`.
- **2D — ✅:** Account-level brute-force lockout (`backend/login_attempts.py`, 423 on lock, clear on success); branded `/reset-password` + `/verify-email` pages + Login "Forgot password?" flow; `tests/test_login_lockout.py`.

> Full backend suite: 235 passed, 1 skipped.

## Phase 3: Backend Modularization
**Status: In Progress (3A complete)** — see `PHASE3_MODULARIZATION_MAP.md`.
- **3A — ✅ Complete (2026-05-30):** Moved `config.py`, `rate_limit.py`, `auth_tokens.py`, `login_attempts.py` → `backend/core/` (via `git mv`); updated all imports; no behavior change; `/api/health` gained a `version` field.
- **3B — Planned:** Extract system/admin/analytics routes.
- **3C–3F — Planned:** Horse → Care/Task → Owner/Report → Billing route extraction.
- **3G — Planned:** server.py reduced to app assembly; JWT/auth helpers → `core/security.py`.

Goals:
- Break `server.py` into modular route files
- Move business logic into services
- Move schemas into schema files
- Create centralized config and security utilities

## Phase 4: Multi-Tenancy & Permissions
Goals:
- Enforce `barn_id` on all operational entities
- Add tenant isolation tests
- Add centralized permission service
- Align code with `ROLE_PERMISSION_MATRIX.md`

## Phase 5: Audit Logging
Goals:
- Create `AuditLog` model
- Track critical changes
- Add audit log service
- Add tests

## Phase 6: Care Workflow Strengthening
Goals:
- Improve feeding, turnout, medication, rehab, stall rest, grooming, training workflows
- Align with `WORKFLOW_MAPS.md`

## Phase 7: Owner Trust Layer
Goals:
- Improve owner dashboard
- Add weekly recap framework
- Add owner-facing update controls
- Add approval flow for sensitive updates

## Phase 8: Mobile Optimization
Goals:
- Optimize barn workflows for phone use
- Improve task completion UX
- Improve horse profile mobile view
- Improve quick notes and photo upload

## Phase 9: Billing Improvements
Goals:
- Improve invoice structure
- Add line-item clarity
- Support recurring charges
- Improve owner billing visibility

**Status: ✅ Complete (2026-06-11)** — see [`BILLING_REFERENCE.md`](./BILLING_REFERENCE.md) for the consolidated Phase 9 billing reference.
- **9A — ✅:** Invoice line-item integrity & server-computed totals (`compute_money`, client total ignored).
- **9B-1 — ✅:** Recurring charge model + CRUD (barn-scoped, `recurring_charge:manage`).
- **9B-2 — ✅:** Manual idempotent materializer (`POST /admin/recurring-charges/run`), partial unique index, monotonic `last_run_period`, `billing_run` audit.
- **9C — ✅:** Invoice clarity UI (staff accordions + owner read-only breakdown).
- **9D — ✅ Complete:** Billing docs/test consolidation — `BILLING_REFERENCE.md`, shared `tests/_billing_helpers.py`, and API-env fallback fixes in `test_operations_routes.py` / `test_onboarding.py` / `test_invites_and_analytics.py` (docs + tests only; no product code change).

## Phase 10: Production Readiness
Goals:
- Add release checklist enforcement (`RELEASE_CHECKLIST.md`)
- Improve logging
- Add monitoring
- Prepare deployment checklist

**Status: In Progress** — sub-phased 10A → 10D, each gated separately.
- **10A — ✅ Complete (2026-06-11):** Structured logging & request correlation. New `core/logging_config.py` (contextvars + `ContextFilter` + `RedactionFilter` + JSON/plain formatters) and **pure-ASGI** `core/middleware.py` (`RequestContextMiddleware`): additive `X-Request-ID` header, one request-completion log per request, best-effort `user_id`/`barn_id` correlation set in `get_current_user` (exception-safe, no auth change). `LOG_FORMAT` json(prod)/plain(dev) with override; secrets/headers/bodies/query never logged. **No response/status/auth/CORS/frontend changes.** See [`OBSERVABILITY.md`](./OBSERVABILITY.md). Suite **575 passed / 3 skipped**.
- **10B — Planned:** Health/observability hardening (liveness vs readiness).
- **10C — Planned:** Release-checklist enforcement + deploy readiness (`deployment_agent` scan, `PRODUCTION_READINESS.md`).
- **10D — Planned:** Phase 10 docs/test consolidation + dependency audit.

**Deferred (separately gated):** P1 localStorage→httpOnly cookie auth migration (own phase); P2 palette reconciliation (Tech Debt #11); Phase 5E audit backlog.
