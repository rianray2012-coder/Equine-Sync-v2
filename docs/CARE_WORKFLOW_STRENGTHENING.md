# Care Workflow Strengthening (Phase 6)

> Boundary: **care records layer only** (`routes/care.py`: owners, riders,
> medications, medication_logs, vet_records, injuries, wellness, feed_tasks,
> farrier history reads). **No task-engine, audit, billing, onboarding,
> permissions, dashboard, digests, or frontend changes.** Each sub-phase is
> separately gated: plan → approval → implement → Codex review.

## Sub-phases
- **6A — Care Input Integrity / Cross-Barn Validation** ✅ **DONE (2026-06-06)**
- **6B — Care Record State Guards** ✅ **DONE (2026-06-06)** — idempotent feed-task
  re-complete + opt-in `client_log_id` med-log idempotency.
- **6C — Care Search / Filtering Polish** ✅ **DONE (2026-06-06)** — deterministic
  `created_at`-desc sort on the previously-unsorted lists + harmonized farrier read +
  opt-in barn-scoped `medication_id` filter on medication-logs.
- **6D — Care Documentation / Test Consolidation** ✅ **DONE (2026-06-06)** —
  consolidated Care Records Contract + coverage map (below); deduped care-test
  boilerplate into `tests/_care_helpers.py`.

## Care Records Contract (authoritative reference)
Single source of truth for the care-records HTTP surface as strengthened across
Phases 4B / 6A / 6B / 6C. **All reads are barn-scoped** (`barn_filter`); all writes
stamp `barn_id`. Responses are **bare arrays** (lists) — no pagination envelope.

| Endpoint | List filters | Sort | Create validation (6A) | State guard (6B) |
|---|---|---|---|---|
| `GET/POST /owners` | barn | `created_at` desc | each `horses[]` ∈ barn → else 404 | — |
| `GET/POST /riders` | barn | `created_at` desc | — (`trainer_id` deferred) | — |
| `GET/POST /medications` | barn + `horse_id?` | `created_at` desc | `horse_id` ∈ barn → else 404 | — |
| `GET/POST /medication-logs` | barn + `medication_id?` | `scheduled_time` desc | `medication_id` ∈ barn → else 404 | opt-in `client_log_id` idempotency (first-write-wins) |
| `GET /feed-tasks` · `POST /feed-tasks/{id}/complete` | barn + `date_str?` | `created_at` desc | — | re-complete is idempotent no-op (preserves first `completed_by`/`completed_at`); foreign id → 404 |
| `GET/POST /vet-records` | barn + `horse_id?` | `date` desc | `horse_id` ∈ barn → else 404 | — |
| `GET /farrier-history` | barn + `horse_id?` | `date` desc | — (engine-projected, read-only here) | — |
| `GET/POST /injuries` | barn + `horse_id?` | `created_at` desc | `horse_id` ∈ barn → else 404 | — |
| `GET/POST /wellness` | barn + `horse_id?` | `created_at` desc | `horse_id` ∈ barn → else 404 (no record/score side-effect) | — |

Notes:
- **No existence leak:** cross-barn / absent *create* ids return a generic 404
  (`"Horse not found"` / `"Medication not found"`).
- **Filter ids are never 404'd:** a foreign/unknown `horse_id` / `medication_id`
  *query filter* simply returns `[]` (barn_filter scopes it) — intentional (6C).
- `POST /wellness` additionally bumps `horses.wellness_score` (barn-scoped update).

### Care behavior → test-file coverage map
| Behavior area | Test file |
|---|---|
| Base CRUD round-trips (+ 3 legacy horse tests*) | `tests/test_care_routes.py` |
| Phase 4B barn isolation / scoping | `tests/test_care_scoping.py` |
| Phase 6A cross-barn input validation | `tests/test_care_integrity.py` |
| Phase 6B idempotency state guards | `tests/test_care_state_guards.py` |
| Phase 6C ordering + `medication_id` filter | `tests/test_care_filtering.py` |
| Shared env/mongo/login fixtures (6D dedup) | `tests/_care_helpers.py` |

\* The 3 horse-endpoint tests in `test_care_routes.py` are **legacy placement** —
horse-profile CRUD moved to `routes/horses.py` in Phase 3C (also covered by
`test_horses_routes.py`). Left in place (documented, not moved) to avoid churn;
new horse tests belong in `test_horses_routes.py`.

## 6A — Care Input Integrity / Cross-Barn Validation ✅
Every care create now validates its referenced id against the caller's barn
**before** writing. Cross-barn and absent ids return the **same generic 404**
(no existence leak), consistent with the 4E isolation contract.

| Endpoint | Validates | Miss → |
|---|---|---|
| `POST /medications` | `horse_id` ∈ barn | `404 "Horse not found"` |
| `POST /vet-records` | `horse_id` ∈ barn | `404 "Horse not found"` |
| `POST /injuries` | `horse_id` ∈ barn | `404 "Horse not found"` |
| `POST /wellness` | `horse_id` ∈ barn | `404 "Horse not found"` (no record/score side-effect) |
| `POST /medication-logs` | `medication_id` ∈ barn | `404 "Medication not found"` |
| `POST /owners` | each `horses[]` id ∈ barn | `404 "Horse not found"` |

- Implemented via two helpers in `routes/care.py`: `_require_horse(user, id)` /
  `_require_medication(user, id)` using `barn_filter(user, {"id": ...})`.
- Valid creates are **behavior-identical** (200 + `barn_id` stamped); only an
  added 404 branch. No new fields, no data migration, no schema redesign.

