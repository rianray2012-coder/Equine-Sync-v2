# PRODUCTION_READINESS.md
# EquineSync — Production Readiness (Phase 10C)

> **Phase 10C — deployment-readiness review (2026-06-11).** This document is the
> **current evidence map, verification results, findings, deferrals, and launch
> status** for the items in [`RELEASE_CHECKLIST.md`](./RELEASE_CHECKLIST.md).
> `RELEASE_CHECKLIST.md` remains the stable operator checklist; this file is the
> Phase 10C evidence layer that references it. No product/runtime/config/security
> code was changed in 10C.
>
> **Phase 10 doc set:** [`OBSERVABILITY.md`](./OBSERVABILITY.md) (logging + health probes) ·
> this file (deployment evidence) · [`DEPENDENCY_AUDIT.md`](./DEPENDENCY_AUDIT.md) (10D dependency audit) ·
> [`PHASED_EXECUTION_PLAN.md`](./PHASED_EXECUTION_PLAN.md) (phase status).

## Launch status — ✅ READY (no deployment blockers)
- **Static deploy scan (`deployment_agent`): PASS, `findings: []`.** Compilation OK; env files OK; frontend API URLs read from `REACT_APP_BACKEND_URL` only; backend DB from `MONGO_URL`/`DB_NAME` only; no hardcoded secrets/URLs; all backend routes under `/api`; supervisor config valid (backend `0.0.0.0:8001`, frontend `3000`); no `load_dotenv(override=True)`; CORS `*` in dev (auto-tightened at deploy / prod-rejected in code).
- **Backend test suite: 582 passed / 3 skipped** (as of Phase 10B).

Legend: ✅ evidenced · ⚠️ partial/operational · ⛳ deferred (backlog).

---

## Security
| Checklist item | Status | Evidence |
|---|---|---|
| JWT secret verified (no fallback) | ✅ | `core/config.py` (`JWT_SECRET`, no `change-me`); `validate_config()` fail-fast in prod; `tests/test_config.py` |
| Environment variables validated | ✅ | `core/config.validate_config()` at startup (`server.py`); `tests/test_config.py` |
| Rate limiting enabled | ✅ | `core/rate_limit.py` on `/auth/login|register|refresh`; `tests/test_rate_limit.py`; `/health` `dependencies.rate_limiting_enabled` |
| Email verification working | ✅ | `core/auth_tokens.py`, `/auth/verify-email` + `/resend-verification`; `tests/test_phase2c_auth.py` |
| Password reset working | ✅ | `/auth/forgot-password` + `/reset-password`; `tests/test_auth_tokens.py`, `test_phase2c_auth.py` |
| Permissions verified | ✅ | `core/permissions.py`; `tests/test_permissions.py`, `test_permissions_wiring.py` |
| `ALLOW_SEED_ROUTE` unset/false in prod (`/api/seed` 404; blocked entirely in prod) | ✅ | `core/config.evaluate_seed_access`; `tests/test_security_patch_2e.py`; `/health` `dependencies.seed_route_enabled` (effective=false in prod) |
| Startup auto-seed disabled in prod | ✅ | `core/config.auto_seed_enabled`; `core/lifespan.py` guard; `tests/test_security_patch_2e.py` |
| Public registration cannot create privileged roles | ✅ | `PUBLIC_REGISTRATION_ROLE="horse_owner"`; `tests/test_security_patch_2e.py` |
| `ENFORCE_EMAIL_VERIFICATION=true` withholds session + 403 on unverified | ✅ | `core/config.user_verification_ok` in both `get_current_user`; `tests/test_security_patch_2e.py` |
| Brute-force lockout | ✅ | `core/login_attempts.py` (423 on lock); `tests/test_login_lockout.py` |
| Security headers + CSP | ✅ | `auth_security.SecurityHeadersMiddleware` |

## Multi-Tenant Safety
| Item | Status | Evidence |
|---|---|---|
| Tenant isolation tested | ✅ | `core/tenancy.py` (`barn_filter`/`stamp_barn`); `tests/test_4e_isolation_core.py`, `test_4e_isolation_engine.py` |
| Cross-tenant access blocked | ✅ | both-directions isolation suites (above); per-domain scoping tests (`test_billing_scoping`, `test_care_scoping`, `test_onboarding_reports_scoping`, `test_dashboard_invites_scoping`) |
| Owner visibility verified | ✅ | `tests/test_owner_billing.py`, `test_owner_upcoming.py`, `test_owner_updates.py`, `test_owner_trust*.py` |

