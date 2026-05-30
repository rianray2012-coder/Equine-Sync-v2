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
**Status: In Progress**
- **2A — ✅ Complete (2026-05-30):** Removed unsafe JWT fallback (`JWT_SECRET='change-me'`); added centralized config (`backend/config.py`) + fail-fast startup validation (`validate_config()`); documented dev-safe ephemeral-secret behavior; added `backend/tests/test_config.py`.
- **2B — ✅ Complete (2026-05-30):** Rate limiting on auth endpoints (`backend/rate_limit.py`, `limits` library, FastAPI dependency, env-driven limits) + CORS tightening (`config.get_cors_origins()` rejects `*` in production). Added `backend/tests/test_rate_limit.py` + CORS/rate-limit unit tests. (Note: implemented via `limits` dependency, not slowapi's decorator, which is incompatible with FastAPI 0.110 + Pydantic v2 bodies.)
- **2C — ✅ Complete (2026-05-30):** Password reset + email verification via hashed single-use expiring tokens (`backend/auth_tokens.py`) + Resend templates; `email_verified` field with safe startup backfill (no lockout) + off-by-default `ENFORCE_EMAIL_VERIFICATION`; `GET /api/health` readiness probe. Tests: `tests/test_auth_tokens.py`, `tests/test_phase2c_auth.py`.
- **2D — Planned:** Account-level brute-force lockout (MongoDB `login_attempts`) + expanded auth/permission test coverage.

## Phase 3: Backend Modularization
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

## Phase 10: Production Readiness
Goals:
- Add release checklist enforcement (`RELEASE_CHECKLIST.md`)
- Improve logging
- Add monitoring
- Prepare deployment checklist
