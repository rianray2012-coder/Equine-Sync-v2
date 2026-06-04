# Phase 4 — Multi-tenancy & Permissions Map

> Status: **4A complete (foundations); 4B-1 Horses + 4B-2 Care complete.** Remaining 4B sub-phases (4B-3 Operations → 4B-6 Aggregations, and 4B-7 task-engine/media reconciliation) are **not started**, along with 4C (centralized permission enforcement), 4D (registration/invite barn binding), and 4E (cross-tenant isolation test suite). Each sub-phase is commit-worthy, additive, and rollback-safe, gated on explicit approval. *(Note: `vet_records` + `farrier_history` read-scoping is intentionally deferred to 4B-7 — see the 4B-2 entry below.)*

## Approved design decisions (locked)
1. **`barn_id` is canonical.** The task engine's existing `tenant_id="default"` is mapped to `barn_id="primary"` **at the boundary** — no global rename. (Reconciliation of task-engine docs/router is a dedicated 4B sub-phase.)
2. **One user → one barn** for v1. Multi-barn membership/switching deferred.
3. **All existing + new users map to the canonical `primary` barn** in 4A/4B. True multi-barn signup deferred to 4D. **Public registration stays low-privilege (`horse_owner`) — never creates admins.**
4. **Lightweight centralized capability map** (`resource:action` → roles) + `require()` helper. No tightening in 4A.
5. **Canonical `barn_id = "primary"`** for the founder/demo barn. Startup migration is idempotent + additive.

---

## 4A — Foundations (done 2026-06-04)

**New modules**
- `core/tenancy.py` — `PRIMARY_BARN_ID="primary"`, `resolve_barn_id(user)` (missing/empty/None ⇒ primary, legacy-safe), `barn_filter(user, extra)`, `stamp_barn(user, doc)`. Pure; no DB; no `server.py` import.
- `core/permissions.py` — `CAPABILITIES` map (`"barn:manage" → {admin, barn_manager}`), `has_capability`, `require` (fail-closed on unknown capability), and `require_setup_role` re-expressed through `require(...,"barn:manage")` (behavior-identical, same 403 message). **Defined + tested only — NOT wired into routes in 4A.**

**JWT / user `barn_id` handling**
- Both auth implementations updated in lockstep: `core/auth.py` (app-wide dependency) **and** `routes/auth.py` (its private `create_token` + `make_current_user_dependency`).
- `create_token(user_id, role, barn_id=None)` adds an **optional, forward-compat** `barn_id` JWT claim.
- `get_current_user` (both paths) attaches `user["barn_id"] = resolve_barn_id(user)` from the **fresh user document** — the document is the **source of truth** for authorization/scoping; the JWT claim is never trusted for isolation.
- `login` / `register` / `refresh` / invite-accept now pass the resolved `barn_id` into `create_token`.

**Creation paths stamp `barn_id`**
- `routes/auth.py::register` → new user gets `barn_id="primary"` (role stays `horse_owner`).
- `routes/invites.py::create_invite_with_link` → **ignores any client-supplied `body.barn_id`** and binds the invite to `resolve_barn_id(current_user)` (currently always `primary`); per-barn targeting is deferred to Phase 4D. The accept-flow `new_user` is **clamped to `PRIMARY_BARN_ID`** (defends against legacy/malformed invite `barn_id`); `onboarding_progress` inherits it.
- `routes/onboarding.py` → stamps `barn_id=resolve_barn_id(user)` at creation time on `onboarding_progress` (both `_ensure_progress` and the `POST /onboarding/reset` upsert), `locations`, `feed_templates`, `inventory`, `recurring_schedules`, and CSV-imported `horses` + `owners` (no longer relying solely on the startup backfill). Staff invites stamp `barn_id="primary"`. The `barn` singleton is intentionally left keyed by its `id` (unchanged).
- `seed_data.py` → idempotent end-of-seed sweep stamps `barn_id="primary"` on all seeded collections.

**Idempotent startup migration** (`core/lifespan.py::_backfill_barn_id`, additive only, logged once)
- `update_many({"barn_id": {"$exists": False}}, {"$set": {"barn_id": "primary"}})` across these **25 domain collections**:
  `users, horses, owners, riders, medications, medication_logs, feed_tasks, vet_records, farrier_history, injuries, wellness, lessons, training, invoices, messages, service_requests, incidents, locations, feed_templates, inventory, recurring_schedules, staff_invites, invites, onboarding_progress, events`.
- First boot backfilled **3296 documents**; subsequent boots = 0 (idempotent — no log line).