### Tests
- New `tests/test_care_integrity.py` — valid creates 200; nonexistent → 404;
  other-barn → 404 (no leak, no record written); owners.horses[] validated.
- Updated `tests/test_care_scoping.py` to the new contract: the horse/medication
  -referencing "stamps primary" cases now use a real barn horse
  (`test_care_create_with_real_refs_stamps_primary`), and the other-barn wellness
  test now asserts **404 + no wellness doc + other horse untouched**.
- Full backend suite: **483 passed / 3 skipped**.

## 6B — Care Record State Guards ✅
The two repeatable care-records mutations are now retry-safe (atomic, idempotent);
success response shapes are unchanged.

- **Feed-task re-complete (`POST /feed-tasks/{id}/complete`)** — idempotent no-op:
  a conditional update (`completed: {$ne: True}`) sets the completion only when not
  already complete, so a re-complete **preserves the original `completed_by` /
  `completed_at`** and still returns the feed-task doc (same shape). 404 path
  unchanged ("Feed task not found").
- **Medication-log idempotency (`POST /medication-logs`)** — new **optional**
  `client_log_id`. When provided, an upsert keyed by `(barn_id, client_log_id)`
  with `$setOnInsert` makes repeat posts return the **first** log (first-write-wins).
  When omitted, behavior is exactly as before (plain insert) and `client_log_id`
  is **not stored or returned** (no `client_log_id: null` in the doc/response).
  6A's `_require_medication` check is preserved. **Scope of the guarantee:** this is
  **retry / double-submit safe for the same idempotency key** (sequential repeats
  return the first log). It is **not** a hard concurrency guarantee under truly
  simultaneous upserts because no unique index was added — an additive unique index
  on `(barn_id, client_log_id)` is noted as **backlog** if concurrent protection is
  ever required.
- **Status stays free-text** in 6B (no `{given,missed,refused,skipped}` allow-list).

### Tests
- New `tests/test_care_state_guards.py` — feed-task re-complete preserves first
  completion; `client_log_id` repeat returns same log + no duplicate; no-key posts
  still insert distinctly. Full backend suite: **486 passed / 3 skipped**.


## 6C — Care Search / Filtering Polish ✅
Care list reads are now predictable and consistent; **bare-array responses are
unchanged** (no pagination envelope) and all reads stay barn-scoped.

- **Deterministic ordering** — the five previously-unsorted lists now sort
  `created_at` desc (newest-first), matching the existing `wellness` convention:
  `GET /owners`, `GET /riders`, `GET /medications`, `GET /feed-tasks`,
  `GET /injuries`. (Lists that were already sorted — `medication-logs` by
  `scheduled_time`, `vet-records`/`farrier-history` by `date` — are unchanged.)
- **Harmonized `GET /farrier-history`** to route through
  `list_collection(..., sort_field="date")` instead of the bespoke
  `.find().sort("date", -1).to_list(500)` — **zero behavior change**, consistency only.
- **Opt-in `medication_id` filter on `GET /medication-logs`** — the only care list
  whose child resource couldn't be filtered now accepts an optional, barn-scoped
  `medication_id` (parity with the `horse_id` filter elsewhere). Omitting it is
  behavior-identical to before.
- **Filter-id → 404 validation intentionally skipped.** A foreign/unknown filter id
  (`horse_id` / `medication_id`) returns an **empty array** (barn_filter scopes it) —
  no 404, no existence leak, no client-breakage. Documented as deferred.

### Tests
- New `tests/test_care_filtering.py` (4 tests) — newest-first ordering on
  medications + owners/riders/injuries; barn-scoped `medication_id` filter narrows
  results and an unknown id returns `[]` (not 404). Full backend suite: **490 passed
  / 3 skipped** (one cross-test analytics-isolation flake passes in isolation).


## 6D — Care Documentation / Test Consolidation ✅
Docs + care-test hygiene only — **zero production code change** (`routes/care.py`
untouched). Behavior is identical; the full care suite (38 tests) is re-verified green.

- **Documentation**: added the **Care Records Contract** reference table + the
  **behavior → test-file coverage map** (above) as the single source of truth for the
  care surface strengthened across 4B/6A/6B/6C.
- **Test consolidation**: extracted the env-reading / Mongo-client / API base-URL /
  admin-login boilerplate (previously copy-pasted across 4 care test modules) into a
  shared `tests/_care_helpers.py` (`API`, `mongo_db()`, `auth_headers()`, `read_env()`),
  mirroring the `_test_creds.py` precedent. The 4 newer modules now import it.
- **Tiny cleanup**: replaced the **stale hardcoded fallback URL**
  (`barn-ops-preview.preview…`) in `tests/test_care_routes.py` with the shared
  env-driven `API` (fail-fast like the other modules).
- **Documented (not moved)**: the 3 horse-endpoint tests in `test_care_routes.py` are
  legacy placement from before Phase 3C's `routes/horses.py` extraction — left in
  place with an inline note to avoid churn.


## Deferred / backlog (documented, NOT implemented in Phase 6 unless re-scoped)
- **`rider.trainer_id` validation** — references a *user/staff* record (cross-domain
  into `users`), outside the care-records boundary. Tracked for a later phase.
- **Audit events for sensitive care mutations** (e.g. `medication.discontinued`,
  `injury.recovered`) — Phase 5 is frozen; revisit as a future audit expansion.
- **feed_tasks ↔ task-engine reconciliation** — care/engine coupling, deferred.
