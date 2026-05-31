# API_CONTRACTS.md
# EquineSync API Contracts

## Philosophy
APIs should: be predictable, be tenant-safe, use consistent naming, return standardized responses.

> All backend routes are prefixed with `/api` (Kubernetes ingress routes `/api/*` to the FastAPI backend). See `API_VERSIONING.md`; current version is **v1**.

## Standardized Response Format
**Success**
```json
{
  "success": true,
  "data": {},
  "message": null
}
```
**Error**
```json
{
  "success": false,
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "User lacks required permissions."
  }
}
```

> **Current-state note:** The live API does not yet apply this envelope consistently (most endpoints return raw objects; a few include a partial `data` field). Standardizing responses is tracked in `KNOWN_TECH_DEBT.md` → "Inconsistent API Responses".

## Authentication
Protected routes require: `Authorization: Bearer <token>`.

### Auth endpoints (current)
| Method | Path | Notes |
|---|---|---|
| POST | `/api/auth/register` | Rate-limited. Creates user (`email_verified=false`), auto-logs in, sends verification email. |
| POST | `/api/auth/login` | Rate-limited. 403 if `ENFORCE_EMAIL_VERIFICATION=true` and user unverified. **423** if account is temporarily locked (brute-force lockout). |
| POST | `/api/auth/refresh` | Rate-limited. Rotates refresh token. |
| POST | `/api/auth/logout` / `/auth/logout-all` | Revokes refresh token(s). |
| GET | `/api/auth/me` | Current user. |
| POST | `/api/auth/forgot-password` | Rate-limited. Always 200 (no email enumeration). Returns `dev_token` only when non-production. |
| POST | `/api/auth/reset-password` | Consumes reset token, sets new password, revokes all sessions. |
| POST | `/api/auth/verify-email` | Consumes verification token, sets `email_verified=true`. |
| POST | `/api/auth/resend-verification` | Rate-limited. Always 200. Returns `dev_token` only when non-production. |

### Health
| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | Readiness probe. Reports DB connectivity + config booleans (never secret values). 200 healthy, 503 if DB unreachable. |

## Endpoint Naming Rules
- Use plural nouns: `/horses`, `/tasks`, `/invoices`.
- Avoid inconsistent naming.

## Horse API
| Method | Path | Description |
|---|---|---|
| GET | `/horses` | Returns visible horses for authenticated tenant. |
| GET | `/horses/{id}` | Returns horse profile. |
| POST | `/horses` | Creates horse. |
| PATCH | `/horses/{id}` | Updates horse. |
| DELETE | `/horses/{id}` | **Soft delete only.** |

## Care Task API
| Method | Path |
|---|---|
| GET | `/tasks` |
| POST | `/tasks` |
| PATCH | `/tasks/{id}/complete` |

## Billing API
| Method | Path |
|---|---|
| GET | `/invoices` |
| POST | `/invoices` |
| POST | `/payments` |

## Permission Rules
APIs must validate, **in this order**:
1. authentication
2. tenant isolation
3. permission authorization

> **Current-state note:** DELETE endpoints in `routes/onboarding.py` currently perform **hard** deletes (`delete_one`). The contract mandates soft-delete; reconciling this is tracked in tech debt.
