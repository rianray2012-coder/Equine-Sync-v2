# EquineSync — Unified Operational Task Engine Architecture

**Status:** Blueprint v1.0 · Awaiting approval
**Author:** E1 (Emergent)
**Scope:** Phase 1 (MVP) → Phase N (operational intelligence)
**Guiding tone:** Operational calm. Elegant restraint. Mobile-first execution.

---

## 0 · North Star

> Every operational action that happens in a barn — a feeding, a turnout, a medication, a stall muck, a farrier visit, a vet exam, a rehab walk — is the same primitive: **a task done to a horse, by a person, at a place, at a time.**

A unified Task Engine treats all of these as instances of one polymorphic backbone. Categories are metadata, not architecture. This unlocks:

- One Today view, one notification stream, one timeline, one analytics surface.
- New care types ship without schema migrations.
- Staff cognitive load stays flat as the product grows.

The blueprint below is intentionally **extensible but not over-engineered**. Anything not needed for Phase 1 is explicitly marked `[Future]`.

---

## 1 · Domain Model — The Five Core Entities

```
                ┌────────────────────┐
                │   TaskTemplate     │  (the recipe)
                │  - category        │
                │  - default windows │
                │  - rrule           │
                └─────────┬──────────┘
                          │  generates
                          ▼
┌────────────┐     ┌──────────────┐     ┌──────────────┐
│  Horse(s)  │◀───▶│     Task     │────▶│ Assignee(s)  │
│  Location  │     │  (occurrence)│     │  (user/role) │
└────────────┘     └──────┬───────┘     └──────────────┘
                          │  produces
                          ▼
                 ┌─────────────────┐
                 │ TaskCompletion  │  (immutable log)
                 └────────┬────────┘
                          │  emits
                          ▼
                 ┌─────────────────┐
                 │   TaskEvent     │  (timeline / analytics)
                 └─────────────────┘
```

### 1.1 TaskTemplate — *"the recipe"*

Defines a repeatable care pattern. Created once, generates many Tasks.

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `tenant_id` | uuid | Barn scope |
| `category` | enum | `feed` · `medication` · `turnout_out` · `turnout_in` · `stall_clean` · `farrier` · `vet` · `rehab` · `custom` |
| `title` | string | "AM Grain", "Banamine 500mg" |
| `description` | string | optional notes |
| `linked_horses` | uuid[] | all-barn template if empty |
| `linked_locations` | uuid[] | optional |
| `default_assignee_role` | enum | `groom` · `trainer` · `manager` · `vet` etc. |
| `default_assignee_user_id` | uuid? | optional override |
| `rrule` | string (iCal RFC 5545) | recurrence; see §3 |
| `window_minutes_before` | int | grace before due (e.g. 30) |
| `window_minutes_after` | int | grace after (e.g. 60) |
| `priority` | enum | `critical` · `standard` · `informational` |
| `payload_schema` | jsonb | per-category typed fields (see §1.4) |
| `payload_defaults` | jsonb | prefilled values |
| `active` | bool | soft pause without delete |
| `created_by` | uuid | |
| `created_at` / `updated_at` | datetime | UTC |

### 1.2 Task — *"the occurrence"*

A single scheduled instance. Materialized from a template **or** ad-hoc.

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `tenant_id` | uuid | |
| `template_id` | uuid? | null for ad-hoc tasks |
| `category` | enum | denormalized from template |
| `title` | string | denormalized; editable per-occurrence |
| `linked_horse_ids` | uuid[] | one task can serve multiple horses (bulk feed) |
| `linked_location_id` | uuid? | |
| `assignee_user_id` | uuid? | resolved at materialization |
| `assignee_role` | enum? | fallback if no user assigned |
| `scheduled_at` | datetime (UTC) | canonical due time |
| `window_start` / `window_end` | datetime | computed from template windows |
| `priority` | enum | inherits from template; overridable |
| `status` | enum | `scheduled` · `due` · `overdue` · `in_progress` · `completed` · `skipped` · `cancelled` |
| `payload` | jsonb | category-specific data |
| `client_completion_id` | string? | idempotency key from mobile client (see §6) |
| `notes` | string? | freeform |
| `created_at` / `updated_at` | datetime | |

