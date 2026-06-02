# Phase 3 — Backend Modularization Map

> Status: **3A + 3B complete**. 3C–3G planned. Each sub-phase is separately commit-worthy, testable, and rollback-safe. Target structure follows `ARCHITECTURE.md`.
>
> **3B done (2026-05-31):** Extracted `routes/system.py` (`/`, `/health` + additive booleans-only `dependencies` block), `routes/admin.py` (`/seed` 2E-hardened + `/admin/tenant-reset`), `routes/analytics.py` (`/events`, `/events/onboarding-funnel`). Seed logic moved to self-contained `seed_data.py` (`run_seed(db)`, called by both startup auto-seed and the guarded route). `_track`/`_base_url` remain shared infra in `server.py` until 3G. `server.py` 891 → 524 lines. Suite: 265 passed, 3 skipped. The digest/recap admin tools (`/admin/digest/run-now`, `/admin/weekly-recap/run-now`) were intentionally **left for 3E** to move with the owner digest/recap feature area.

## Goal
Move from a ~800-line `server.py` + `routes/*.py` toward the documented target:
```
/backend
  /core      (config, security, rate limiting, tokens)   ← 3A ✅
  /routes    (thin HTTP routers, one per domain)
  /services  (business logic)        ← future
  server.py  (app assembly only)     ← 3G
```

---

## Current Module Dependency Graph (as of 3A)
```
core/config.py        → (stdlib only)              [JWT secret, CORS, limits, ttls, env validation]
core/rate_limit.py    → core.config                [auth-endpoint limiter dependency]
core/auth_tokens.py   → (stdlib only)              [reset/verify one-time tokens]
core/login_attempts.py→ (stdlib only)              [brute-force lockout]
core/__init__.py      → (docstring only)

mailer.py             → resend, email_templates/   [NOT moved — separate concern]
auth_security.py      → (db)                        [refresh tokens, security headers] (move candidate: 3A-follow / core)
task_engine.py, notifications.py, owner_digest.py   [domain/services — later phases]

routes/auth.py        → core.config, core.rate_limit, core.auth_tokens,
                        core.login_attempts, auth_security, mailer
server.py             → core.config, core.auth_tokens, core.login_attempts,
                        routes.*, task_engine, notifications, auth_security, mailer, db
```
**Importers of the moved modules (all updated in 3A):** `server.py`, `routes/auth.py`, `tests/{test_config,test_rate_limit,test_auth_tokens,test_login_lockout}.py`, and `core/rate_limit.py`→`core.config` (internal).

---

## Route Groups Inside server.py (extraction inventory)

### Already modularized (in `routes/*.py`, included by server.py)
`auth`, `dashboard`, `reports`, `invites`, `onboarding`, `care`, `operations`, `task_engine`, `notifications`, **`system` (3B)**, **`admin` (3B)**, **`analytics` (3B)**. Plus **`seed_data.py`** (self-contained `run_seed(db)`, 3B).

### Still inline in server.py (extraction candidates)
| Lines (approx) | Group | Endpoints | Target sub-phase |
|---|---|---|---|
| ✅ done (3B) | **System** | `GET /health` (+ `dependencies`), `GET /` | **3B ✅ → routes/system.py** |
| ✅ done (3B) | **Admin** | `/seed` (2E-hardened), `/admin/tenant-reset` | **3B ✅ → routes/admin.py** |
| ✅ done (3B) | **Analytics** | `/events`, `/events/onboarding-funnel` | **3B ✅ → routes/analytics.py** |
| `/notifications/digest/*`, `/notifications/weekly-recap/*`, `/admin/digest/run-now`, `/admin/weekly-recap/run-now` | **Notifications/Digest (inline)** | digest/recap preview + send-me + admin run-now | 3E (with owner/reports) |
| horse CRUD (currently in `routes/operations` / `care`?) | **Horses** | — audit & consolidate | **3C** |
| care/task endpoints | **Care/Tasks** | mostly in `routes/care`, `task_engine` | **3D** |
| owner/report endpoints | **Owner/Reports** | mostly in `routes/reports`, `dashboard` | **3E** |
| billing endpoints | **Billing** | — (audit; may not yet exist) | **3F** |

> Note: server.py also holds shared infra that is **not** a route group — `db` setup, JWT helpers (`create_token`), `get_current_user`, `_track`, `_base_url`, and the startup/shutdown bootstrap. These remain until **3G** (app assembly only), where the JWT/auth helpers should move into `core` and the bootstrap into a small `lifespan`/startup module.

---

## Sub-Phase Plan (ordered, rollback-safe)

- **3A ✅ — Core/security/config package.** Moved `config.py`, `rate_limit.py`, `auth_tokens.py`, `login_attempts.py` → `backend/core/` (via `git mv`, history preserved); updated all imports; no behavior change. `/api/health` gained a `version` field.
- **3B ✅ — System/Admin/Analytics routes.** Extracted `routes/system.py` (`/`, `/health` + additive booleans-only `dependencies`), `routes/admin.py` (`/seed` 2E-hardened + `/admin/tenant-reset`), `routes/analytics.py` (`/events*`). Seed moved to self-contained `seed_data.py::run_seed(db)`. `_track` kept in server.py (shared; moves in 3G — superseded the earlier "move `_track` near analytics" note). Digest/recap admin run-now deferred to **3E**. `server.py` 891 → 524 lines. Suite 265 passed / 3 skipped.
- **3C — Horse routes.** Consolidate horse CRUD into `routes/horses.py`; audit overlap with `operations`/`care`.
- **3D — Care/Task routes.** Ensure all care/task/turnout/medication endpoints live in `routes/care.py` (+ `task_engine`); thin out server.py.
- **3E — Owner/Report routes.** Consolidate owner-facing + reporting + inline notification digest/recap (incl. `/admin/digest/run-now` + `/admin/weekly-recap/run-now`) into `routes/owner.py` / `routes/reports.py`.
- **3F — Billing routes.** Extract/define `routes/billing.py` (audit current state first).
- **3G — server.py → app assembly only.** server.py becomes: env load → config validate → middleware → router includes → lifespan/startup. Move JWT helpers + `get_current_user` + `_track`/`_base_url` into `core`; move bootstrap into `core/lifespan.py` (or `startup.py`).

### Extraction order rationale
Lowest-risk, least-coupled first (system/admin/analytics → 3B), then domain groups by blast radius (horses → care → owner/reports → billing), finishing with the high-touch assembly cleanup (3G) once everything else is out.

---

## Guardrails for every sub-phase
1. No API behavior change; no frontend change.
2. Use `git mv` / additive routers; keep diffs reviewable.
3. Run full backend suite (currently **235 passed, 1 skipped**) + `/api/health` + login smoke before finishing.
4. One sub-phase = one commit-worthy checkpoint.
5. No multi-tenancy/permissions work here (that's Phase 4).
