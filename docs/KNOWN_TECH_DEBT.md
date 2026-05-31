# KNOWN_TECH_DEBT.md
# EquineSync Known Tech Debt

> **Code-grounded (Phase 1 documentation pass, 2026-05-30).** Every item below was verified against the live codebase and references the actual file/line where observed. This is the authoritative debt register that feeds `PHASED_EXECUTION_PLAN.md`. No code was changed during this pass.

---

## 1. JWT Secret Fallback — **Severity: Critical** — ✅ RESOLVED (Phase 2A, 2026-05-30)
- **Observed:** `backend/server.py:70` → `JWT_SECRET = os.environ.get('JWT_SECRET', 'change-me')` and `backend/routes/auth.py:31` → identical fallback. The secret was also duplicated across two modules.
- **Risks:** Token forgery / authentication bypass if `JWT_SECRET` is unset in any environment; secret drift between the two definitions.
- **Resolution:** Created `backend/config.py` as the single source of truth. Both `server.py` and `routes/auth.py` now import `JWT_SECRET`/`JWT_ALG` from it — the `'change-me'` fallback is removed everywhere. `validate_config()` runs at startup and **fails fast in production** when `JWT_SECRET` (or `MONGO_URL`/`DB_NAME`) is missing or insecure (placeholder / < 16 chars). In development it falls back to a clearly-logged ephemeral per-process secret. Covered by `backend/tests/test_config.py` (18 tests). Verified: login + `/auth/me` + 20 `test_phase2.py` integration tests pass.

## 2. Backend Monolith — **Severity: High** — 🟡 IN PROGRESS (Phase 3)
- **Observed:** `backend/server.py` is **~800 lines**. Target modular dirs partially created: **`core/` now exists** (Phase 3A: `config`, `rate_limit`, `auth_tokens`, `login_attempts`); `models`/`schemas`/`services` still pending. Routes partially extracted into `backend/routes/*.py`.
- **Risks:** Merge conflicts, difficult testing, difficult scaling, architectural drift.
- **Recommended Action:** Continue per `PHASE3_MODULARIZATION_MAP.md` (3B system → 3G app-assembly). **(Phase 3)**

## 3. Incomplete Multi-Tenant Enforcement — **Severity: High**
- **Observed:** `barn_id` appears in only **one** route module (`backend/routes/invites.py`, 5 occurrences) and **zero** times in `server.py`, `care.py`, `operations.py`, `onboarding.py`, `dashboard.py`, `reports.py`, `auth.py`. The `User` document created in `routes/auth.py:133-140` has **no `barn_id`** field. The platform effectively assumes a single barn.
- **Risks:** Cross-tenant data exposure once multiple barns exist; no tenant scoping on queries.
- **Recommended Action:** Add `barn_id` to all operational entities + `User`; scope every query by `barn_id`; add tenant-isolation tests. **(Phase 4)**

## 4. Inconsistent / Missing Permission Logic — **Severity: High**
- **Observed:** Only one permission primitive exists: `require_setup_role(user)` in `routes/auth.py:87` (admin/barn_manager gate). There is **no centralized permission service** and the `ROLE_PERMISSION_MATRIX.md` is not enforced. Most routes perform no role-based authorization beyond authentication.
- **Risks:** Inconsistent authorization, privilege escalation, security gaps.
- **Recommended Action:** Build a centralized permission service aligned with `ROLE_PERMISSION_MATRIX.md`; remove ad-hoc inline checks; add permission tests. **(Phase 4)**

## 5. Hard Deletes Instead of Soft Deletes — **Severity: Medium**
- **Observed:** `routes/onboarding.py` DELETE endpoints use hard `delete_one` for locations (`:244`), feed-templates (`:262`), inventory (`:286`), recurring-schedules (`:304`), staff-invites (`:332`). `API_CONTRACTS.md` mandates **soft delete only**.
- **Risks:** Irreversible data loss; breaks audit/accountability expectations.
- **Recommended Action:** Convert to soft-delete (`status`/`deleted_at` flag) and filter on read. **(Phase 4/5)**

## 6. Inconsistent API Responses — **Severity: Medium**
- **Observed:** No standardized `{success, data, error}` envelope. Only sporadic partial usage (`routes/invites.py:268`, `routes/onboarding.py:150` include a `"data": {}` field); most endpoints return raw objects.
- **Risks:** Frontend complexity, inconsistent error handling.
- **Recommended Action:** Implement a shared response contract + exception handler. Coordinate with `API_VERSIONING.md` (non-breaking rollout). **(Phase 3)**

## 7. No Audit Logging — **Severity: Medium**
- **Observed:** No `AuditLog` model/collection or audit service exists in `backend/`. `OWNER_TRUST_FRAMEWORK.md` and `ROLE_PERMISSION_MATRIX.md` both assume audit trails.
- **Risks:** Reduced accountability, poor debugging, legal/compliance gaps.
- **Recommended Action:** Create immutable `AuditLog` (see `DATA_MODEL.md`) + audit service + tests. **(Phase 5)**