**Explicitly NOT touched in 4A** (with reasons)
- **Task engine** (`tasks, task_templates, task_completions, task_events`) + **`media`** — these use `tenant_id="default"`; reconciled to `barn_id` in the dedicated **4B task-engine sub-phase** (alias: `tenant_id="default"` ≡ `barn_id="primary"`).
- **Notification collections** (`notifications, notification_preferences, notification_digest_log`) — user-keyed; isolation follows user→barn.
- **`barn` singleton** — keyed by its own `id="primary"` (that id *is* the barn id); adding a redundant field would change `GET /barn` response shape.
- **Auth/session/attempt infra** (`auth_tokens, refresh_tokens, login_attempts`) — user/token-scoped, no barn needed.

**Tests** (all green)
- `tests/test_tenancy.py` (13) + `tests/test_permissions.py` (7) — pure unit (incl. `barn_filter` override-rejection tests).
- `tests/test_core_auth_verification_gate.py` extended (+3): both auth paths attach `barn_id`.
- `tests/test_phase4a_barn_id.py` (live): public registration → `barn_id="primary"` + role forced `horse_owner`; invite create ignores client `barn_id="other"`; invite accept (incl. a legacy `barn_id="other"` invite) → user clamped to `barn_id="primary"`; `POST /onboarding/reset` before progress exists → created `onboarding_progress` is `primary`; onboarding creates (`locations`/`feed-templates`/`inventory`/`recurring-schedules`) and `csv-commit` horses+owners stamp `barn_id="primary"`.
- Full suite: **323 passed / 3 skipped** (a transient HTTPS connection flake to the preview host can occur under full-suite load; passes on clean re-run — unrelated to logic).

**Guardrails honored:** no read/write scoping yet, no route behavior changes, additive-only migration, no `server.py` imports from core, Security Patch 2E + both email-verification gates preserved.

---

## Next sub-phases (NOT started — await approval)
- **4B-1 ✅ — Horses** (`routes/horses.py`, done 2026-06-04). Scoped `GET /horses` list via `barn_filter(user)`; `GET/PATCH /horses/{id}` filter on `id`+`barn_id` (cross-barn ⇒ **404**, no existence leak); `POST /horses` stamps `barn_id` via `stamp_barn(user, doc)`; free-form `PATCH` strips `barn_id`/`id` so a horse can never be moved between barns. New `tests/test_horses_scoping.py` (4): other-barn exclusion from list, GET+PATCH 404, POST→primary, PATCH-cannot-move. Full suite **327 passed / 3 skipped**. *(Scope from the fresh user doc via `resolve_barn_id` only; no task_engine/media changes.)*
- **4B-2 ✅ — Care** (`routes/care.py`, done 2026-06-04). Scoped reads + stamped writes on the **7 engine-independent** collections: `owners`, `riders`, `medications`, `medication_logs`, `feed_tasks`, `injuries`, `wellness` (lists via `barn_filter(user, extra)`; creates via `stamp_barn`). `POST /feed-tasks/{id}/complete` now filters `id`+`barn_id` → cross-barn **404** with no mutation. `POST /wellness` stamps `barn_id` **and** scopes the cross-domain `horses.wellness_score` bump via `barn_filter(user, {"id": horse_id})` so a cross-barn `horse_id` triggers no side effect (no new horse-existence validation added — scoping only). `POST /vet-records` stamps `barn_id`. **Deferred to 4B-7:** `GET /vet-records` and `GET /farrier-history` reads are intentionally **NOT** barn-scoped yet, because `task_engine.py` completion hooks (lines 514/524) write those rows **without** `barn_id`; scoping their reads now would hide engine-projected rows and break engine completion tests. Read-scoping for both is bundled with the engine reconciliation in 4B-7. New `tests/test_care_scoping.py` (16): per-collection other-barn exclusion + POST→primary for the 7 (+vet POST stamp), feed-complete 404+no-mutation, wellness cross-barn-horse guard. Full suite **343 passed / 3 skipped**. *(Strict `barn_filter` unchanged; no task_engine/media changes.)*
- **4B-3 … 4B-6** — per-domain read/write scoping (operations, billing, onboarding+reports incl. barn-settings key switch, aggregations). **Not started.**
- **4B-7 — task-engine + media reconciliation** (`task_engine.py`, `storage.py`, dashboard tenant param): coupled idempotent migration `tenant_id "default" → "primary"` + router/loops switch to `resolve_barn_id(user)`. **RESERVED — not started; highest risk; its own separate approval gate, executed LAST in 4B.**
- **4C** — swap inline role checks for `core/permissions.require(...)`.
- **4D** — registration/invite barn binding (multi-barn signup); decide self-serve vs invite-only barn creation.
- **4E** — two-barn cross-tenant isolation test suite (the security gate).
