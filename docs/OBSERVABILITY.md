# OBSERVABILITY.md
# EquineSync — Observability (Phase 10A: Structured Logging & Request Correlation)

Operational logging guide. This surface is **observability-only**: logs are
ephemeral stdout diagnostics (captured by supervisor). It does **not** persist
anything, does **not** write the `audit_log` collection, and emits **no** audit
events — `core/audit.py` remains the sole compliance trail.

> **Phase 10 (Production Readiness) doc set:** logging + health probes here ·
> deployment evidence in [`PRODUCTION_READINESS.md`](./PRODUCTION_READINESS.md) ·
> dependency audit in [`DEPENDENCY_AUDIT.md`](./DEPENDENCY_AUDIT.md) ·
> phase status in [`PHASED_EXECUTION_PLAN.md`](./PHASED_EXECUTION_PLAN.md).

## Components
- `core/logging_config.py` — contextvars (`request_id`, `user_id`, `barn_id`),
  `ContextFilter`, `RedactionFilter`, `JsonFormatter` / `PlainFormatter`,
  `configure_logging()`.
- `core/middleware.py` — `RequestContextMiddleware` (**pure ASGI**, outermost),
  assigns `request_id`, emits one request-completion log, sets the additive
  `X-Request-ID` response header.
- `core/auth.py` — `get_current_user` sets best-effort `user_id`/`barn_id`
  correlation (opaque ids only; exception-safe; never affects auth).

## Configuration (env)
| Var | Default | Notes |
|---|---|---|
| `LOG_FORMAT` | `json` in production, `plain` in development | explicit `json`/`plain` override honored in either env |
| `LOG_LEVEL` | `INFO` | standard Python levels |

## Log fields (structured)
`timestamp` (UTC ISO), `level`, `logger`, `message`, `request_id`, `user_id`,
`barn_id`, and on request-completion records: `method`, `path` (no query
string), `status_code`, `duration_ms`. Errors add `exc_type` + `exc_info`.

## Levels
- **INFO** — one request-completion line per request; background-loop start +
  meaningful iteration summaries.
- **WARNING** — degraded/retryable conditions.
- **ERROR** — unhandled exceptions (stack) and terminal loop failures.
- Expected 4xx are not errors (surfaced via the completion line's `status_code`).

## Request correlation
- Incoming `X-Request-ID` accepted only if it matches `^[A-Za-z0-9._-]{1,64}$`;
  otherwise a `uuid4().hex` is generated. The id is echoed back as the additive
  `X-Request-ID` response header.
- contextvars are **reset per request** (in `finally`) so values never leak
  between requests; unauthenticated requests carry no user/barn context.

## Secret / PII safety
- Request/response bodies, headers, and query strings are **never** logged.
- `RedactionFilter` scrubs `record.msg`/`record.args` **before formatting** for
  the fragments `password|token|secret|authorization|credential|apikey|jwt|hash`,
  plus `Bearer <…>` and raw `eyJ…` JWTs (backstop only).

## Verification
`backend/tests/test_logging_10a.py` covers sanitizer, redaction (msg + args),
JSON formatter fields, `X-Request-ID` (generated/echoed/regenerated),
authenticated correlation (user_id/barn_id in the completion log), and
no-context-leak. Full backend suite: **575 passed / 3 skipped**.

## Rollback
Revert the `server.py` logging/middleware lines, remove the `core/auth.py`
correlation line, delete `core/logging_config.py` + `core/middleware.py` +
the test. The `X-Request-ID` header is independently removable.

---

## Health Probes (Phase 10B)
Three endpoints (`routes/system.py`); orchestration-grade liveness vs readiness.

| Endpoint | Touches Mongo? | Status | Body |
|---|---|---|---|
| `GET /api/health` | yes (ping) | 200 / 503 | **legacy, byte-compatible:** `status, service, version, database, config{}, dependencies{}` — no additive fields |
| `GET /api/health/live` | **no** | always 200 | `{status:"alive", service}` — process-up only (won't flap on a DB blip) |
| `GET /api/health/ready` | yes (ping) | 200 / 503 | `/health` body **+ additive** `started_at`, `uptime_seconds`, `indexes_ensured` |

- Shared `_build_health()` returns a fresh dict per call; `/health/ready`
  **copies** it before adding the additive fields, so `/health` can never
  inherit them by mutation.
- Additive readiness fields come from `core/runtime_state.py` (pure process
  state: no DB, no secrets) — `started_at`/uptime from `mark_started()`,
  `indexes_ensured` set after the startup index-ensure block.
- **Lifecycle logging:** `core/lifespan.py` emits a booleans-only
  `startup complete: env=… db_ok=… indexes_ensured=… <loops>` INFO line and a
  `shutting down` line — logs only, no flow change, no secrets.
- No metrics/Prometheus endpoint in 10B (deferred observability enhancement).

---

## Phase 10 backlog (deferred, separately gated)
- **P1 — localStorage → httpOnly cookie auth migration.** Touches runtime auth,
  frontend request behavior, refresh/logout flows, CSRF posture, and test setup.
  **Deferred to its own dedicated gated phase** with a standalone plan covering
  backend cookie issuance, CSRF, frontend migration, a compatibility window,
  tests, and rollback. **Not** part of Phase 10A.
- **P2 — palette reconciliation to Brand Guide 22** (Tech Debt #11, frontend).
- **Phase 5E audit backlog** — TTL/retention, tamper-evidence, IP on denials.
