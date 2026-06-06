# Audit Logging (Phase 5)

> Status: **5A foundation COMPLETE + 5B auth/session + admin/destructive instrumentation COMPLETE.**
> Remaining: 5C (barn/invite lifecycle + SR approve/decline + invoice.paid) and the
> 5D read API are separately gated.

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
   by **normalized variant matching** — keys are lowercased and collapsed
   (separators/camelCase removed), then redacted if they contain any sensitive
   fragment (`password`, `passwd`, `token`, `secret`, `authorization`,
   `credential`, `apikey`, `jwt`, `hash`) or exactly match a token-bearing URL
   key (`accept_url`/`reset_url`/`verify_url`/`dev_accept_url`). This catches
   variants like `resetToken`, `verificationToken`, `authorization_header`,
   `apiKey`, `secretKey`, `session_token_id`, `password_hash` at any nesting
   depth. Long strings are truncated (500 chars) and lists capped (50).
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
  `auth.email.verified`. ✅ **5B (`routes/auth.py`)**
- **Admin/destructive:** `admin.seed.attempt` (with outcome), `admin.tenant_reset`,
  `barn.created`. ✅ **5B (`routes/admin.py`, `routes/barns.py`)** — `admin.tenant_reset`
  success-path audit is wired but **not exercised destructively in tests** (the wipe is
  `delete_many({})` on the shared DB); verified by code review + the denied-gate test
  until a safer isolated harness exists.
- **Access control:** `permission.denied` — emitted by `core.permissions.require()`
  for the centralized capability gates only. ✅ **5B** (fire-and-forget; behavior-identical
  403; IP/user-agent capture for denials is a future enhancement).
- **Barn/invite lifecycle:** `invite.created`, `invite.resent`, `invite.revoked`,
  `invite.accepted`, `barn.settings.updated`. → **5C (pending)**
- **Operational approvals:** `service_request.approved`, `service_request.declined`. → **5C**
- **Billing:** `invoice.paid`. → **5C**

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