### 1.3 TaskCompletion — *"the immutable log"*

Append-only. A Task can in principle have multiple completion attempts (e.g. partial → final), but the latest non-voided record is canonical.

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `task_id` | uuid | FK |
| `tenant_id` | uuid | |
| `completed_by_user_id` | uuid | |
| `completed_at` | datetime (UTC) | client-reported; server validates |
| `server_received_at` | datetime | for offline diagnostics |
| `outcome` | enum | `done` · `partial` · `skipped` · `refused` (horse refused) · `issue` |
| `payload_actual` | jsonb | what was actually given/done |
| `notes` | string? | |
| `media_ids` | uuid[] | `[Future]` photo evidence |
| `client_completion_id` | string | idempotency dedup key |
| `voided` | bool | soft-revert; never hard delete |
| `voided_by_user_id` | uuid? | |
| `voided_reason` | string? | |

### 1.4 Category Payloads (typed extensions)

Each category extends `payload` with a small, predictable shape. The shape is enforced in code (Pydantic models per category), **not** by a separate table — keeping Mongo collections lean.

| Category | `payload_schema` |
|---|---|
| `feed` | `{ feed_type, amount, unit, supplements[] }` |
| `medication` | `{ med_name, dose, unit, route, withdrawal_until? }` |
| `turnout_out` / `turnout_in` | `{ paddock_id, blanket?, fly_mask?, group_horse_ids[] }` |
| `stall_clean` | `{ level: "pick" \| "strip", bedding_added? }` |
| `farrier` | `{ farrier_name, shoes_on[], next_visit_due? }` |
| `vet` | `{ vet_name, reason, follow_up_due? }` |
| `rehab` | `{ activity, duration_min, intensity }` |
| `custom` | `{}` (freeform) |

> **Naming convention:** category keys are lowercase snake_case. UI strings are localized separately — never derived from the enum value.

### 1.5 TaskEvent — *"the timeline"*

Side-effect of completions and lifecycle transitions. Powers horse timelines, staff feeds, notifications, analytics. **Decoupled** from Task by design — Events outlive Tasks even if a Task is deleted.

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `tenant_id` | uuid | |
| `event_type` | enum | `task.created` · `task.completed` · `task.overdue` · `task.skipped` · `task.voided` · `task.reassigned` |
| `task_id` | uuid? | nullable for system events |
| `category` | enum? | |
| `actor_user_id` | uuid? | who caused it (null = system) |
| `subject_horse_ids` | uuid[] | for timeline queries |
| `location_id` | uuid? | |
| `occurred_at` | datetime (UTC) | |
| `payload_snapshot` | jsonb | denormalized copy for replay-safety |

---

## 2 · Lifecycle & State Machine

```
              ┌────────────┐
              │ scheduled  │  (created, not yet due)
              └─────┬──────┘
                    │ scheduled_at − window_before reached
                    ▼
              ┌────────────┐
              │    due     │  (in completion window)
              └─────┬──────┘
        ┌───────────┼─────────────┐
        ▼           ▼             ▼
 ┌────────────┐ ┌────────┐ ┌──────────┐
 │in_progress │ │overdue │ │ skipped  │
 └─────┬──────┘ └───┬────┘ └──────────┘
       │            │
       ▼            ▼
  ┌──────────┐   ┌──────────┐
  │completed │   │completed │ (late completion still allowed)
  └──────────┘   └──────────┘
```

**Rules:**