## 8. Missing Security Hardening — **Severity: High (security)** — 🟡 PARTIALLY RESOLVED (Phase 2B, 2026-05-30)
- **Observed:** No rate limiting; CORS defaulted to `*` (`server.py` → `os.environ.get('CORS_ORIGINS', '*')`); no email verification or password-reset endpoints (`routes/auth.py` exposes register/login/refresh/logout/me only). `SecurityHeadersMiddleware` + refresh-token rotation **are** implemented (`auth_security.py`) — good baseline.
- **Resolved (Phase 2B):** Added IP-based rate limiting on `/api/auth/login|register|refresh` via a FastAPI dependency (`backend/rate_limit.py`, `limits` library, env-driven: strict in prod `5/minute`, generous in dev to avoid throttling tests). Tightened CORS: `config.get_cors_origins()` **rejects `*`/empty in production** (validated at startup), defaults to `*` only in development. Covered by `tests/test_rate_limit.py` + CORS/rate-limit unit tests in `tests/test_config.py`.
- **Resolved (Phase 2C, 2026-05-30):** Added **password reset** (`/api/auth/forgot-password` + `/api/auth/reset-password`) and **email verification** (`/api/auth/verify-email` + `/api/auth/resend-verification`) via hashed, single-use, expiring tokens (`backend/auth_tokens.py`) and Resend email templates. Added `email_verified` to `User` with a **safe startup backfill** (existing users → `True`, no lockout) and an off-by-default `ENFORCE_EMAIL_VERIFICATION` gate. Added `GET /api/health` readiness probe (config + DB, no secrets). Covered by `tests/test_auth_tokens.py` + `tests/test_phase2c_auth.py`.
- **Resolved (Phase 2D, 2026-05-30):** Added account-level brute-force lockout (`backend/login_attempts.py`, `login_attempts` collection): N failures within a window lock the account temporarily (login returns `423`); a successful login clears the counter. Env-driven (`LOGIN_LOCKOUT_ENABLED`/`MAX_ATTEMPTS`/`LOCKOUT_MINUTES`/`WINDOW_MINUTES`). Built branded frontend pages `/reset-password` + `/verify-email` (Brand Guide 22) and a "Forgot password?" flow on Login. Covered by `tests/test_login_lockout.py`.
- **Still open:** Multi-replica rate-limit/lockout store (Redis) if/when horizontally scaled.

## 9. Incomplete Test Coverage — **Severity: Medium**
- **Observed:** `backend/tests/` exists with `_test_creds.py`, `test_dispatch_retry.py`, `__init__.py` (per handoff, 175 backend tests pass) but lacks dedicated permission, tenant-isolation, and billing test suites.
- **Risks:** Regression bugs, unstable refactors.
- **Recommended Action:** Add auth, permission, tenant-isolation, billing, and care-workflow tests. **(Phases 2/4)**

## 10. Missing Structured Logging — **Severity: Medium**
- **Observed:** Standard `logging` used without consistent request/tenant/user-id correlation fields.
- **Risks:** Difficult debugging, poor observability.
- **Recommended Action:** Centralized structured logging with request IDs, tenant IDs, user IDs. **(Phase 10)**

## 11. Design-Token Drift (frontend) — **Severity: Low/Medium**
- **Observed:** Live `frontend/src/index.css` + `tailwind.config.js` use a sibling "lavender pearl / charcoal navy" palette (navy `#2E3448`, bg `#F7F5FA`, lavender `#C7B6D9`, accent `#A7B7E7`) that approximates but does not exactly match the authoritative Brand Guide (`#232734 / #2E3550 / #F7F8FA / #B8AECF`). Cormorant Garamond display face not yet wired.
- **Risks:** Visual inconsistency vs brand; future rework.
- **Recommended Action:** Reconcile live CSS variables + Tailwind theme to `DESIGN_TOKENS.md`; load Cormorant Garamond. **(Phase 8)**

## 12. Duplicate UI Components — **Severity: Medium**
- **Observed:** No `components/features/` separation; feature components live flat in `frontend/src/components/`. Potential overlap to audit (e.g. card/badge primitives).
- **Risks:** Inconsistent UX, maintenance difficulty.
- **Recommended Action:** Establish `components/features/` structure; audit and de-duplicate. **(Phase 3/8)**

## 13. Limited Mobile Optimization — **Severity: Medium**
- **Observed:** Per handoff, significant mobile polish done (`QuickAddSheet`, thumb-zone work) but full workflow audit pending against `WORKFLOW_MAPS.md` mobile-priority items (feeding "very high").
- **Recommended Action:** Audit all core workflows for mobile-first use. **(Phase 8)**

## 14. Dependency Bloat — **Severity: Low**
- **Observed:** Frontend dependency stack not yet audited for overlap.
- **Recommended Action:** Audit and consolidate where possible. **(Phase 10)**

## 15. Documentation Gaps — **Severity: Medium (now largely addressed)**
- **Observed:** Governance docs now materialized in `/app/docs` (this pass). Ongoing: keep `ARCHITECTURE.md`, `API_CONTRACTS.md`, `DATA_MODEL.md`, `FEATURE_ROADMAP.md` current with each change.
- **Recommended Action:** Continuous doc updates per `SCHEMA_CHANGE_POLICY.md` and `AI_CODING_PROMPTS.md`.

---

## Future Considerations (not actionable now)
- **Scaling MongoDB Relationships** — evaluate long-term relational needs before major scaling (reporting/permission/billing complexity).
- **Background Job Infrastructure** — async workflows (email queues, AI summaries, scheduled reports, reminders) may eventually need Celery/Redis. Note: a lightweight in-process scheduler already runs in `server.py` (task materializer, notifications, owner digest/recap, nudges) gated by `DISABLE_*` env flags.
- **Dashboard Information Density** — maintain strong UX hierarchy and progressive disclosure as features expand.
