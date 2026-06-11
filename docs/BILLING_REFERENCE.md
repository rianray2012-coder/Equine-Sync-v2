# BILLING_REFERENCE.md
# EquineSync — Billing Reference (Phase 9, single source of truth)

Authoritative reference for the **Phase 9 billing surface**: invoice integrity
(9A), recurring charges (9B-1 CRUD + 9B-2 materializer), and invoice clarity UI
(9C). Billing is intentionally **invoice bookkeeping only** — there is **no
payment processor** (no Stripe/charges/subscriptions); `POST /invoices/{id}/pay`
is a status flip. A real payments integration would be a separate, explicitly
scoped feature.

> Code: `backend/routes/billing.py`, `backend/routes/recurring_charges.py`,
> index bootstrap in `backend/core/lifespan.py`, frontend
> `frontend/src/components/InvoiceLineItems.jsx` /
> `InvoiceBreakdown.jsx` / `OwnerBillingCard.jsx`, `Billing.jsx`,
> `frontend/src/lib/invoices.js`.

---

## 1. Endpoint map

| Method & path | Auth / capability | Purpose |
|---|---|---|
| `GET /api/invoices` | any authenticated user | List invoices. **Owner-scoped** for `role==horse_owner` (only their own); staff get the full barn-scoped list. |
| `POST /api/invoices` | any authenticated user (staff in practice) | Create an invoice. Server-authoritative totals (9A). |
| `POST /api/invoices/{id}/pay` | any authenticated user | Idempotent status flip to `paid` + `paid_at`. Cross-barn id → `404`. |
| `POST /api/recurring-charges` | `recurring_charge:manage` = {admin, barn_manager} | Create a recurring-charge template (9B-1). |
| `GET /api/recurring-charges` | `recurring_charge:manage` | List (`?active`, `?owner_id`), barn-scoped. |
| `GET /api/recurring-charges/{id}` | `recurring_charge:manage` | Fetch one (barn-scoped; foreign → `404`). |
| `PATCH /api/recurring-charges/{id}` | `recurring_charge:manage` | Update fields (validated). |
| `POST /api/recurring-charges/{id}/deactivate` | `recurring_charge:manage` | Soft deactivate (idempotent; no hard delete). |
| `POST /api/admin/recurring-charges/run` | `recurring_charge:manage` | **9B-2 materializer** — manual, idempotent invoice generation for a month. |

Owners have **no** access to recurring-charge definitions; they only ever see
the resulting invoices via `GET /invoices`.

---

## 2. Schemas

### `invoices`
```
{
  id, barn_id, owner_id, horse_id,
  items: [ { description, label?, quantity?, unit_amount?, amount } ],
  subtotal, discount, tax_rate, tax_amount, total,   # server-computed (9A)
  due_date, status,           # status ∈ {open, paid, overdue}
  notes, created_at,
  paid_at?,                   # set by /pay
  # materializer-only (9B-2):
  recurring_charge_id?, period_key?, source?          # source = "recurring"
}
```
Legacy `{label, amount}` line items are preserved and `label` is mirrored to
`description`.

### `recurring_charges`
```
{
  id, barn_id, owner_id, horse_id?,
  description,
  items: [ LineItem ],         # same 9A LineItem shape, normalized on write
  discount, tax_rate,
  cadence,                     # "monthly" only
  day_of_month,                # 1..28
  start_date, end_date?,       # strict YYYY-MM-DD
  due_days,                    # >= 0
  active,                      # soft on/off
  last_run_period,             # YYYY-MM, advanced monotonically by 9B-2
  created_by, created_at, updated_at
}
```

---

## 3. Money math (shared helper)

`compute_money(items, discount, tax_rate)` in `routes/billing.py` is the single
pure function used by invoice create (9A), the recurring-charge template total
(9B-1 audit), and the materializer (9B-2):

- `subtotal = round(Σ line.amount, 2)`
- `discount` is an **absolute amount**, clamped to `0..subtotal`
- `tax_rate` is a **percentage** applied to `(subtotal − discount)`
- `tax_amount = round((subtotal − discount) × rate / 100, 2)`
- `total = round(subtotal − discount + tax_amount, 2)`

The server is **authoritative**: any client-supplied `total` is ignored.
Negative `amount`/`quantity`/`unit_amount`/`discount`/`tax_rate`, amount-less
lines, and empty `items` → `422`.