- `scheduled → due → overdue` transitions are computed by a lightweight cron sweep (every 1 min for Phase 1). Status is materialized lazily on read for fairness when the sweep lags.
- `completed` is **terminal but reversible** via void (creates a new `task.voided` event; original Completion row stays).
- `cancelled` is admin-only and only valid pre-completion.
- `in_progress` is optional UX state — used for multi-step tasks (e.g. rehab session timer). Phase 1 may collapse into `due`.

---

## 3 · Recurrence Strategy

**Internal:** RRULE strings per RFC 5545. **UI:** preset chips + custom builder.

| UI Preset | RRULE example |
|---|---|
| Daily | `FREQ=DAILY` |
| Weekdays | `FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR` |
| Custom weekly (pick days) | `FREQ=WEEKLY;BYDAY=MO,WE,FR` |
| Every X hours | `FREQ=HOURLY;INTERVAL=4` |
| Monthly (date) | `FREQ=MONTHLY;BYMONTHDAY=15` |
| Monthly (weekday) | `FREQ=MONTHLY;BYDAY=2TU` |
| Custom | raw RRULE editor (admin only) |

**Materialization policy:**
- We do **not** pre-create every future task forever. We materialize a rolling **14-day horizon** per template via a background job, plus on-demand when a Today view requests a date beyond the horizon.
- Templates store the RRULE; the materializer is the only consumer.
- Editing a template's RRULE re-materializes future, untouched occurrences only. Already-completed tasks are immutable.

**Library:** `python-dateutil.rrule` (already in transitive deps; no new SDK).

---

## 4 · Linked Entity Architecture

A Task can attach to **many horses** and one location. A Completion belongs to **one Task** but its event fans out to all linked horses' timelines.

```
horse ─┐
horse ─┼──▶ Task ──▶ Completion ──▶ TaskEvent ──▶ HorseTimeline (per horse)
horse ─┘                                  └────▶ StaffActivityFeed
                                          └────▶ AnalyticsRollup
```

**Why multi-horse on a single Task?**
Real barn ops: "Feed pasture group A" is one action, four horses. Forcing four separate tasks creates friction. The engine treats `linked_horse_ids` as a set; completion fans out events per horse.

**Bulk completion** (mobile UX) is the inverse: one staff action → multiple distinct Tasks completed in one network call. See §6.

---

## 5 · Notification & Event Propagation

```
TaskCompletion ──┐
Task transition ─┼──▶ TaskEvent (persisted) ──▶ Dispatcher
                 │                                  ├─▶ Push/Email (P1)
                 │                                  ├─▶ WebSocket fanout (P1)
                 │                                  ├─▶ Timeline writer
                 │                                  └─▶ Analytics writer
```

**Phase 1 (MVP):**
- TaskEvent rows are written synchronously inside the completion transaction.
- A single in-process listener writes denormalized timeline + analytics rollups.
- Notifications: in-app badge counts only. Email/push deferred.

**Phase 2 (`[Future]`):**
- Move dispatcher behind a queue (Mongo change streams or Redis Streams).
- Email/push channels per user notification preferences.
- Webhooks for owner-portal subscribers.

**Anti-pattern to avoid:** writing notification logic inline in route handlers. All side effects go through TaskEvent — single funnel.

---

## 6 · Mobile / Offline Interaction Model

### 6.1 Optimistic Completion Flow

```
[user swipes complete]
       │
       ├─▶ Local IndexedDB: write CompletionDraft { client_completion_id, task_id, ts, payload }
       ├─▶ UI: mark task as ✓ instantly (optimistic)
       └─▶ Queue worker: POST /api/tasks/{id}/complete
              │
              ├─ 2xx → mark draft synced, remove from queue
              ├─ 409 (dup client_completion_id) → already accepted, mark synced
              ├─ 4xx (validation) → surface inline error, allow retry/edit
              └─ network fail → exponential backoff retry (1s, 5s, 30s, 2m, 10m)
```

### 6.2 Idempotency Contract

