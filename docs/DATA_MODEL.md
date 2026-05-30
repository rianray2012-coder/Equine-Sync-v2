# DATA_MODEL.md
# EquineSync Data Model

> Every major operational entity must include: `id`, `barn_id`, `created_at`, `updated_at`, `created_by` (per `ENGINEERING_RULES.md`). See `SCHEMA_CHANGE_POLICY.md` before changing any schema.
>
> **Current-state note:** Some entities below describe the **target** schema. The live code does not yet enforce `barn_id`/`created_by` on every entity (notably the `User` model currently lacks `barn_id`). Gaps are tracked in `KNOWN_TECH_DEBT.md` and sequenced in Phase 4.

---

## Barn
Represents a single operational organization (tenant).

| Field | Type | Notes |
|---|---|---|
| `id` | string | primary key |
| `name` | string | |
| `address` | string | |
| `timezone` | string | IANA tz |
| `subscription_plan` | string | |
| `created_at` | ISO datetime | |

**Relationships:** has many `User`, `Horse`, `Invoice`, `Task`.

---

## User
Represents a platform user.

| Field | Type | Notes |
|---|---|---|
| `id` | string | primary key |
| `barn_id` | string | **target** (not yet enforced in code) |
| `first_name` | string | |
| `last_name` | string | |
| `email` | string | unique, lowercased |
| `role` | enum | see roles below |
| `phone` | string | |
| `status` | string | active / invited / disabled |
| `created_at` | ISO datetime | |

**Roles:** `admin`, `barn_manager`, `trainer`, `groom`, `working_student`, `horse_owner`, `rider`, `parent`, `veterinarian`, `farrier`.

> **Reconciliation note:** Live code stores `full_name` (single field) + `password_hash`; it does not yet store `first_name`/`last_name`/`barn_id`/`phone`/`status`. The role list in code matches the target.

**Relationships:** has many `Task`.

---

## Horse
Represents an equine profile.

| Field | Type | Notes |
|---|---|---|
| `id` | string | |
| `barn_id` | string | |
| `name` | string | |
| `breed` | string | |
| `sex` | string | |
| `color` | string | |
| `age` | number | |
| `owner_ids` | string[] | |
| `trainer_id` | string | |
| `status` | string | active / archived |
| `special_instructions` | string | |

**Relationships:** has many `CareTask`, `MedicationSchedule`, `IncidentReport`, `Invoice`.

---

## CareTask
Tracks operational care actions.

| Field | Type | Notes |
|---|---|---|
| `id` | string | |
| `barn_id` | string | |
| `horse_id` | string | |
| `task_type` | enum | see below |
| `assigned_to` | string | user id |
| `due_date` | ISO datetime | |
| `status` | string | scheduled / completed / missed / delayed |
| `notes` | string | |
| `completed_at` | ISO datetime | |

**Task types:** `feeding`, `turnout`, `medication`, `stall_cleaning`, `rehab`, `grooming`, `exercise`, `show_prep`.

> **Reconciliation note:** Live operational timeline is implemented as `task_events` (unified event-driven engine, see `TASK_ENGINE_ARCHITECTURE` in `/app/memory`). `CareTask` here is the documented logical model; the physical collection is `task_events`.

---

## MedicationSchedule
Tracks horse medication instructions.

| Field | Type |
|---|---|
| `id` | string |
| `horse_id` | string |
| `medication_name` | string |
| `dosage` | string |
| `frequency` | string |
| `start_date` | ISO date |
| `end_date` | ISO date |
| `instructions` | string |

---

## Invoice
Tracks owner billing.

| Field | Type |
|---|---|
| `id` | string |
| `barn_id` | string |
| `owner_id` | string |
| `horse_id` | string |
| `invoice_number` | string |
| `line_items` | object[] |
| `subtotal` | number |
| `tax` | number |
| `total` | number |
| `status` | string |
| `due_date` | ISO date |

---

## AuditLog
Immutable operational history. **(Target — not yet implemented; see Phase 5.)**

| Field | Type |
|---|---|
| `id` | string |
| `barn_id` | string |
| `actor_id` | string |
| `resource_type` | string |
| `resource_id` | string |
| `action` | string |
| `old_value` | object |
| `new_value` | object |
| `timestamp` | ISO datetime |

---

## Known live collections (observed in code, for reference)
`users`, `refresh_tokens`, `task_events`, `service_requests`, `horses`, `inventory`, `locations`, `feed_templates`, `recurring_schedules`, `staff_invites`, `onboarding_progress`, `notifications`.
