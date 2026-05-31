# ONBOARDING_GUIDE.md
# EquineSync Onboarding Guide

## Welcome
EquineSync is a multi-tenant equine operations platform. Before making changes, read:
1. `PRODUCT_VISION.md`
2. `ENGINEERING_RULES.md`
3. `DATA_MODEL.md`
4. `API_CONTRACTS.md`

## Project Philosophy
EquineSync prioritizes: trust, accountability, operational clarity, mobile usability.

## Folder Structure
```
/docs        (governance — physically /app/docs)
/frontend    (React app)
/backend     (FastAPI app)
```

## Development Workflow
1. Analyze
2. Plan
3. Implement
4. Test
5. Document

## Rules
Never: create duplicate systems, bypass permissions, skip testing, alter schemas without documentation.

## Core Modules
Authentication · Horse Management · Care Operations · Billing · Owner Portal · Notifications · Audit Logs · Reporting.

## Required Environment Variables (backend `.env`)
Configuration is centralized in `backend/config.py` and validated at startup via `validate_config()`.

| Variable | Required | Notes |
|---|---|---|
| `MONGO_URL` | Always | MongoDB connection string. Startup fails if missing. |
| `DB_NAME` | Always | Database name. Startup fails if missing. |
| `JWT_SECRET` | **Production** | JWT signing secret. Must be strong (≥ 16 chars, not a placeholder like `change-me`). In **production** a missing/insecure value **fails startup**. In **development** a missing value falls back to a logged ephemeral per-process secret (sessions reset on restart). |
| `APP_ENV` | Optional | `development` (default) or `production`. Drives fail-fast behavior. Set `APP_ENV=production` in production deployments. |
| `CORS_ORIGINS` | **Production** | Comma-separated allowed origins. In **production** `*` or empty is rejected at startup. In development defaults to `*`. |
| `RATE_LIMIT_ENABLED` | Optional | `true` (default) / `false`. Toggles auth-endpoint rate limiting. |
| `AUTH_RATE_LIMIT` | Optional | Override in `limits` format (e.g. `5/minute`). Defaults: `5/minute` in production, `1000/minute` in development (so local use / tests aren't throttled). |
| `ENFORCE_EMAIL_VERIFICATION` | Optional | `false` (default) / `true`. When `true`, unverified users are blocked at login (403). Existing users are backfilled to verified at startup, so enabling this never locks them out. |
| `EMAIL_VERIFY_TTL_HOURS` | Optional | Email-verification token lifetime (default `48`). |
| `PASSWORD_RESET_TTL_HOURS` | Optional | Password-reset token lifetime (default `1`). |
| `LOGIN_LOCKOUT_ENABLED` | Optional | `true` (default) / `false`. Toggles account-level brute-force lockout. |
| `LOGIN_MAX_ATTEMPTS` | Optional | Failed logins before lockout (default `5`). |
| `LOGIN_LOCKOUT_MINUTES` | Optional | Lockout duration (default `15`). |
| `LOGIN_ATTEMPT_WINDOW_MINUTES` | Optional | Window in which failures accumulate (default `15`). |
| `RESEND_API_KEY` | For email | Resend transactional email key (used by upcoming Phase 2B). Never logged or committed. |
| `RESEND_FROM` | For email | Verified sender address. |
| `APP_BASE_URL` | Optional | Public app URL for links in emails. |
| `INVITE_TTL_DAYS` | Optional | Staff invite expiry window. |
| `EMERGENT_LLM_KEY` | For AI | Universal LLM key. |

> **Security note:** Secrets must only ever be provided via environment variables. Never hardcode, print, log, commit, or expose them in frontend code.

## Before Shipping
Review `RELEASE_CHECKLIST.md`.

## Local Environment Notes (this workspace)
- Backend: FastAPI on `0.0.0.0:8001` (supervisor-managed). All routes prefixed `/api`.
- Frontend: React on `:3000`. Uses `REACT_APP_BACKEND_URL` for API calls.
- Database: MongoDB via `MONGO_URL` + `DB_NAME` (backend `.env`).
- Restart after `.env`/dependency changes only: `sudo supervisorctl restart backend|frontend`.