- Client generates `client_completion_id = uuidv4()` **before** the optimistic UI update.
- Server upserts on `(task_id, client_completion_id)`. Duplicate requests return the existing Completion verbatim (HTTP 200, not 409 — keeping clients simple).
- Voiding requires a new completion ID; never reuse.

### 6.3 Conflict Resolution

- **Two staff complete the same task offline:** first sync wins; second is converted into a `note` on the canonical completion ("Also marked done by Jamie 08:14"). No data is lost; no duplicate event is emitted.
- **Task edited server-side while offline draft pending:** draft attaches to current task version; payload validation rejects drafts whose category no longer matches → user prompted to re-confirm.
- **Task deleted server-side:** offline completion is preserved as a `TaskEvent` with `event_type=task.completed_orphan` for audit; never silently dropped.

### 6.4 Retry Indicators

- Subtle pearl-colored dot on the task card: solid (synced), pulsing (queued), amber ring (retrying), red (failed > 5 attempts, user action required).
- A single "Sync status" affordance in the header reveals the queue.

---

## 7 · Analytics Integration Points

Phase 1 emits minimal but durable signals. No premature dashboards — just the data that future dashboards will need.

| Rollup | Source | Granularity |
|---|---|---|
| `completion_rate_per_template` | TaskEvent | daily |
| `overdue_count_per_assignee` | TaskEvent | daily |
| `time_to_completion_per_category` | Completion - Task.scheduled_at | weekly |
| `task_volume_per_horse` | TaskEvent.subject_horse_ids | weekly |
| `staff_activity_score` | TaskEvent grouped by actor | weekly |

Stored in a separate `analytics_rollups` collection, recomputed nightly. Read-only to the API. Wellness/operational-intelligence systems consume from here, never from raw events.

---

## 8 · API Surface (Phase 1)