---

## 4. Materializer eligibility (9B-2)

`POST /admin/recurring-charges/run` accepts an optional `{"period": "YYYY-MM"}`
(default = current **UTC** month; bad format/month → `422`). It scans **all**
recurring charges in the caller's barn and classifies each:

A charge is **eligible** for the target `year-month` iff **all** hold:
- `active == true`
- `cadence == "monthly"`
- `start_date` is valid `YYYY-MM-DD` and its month `<=` the period
- `end_date` is absent, OR valid `YYYY-MM-DD` and its month `>=` the period

Everything else (inactive, non-monthly, not-yet-started, ended,
invalid/legacy date, or already generated for the period) is **skipped
defensively** and counted in `skipped_count` — never a run failure.

---

## 5. Dedupe / idempotency

- **Partial unique index** (created at startup by `ensure_billing_indexes`):
  `invoices (barn_id, recurring_charge_id, period_key)` where
  `source == "recurring"`. Legacy/manual invoices have no `source` and are
  excluded by the partial filter, so they never conflict.
- The run does a **find-before-insert** dedup check and also catches
  `DuplicateKeyError` (concurrent-run race) — either way the existing invoice is
  **skipped, never updated/overwritten/refreshed**.
- `last_run_period` is advanced **monotonically** via `max(existing, period_key)`
  (zero-padded `YYYY-MM` ⇒ lexical max == chronological max), so an older
  backfill run still generates its invoice but **never regresses** the field.
- Response: `{ period, generated_count, skipped_count, generated_invoice_ids[] }`.
- Generated invoices use the full **9A structure** plus `recurring_charge_id`,
  `period_key`, `source="recurring"`, `status="open"`,
  `due_date = day_of_month + due_days`, `notes = description`.

---

## 6. Audit events (fail-open, non-sensitive metadata only)

| Action | resource_type / id | Metadata |
|---|---|---|
| `invoice.paid` | `invoice` / invoice id | `{amount}` (numeric) |
| `recurring_charge.created` | `recurring_charge` / rc id | `{cadence, amount}` (template total) |
| `recurring_charge.updated` | `recurring_charge` / rc id | `{updated_fields: [names]}` (keys only) |
| `recurring_charge.deactivated` | `recurring_charge` / rc id | `{reason_provided: bool}` (no free text) |
| `recurring_charges.materialized` | `billing_run` / `period_key` | `{month, generated_count, skipped_count}` |

---

## 7. Owner vs staff visibility

- **Owners** (`role==horse_owner`): `GET /invoices` is auto-scoped to their own
  invoices (7D-1). The owner UI (`OwnerBillingCard.jsx`) shows open balance,
  next due, and **read-only** line-item/breakdown detail — **no pay action**, no
  recurring-charge visibility.
- **Staff**: full barn-scoped invoice list; `Billing.jsx` accordions reveal line
  items + breakdown and keep **Mark Paid**. A "Past due" hint shows on `open`
  invoices past `due_date` (visual only — does not mutate status).
- Shared display normalization is in `frontend/src/lib/invoices.js`
  (`normalizeInvoiceForDisplay`, `isPastDue`, `statusTone`), tolerant of legacy
  `label`-only items and missing breakdown fields.

---

## 8. Behavior → test-file coverage map

| Behavior | Test file |
|---|---|
| 9A server-computed totals, client-total ignored, legacy lines, discount/tax math, 422s | `backend/tests/test_billing_9a.py` |
| Route registration + auth + create/list/pay round-trip (3F) | `backend/tests/test_billing_routes.py` |
| Barn scoping: cross-barn list exclusion, primary stamp, cross-barn pay 404, same-barn pay (4B-4) | `backend/tests/test_billing_scoping.py` |
| Owner-scoped invoice visibility, staff full list, cross-barn no-leak (7D-1) | `backend/tests/test_owner_billing.py` |
| Recurring CRUD, ref validation, cadence/template/date validation, permissions, barn isolation (9B-1) + materializer eligibility/idempotency/totals/audit/backfill non-regression (9B-2) | `backend/tests/test_recurring_charges.py` |

Shared test boilerplate (API base URL, Mongo, auth headers, cleanup) lives in
`backend/tests/_billing_helpers.py` (domain-scoped, mirrors `_owner_helpers.py` /
`_care_helpers.py`).