## Testing
| Item | Status | Evidence |
|---|---|---|
| Authentication tests pass | ✅ | `test_config.py`, `test_login_lockout.py`, `test_security_patch_2e.py`, `test_phase2c_auth.py` |
| Billing tests pass | ✅ | `test_billing_9a.py`, `test_billing_routes.py`, `test_billing_scoping.py`, `test_owner_billing.py`, `test_recurring_charges.py` (see `BILLING_REFERENCE.md`) |
| Care workflow tests pass | ✅ | `test_care_*.py` (integrity/scoping/state-guards/filtering/routes) |
| Permission tests pass | ✅ | `test_permissions.py`, `test_permissions_wiring.py` |
| Audit log tests pass | ✅ | `test_audit_service.py`, `test_audit_5b/5c/5d.py` (see `AUDIT_LOGGING.md`) |

## Frontend
| Item | Status | Evidence |
|---|---|---|
| Mobile layouts verified | ✅ | mobile-hardening batches (testing_agent iterations 21–23) |
| Dashboard / forms / navigation | ✅ | testing_agent frontend iterations through Phase 9C (iteration 29) |

## Backend
| Item | Status | Evidence |
|---|---|---|
| No critical errors | ✅ | clean startup logs; `startup complete: db_ok=True …` (10B) |
| No failing tests | ✅ | **582 passed / 3 skipped** |
| Database indexes verified | ✅ | `ensure_*_indexes` (refresh/notification/auth-token/audit/billing) in `core/lifespan.py`; surfaced via `/api/health/ready` `indexes_ensured` (Phase 10B) |

## Billing
| Item | Status | Evidence |
|---|---|---|
| Invoice calculations verified | ✅ | server-authoritative `compute_money` (9A); `test_billing_9a.py`, `test_recurring_charges.py` |
| Payment tracking verified | ✅ | `/invoices/{id}/pay` status flip + `invoice.paid` audit; `test_billing_routes.py` (bookkeeping only — no payment processor) |

## Owner Portal
| Item | Status | Evidence |
|---|---|---|
| Horse visibility verified | ✅ | owner-scoped reads; `test_owner_upcoming.py`, `test_owner_trust*.py` |
| Owner updates verified | ✅ | `routes/owner_updates.py`; `test_owner_updates.py` |

## Deployment
| Item | Status | Evidence |
|---|---|---|
| Production variables configured | ✅ | env-only config; `validate_config()` fail-fast; `deployment_agent` PASS |
| Database backups confirmed | ⚠️ | **Operational/infra step** — handled by the Emergent-managed MongoDB at deploy time; not a code concern |
| Monitoring enabled | ✅/⚠️ | Structured logging + request correlation (10A); liveness/readiness probes (10B). Metrics/Prometheus endpoint ⛳ deferred (later observability enhancement) |

## Documentation
| Item | Status | Evidence |
|---|---|---|
| Changelog updated | ✅ | `memory/PRD.md` running status log |
| Documentation updated | ✅ | `MASTER_INDEX.md`, `PHASED_EXECUTION_PLAN.md`, `OBSERVABILITY.md`, `BILLING_REFERENCE.md`, `AUDIT_LOGGING.md`, this file |

---

## Verification performed in 10C (no code change)
1. **`deployment_agent` static scan → PASS** (`findings: []`): no hardcoded secrets/URLs/ports, env-only config, `/api` routing, supervisor config valid.
2. **Config fail-fast policy** confirmed via `core/config.validate_config()` + `tests/test_config.py` (prod missing/insecure `JWT_SECRET`/`MONGO_URL`/`DB_NAME` → startup abort).
3. **CORS prod policy** confirmed via `core/config.get_cors_origins()` (rejects `*`/empty in production) + `test_config.py`.
4. **Index-ensure path** confirmed wired in `core/lifespan.py` and surfaced by `/api/health/ready` `indexes_ensured=true`.
5. **Health probes** confirmed: `/api/health` (legacy), `/api/health/live` (no DB), `/api/health/ready` (additive runtime fields). See `OBSERVABILITY.md`.

## Findings (10C)
- **No P0 launch blockers.** `deployment_agent` returned `pass` with zero findings; no runtime/config/security fix required.
- No stale/incorrect `RELEASE_CHECKLIST.md` items found that warranted a doc-fix callout (left untouched per 10C scope).

## Deferred / backlog (not launch blockers)
- ⛳ **Metrics/Prometheus endpoint** — later observability enhancement (explicitly out of scope for 10A/10B).
- ⛳ **Multi-replica rate-limit/lockout store (Redis)** — only needed if horizontally scaled (Tech Debt #8 "still open").
- ⛳ **P1 localStorage → httpOnly cookie auth migration** — dedicated gated phase (see `OBSERVABILITY.md` backlog).
- ⛳ **Phase 5E audit backlog** — TTL/retention, tamper-evidence, IP on denials.
- ⚠️ **DB backups** — operational/infra responsibility at deploy time.