All routes are tenant-scoped via JWT.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/tasks` | filter: `from`, `to`, `horse_id`, `category`, `assignee_id`, `status`, `priority` |
| GET | `/api/tasks/today` | convenience: returns urgency-ordered groups (see §9) |
| POST | `/api/tasks` | ad-hoc task |
| PATCH | `/api/tasks/{id}` | edit (pre-completion) |
| POST | `/api/tasks/{id}/complete` | idempotent completion |
| POST | `/api/tasks/bulk-complete` | array of `{task_id, client_completion_id, payload_actual}` |
| POST | `/api/tasks/{id}/skip` | with reason |
| POST | `/api/tasks/{id}/void` | revert completion |
| POST | `/api/tasks/{id}/reassign` | change assignee |
| GET | `/api/task-templates` | list |
| POST | `/api/task-templates` | create |
| PATCH | `/api/task-templates/{id}` | edit (triggers re-materialization) |
| DELETE | `/api/task-templates/{id}` | soft-delete (sets `active=false`) |
| GET | `/api/horses/{id}/timeline` | from TaskEvent |
| GET | `/api/staff/{id}/activity` | from TaskEvent |
| POST | `/api/tasks/materialize` | admin: force re-materialize horizon |

**Response envelope:** all list endpoints return `{ items, next_cursor, total_estimate }`. Never offset-paginate — cursor-only.

---

## 9 · "Today" View — Urgency Hierarchy

Returned from `/api/tasks/today` as ordered groups:

1. **Overdue critical** — red rail, top
2. **Due now** — primary lavender accent
3. **Upcoming next 4h** — soft surface
4. **Later today** — collapsed by default
5. **Completed today** — pearl/muted, collapsed by default
6. **Informational** — pinned bottom (e.g. "Vet visit tomorrow", reference-only)

Each group renders as a swipeable card stack with bulk-select affordance. Completed items animate to group 5 with a gentle reduce-motion-safe transition.

---

## 10 · Migration Strategy from Siloed Concepts

The current codebase has no entrenched siloed task collections yet (only `Horse`, `User`, `Location`, `BarnSettings`, `Invites`, `OnboardingProgress`). This is the cleanest possible runway.

**Mapping table — how legacy mental models become Tasks:**

| Old concept | TaskTemplate.category | Notes |
|---|---|---|
| "Feeding schedule" entry | `feed` | one template per meal × group |
| "Med chart" row | `medication` | one template per active medication |
| "Turnout sheet" line | `turnout_out` + `turnout_in` (paired) | two templates referencing same paddock |
| "Stall list" | `stall_clean` | one template per stall row, RRULE=daily |
| "Farrier 6-week cycle" | `farrier` | RRULE=`FREQ=WEEKLY;INTERVAL=6` |
| "Vet appointment" | `vet` | usually one-off (no RRULE) |
| "Rehab plan" | `rehab` | RRULE per phase; template archived on phase change |

**Onboarding wizard impact (`[Future]`):**
The existing 10-step wizard's "Feeding" and "Care" steps will produce TaskTemplates instead of legacy schedule rows. Wizard schema changes are scoped to Phase 2 to avoid blocking the engine ship.

---

## 11 · Naming Conventions

| Layer | Convention | Example |
|---|---|---|
| Mongo collections | snake_case plural | `tasks`, `task_templates`, `task_completions`, `task_events` |
| Pydantic models | PascalCase singular | `Task`, `TaskTemplate`, `TaskCompletion`, `TaskEvent` |
| Enum values | snake_case | `turnout_out`, `in_progress` |
| API paths | kebab-case nouns, verbs only for actions | `/api/task-templates`, `/api/tasks/{id}/complete` |
| Event types | dot-namespaced | `task.completed`, `task.voided` |
| Frontend components | PascalCase | `TaskCard`, `TodayView`, `BulkCompleteBar` |
| React Query keys | array tuple | `['tasks', 'today', { date }]` |

---

## 12 · Anti-Patterns to Avoid

1. **Per-category collections.** `feedings`, `medications`, `turnouts`… that's the bug we're refactoring out. One `tasks` collection. Forever.
2. **Mutating completed Tasks.** Always void + re-complete via new ID. Audit trail is the product.
3. **Inline side effects in routes.** Notifications, timelines, analytics — all funnel through TaskEvent. No exceptions.
4. **Eager pre-materializing infinite recurrences.** Bounded 14-day horizon. Compute on demand beyond.
5. **Server-trusted timestamps from offline clients.** Accept client `completed_at`, **also** store `server_received_at`, and clamp drift > 24h with a flag.
6. **Polling the API from the mobile client.** Use a single Today subscription (WebSocket in P2; polling-every-60s acceptable in P1).
7. **Cross-tenant joins.** Every query carries `tenant_id`. Indexes are `(tenant_id, …)`. No exceptions.
8. **Renaming enum values.** Treat enums as a wire contract. Add new values; never rename.
9. **Embedding TaskTemplate inside Task.** Denormalize only the fields needed for display/perf. Templates evolve; embedded snapshots rot.
10. **Special-casing categories in the engine core.** Category logic lives in payload validators, not in lifecycle code. The engine doesn't know what feeding is.

---

## 13 · Indexing Plan (Mongo)

```
tasks:
  { tenant_id: 1, scheduled_at: 1, status: 1 }       // Today view
  { tenant_id: 1, linked_horse_ids: 1, scheduled_at: -1 }  // horse timeline
  { tenant_id: 1, assignee_user_id: 1, status: 1 }   // staff queue
  { tenant_id: 1, template_id: 1, scheduled_at: 1 }  // re-materialization

task_completions:
  { task_id: 1, client_completion_id: 1 } unique     // idempotency
  { tenant_id: 1, completed_by_user_id: 1, completed_at: -1 }

task_events:
  { tenant_id: 1, subject_horse_ids: 1, occurred_at: -1 }
  { tenant_id: 1, actor_user_id: 1, occurred_at: -1 }
  { tenant_id: 1, event_type: 1, occurred_at: -1 }

task_templates:
  { tenant_id: 1, active: 1, category: 1 }
