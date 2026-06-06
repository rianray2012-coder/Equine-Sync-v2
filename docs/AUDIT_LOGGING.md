# Audit Logging (Phase 5)

> Status: **5A foundation COMPLETE (write-side service + schema + tests).**
> Route instrumentation (5B/5C) and the read API (5D) are separately gated.

## Purpose
An immutable, append-only operational/security audit trail for accountability,
debugging, and (future) compliance. Closes `KNOWN_TECH_DEBT.md #7`.

## Design principles (locked)
1. **Fail-open.** `audit.record(...)` never raises to the caller and never
   blocks the primary action — modeled on the analytics `_track` pattern.
2. **Barn-stamped.** Every entry carries `barn_id` (via `resolve_barn_id`), so
   the trail inherits Phase-4 multi-tenant isolation. The 5D read API will scope
   reads with `barn_filter`.
3. **PII-minimized.** A redaction pass strips sensitive keys from `metadata`
   (passwords, hashes, tokens, secrets, api keys, dev tokens, accept URLs) at
   any nesting depth, truncates long strings (500 chars) and caps lists (50).
4. **Immutable.** Append-only; no update/delete API. v1 has **no read API**.
5. **Indefinite retention (v1).** No TTL index. TTL/archival/export policy is
   deferred until compliance requirements are defined (customer contracts,
   legal hold, incident-investigation windows, privacy law). **Audit logs are
   not auto-deleted in v1.**

## Collection: `audit_log`
| field | type | notes |
|---|---|---|
| `id` | str (uuid) | entry id |
| `ts` | ISO 8601 UTC | event time |
| `barn_id` | str | tenant scope (`resolve_barn_id`) |
| `actor_user_id` | str \| null | null for unauthenticated events (e.g. failed login) |
| `actor_email` | str \| null | lowercased |
| `actor_role` | str \| null | |
| `action` | str | canonical `domain.entity.verb` (e.g. `auth.login.success`, `invoice.paid`) |
| `resource_type` | str \| null | e.g. `invoice`, `service_request`, `barn`, `capability` |
| `resource_id` | str \| null | |
| `outcome` | `success` \| `failure` \| `denied` | |
| `status_code` | int \| null | |
| `ip` | str \| null | from request, when available |
| `user_agent` | str \| null | from request, when available |
| `metadata` | object | action-specific, **redacted** (never secrets) |

Indexes (additive, idempotent): `(barn_id, ts desc)`, `(action, ts desc)`,
`(actor_user_id, ts desc)`.

## Service API (`core/audit.py`)
- `build_entry(...) -> dict` — pure entry builder (no I/O); stamps id/ts/barn/actor + redacts metadata.
- `await record(..., _db=None)` — fail-open append (`_db` lets tests inject a fake collection).
- `record_denial(user, capability, message)` — sync entrypoint for
  `core.permissions.require()` denials; schedules a fire-and-forget write on the
  running loop, no-op when no loop (keeps `require()` behavior-identical).
- `await ensure_audit_indexes(db)` — called once at startup (`core/lifespan.py`).

## v1 audited events (write-side scope — 5B/5C, instrumented next)
- **Auth/session:** `auth.login.success`, `auth.login.failure`, `auth.login.locked`,
  `auth.token.refreshed`, `auth.logout`, `auth.logout_all`,
  `auth.password_reset.requested`, `auth.password_reset.completed`,
  `auth.email.verified`.
- **Admin/destructive:** `admin.seed.attempt` (with outcome), `admin.tenant_reset`,
  `barn.created`.
- **Barn/invite lifecycle:** `invite.created`, `invite.resent`, `invite.revoked`,
  `invite.accepted`, `barn.settings.updated`.
- **Operational approvals:** `service_request.approved`, `service_request.declined`.
- **Billing:** `invoice.paid`.
- **Access control:** `permission.denied` — emitted by `core.permissions.require()`
  for the centralized capability gates only.

## Explicitly OUT OF SCOPE for v1 (later phases)
- A read/list API (`GET /api/audit-logs`) + `audit:read` capability + auditing
  reads of the audit log itself (`audit_logs.view`) → **Phase 5D**.
- Broad CRUD auditing (every create/update/delete across domains).
- Generic 401/validation(422) denial auditing (only `require()` 403s in v1).
- `auth.register` (public self-registration) and `auth.resend_verification`.
- Tamper-evidence (hash-chaining), request-id correlation, retention/TTL,
  archival/export, SIEM streaming → **Phase 5E / backlog**.

## Privacy / security guardrails
- Never store passwords, hashes, tokens, reset/verify tokens, payment data —
  enforced by the redaction allowlist + minimal call-site metadata.
- Append-only; no edit/delete endpoints.
- Reads (5D) are admin/barn_manager only and barn-scoped.
- Fail-open so audit can never become an availability/DoS risk.