```

---

## 14 · Backend File Layout (proposed refactor)

```
/app/backend/
├── server.py                  # FastAPI app, router includes only
├── core/
│   ├── auth.py                # JWT, current_user dependency
│   ├── db.py                  # Mongo client + indexes bootstrap
│   ├── time.py                # UTC helpers, RRULE expansion
│   └── errors.py
├── models/
│   ├── task.py                # Task, TaskTemplate, TaskCompletion, TaskEvent
│   ├── horse.py
│   └── user.py
├── routes/
│   ├── tasks.py
│   ├── task_templates.py
│   ├── horses.py
│   ├── timelines.py
│   ├── onboarding.py          # existing
│   ├── invites.py             # existing
│   └── reports.py             # existing
├── services/
│   ├── task_engine.py         # lifecycle transitions, completion logic
│   ├── materializer.py        # RRULE → Task occurrences
│   ├── event_dispatcher.py    # TaskEvent → timelines + analytics
│   └── analytics_rollup.py
├── mailer.py                  # existing
└── tests/
    ├── test_task_engine.py
    ├── test_materializer.py
    └── test_idempotency.py
```

> Refactor lands *with* Phase 2 implementation, not as a separate commit. We avoid a "big bang move" that breaks the current healthy MVP.

---

## 15 · Future Extensibility (intentionally out of scope for P1)

- **WebSocket fanout** for live Today view across devices.
- **AI suggestions** (Claude Sonnet 4.5) — "Halo skipped feed twice this week" surfaced as a soft nudge on the timeline.
- **Wellness rollups** — derive vitals trends from rehab + vet + medication completions.
- **Owner-portal feed** — read-only Timeline scoped to an owner's horses.
- **Webhooks** for vet integrations / feed mill suppliers.
- **Photo evidence** on completions (object storage, signed URLs).
- **Role-based default views** — groom defaults to bulk-mode; trainer defaults to per-horse.

Every one of these slots into the engine *without schema changes* — the entire point of the unification.

---

## 16 · Phase 1 Definition of Done

- [ ] Mongo collections + indexes created on app boot.
- [ ] CRUD for TaskTemplate (all 8 categories) via API + UI.
- [ ] Materializer job populates 14-day rolling horizon every 15 min.
- [ ] `GET /api/tasks/today` returns the §9 urgency-grouped payload.
- [ ] Mobile Today view: swipe-to-complete, bulk-select, filter chips, optimistic UI, retry queue, sync indicator.
- [ ] Idempotent `complete` + `bulk-complete` endpoints with `client_completion_id`.
- [ ] TaskEvent rows emitted for every completion + lifecycle transition.
- [ ] Horse timeline view (read-only) sourced from TaskEvent.
- [ ] Seed data: one TaskTemplate per category for the demo tenant.
- [ ] Tests: unit (engine, materializer, idempotency) + integration (today view) + one e2e (complete a task, see it on timeline).
- [ ] No regression in existing onboarding / invites / reports flows.
- [ ] Lavender pearl design system preserved end-to-end.

---

## 17 · Open Questions for User

1. **Skip vs. Refused:** I've modeled both. Confirm you want them distinct, or collapse into a single `skipped` with a reason field?
2. **Owner visibility:** for Phase 1, should owners see *anything* from the new task engine (e.g. their horse's timeline), or is that strictly Phase 2?
3. **Bulk-complete payload editing:** when a staff member bulk-completes 8 stalls, do they edit each `payload_actual` individually, or accept template defaults silently with an "edit" affordance per row?
4. **Time zones:** all scheduling stored in UTC; display in barn's configured TZ from `BarnSettings`. Confirm there's no per-user TZ requirement in P1.
5. **Hard delete policy:** I've gone soft-delete everywhere. Any compliance reason to expose hard-delete to admins?

---

*End of blueprint. Awaiting approval to proceed to Phase 2 (backend implementation).*
