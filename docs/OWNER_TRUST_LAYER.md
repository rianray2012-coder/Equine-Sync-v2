# Owner Trust Layer (Phase 7)

> Authoritative spec: `docs/OWNER_TRUST_FRAMEWORK.md` + `docs/PHASED_EXECUTION_PLAN.md`
> §Phase 7 (goals: improve owner dashboard · weekly recap framework ·
> **owner-facing update controls** · **approval flow for sensitive updates**).
>
> Boundary: each sub-phase is separately gated (plan → approval → implement →
> Codex review). **7A is backend-only** — no frontend, no task-engine, billing,
> onboarding, or scheduler changes.

## Sub-phases
- **7A — Owner Update model + lifecycle** ✅ **DONE (2026-06-06)** — backend
  foundation: the `owner_updates` collection + `/api/owner-updates` lifecycle
  (`draft → published → archived`), barn + owner isolation, role gates, and
  high-signal audit. *(this doc)*
- **7B — Approval flow for sensitive updates** ✅ **DONE (2026-06-06)** — review
  workflow `draft → pending_review → published` (+ `request-changes → draft`),
  dedicated `owner_update:review` cap, four-eyes on sensitive approvals, audit
  `submitted`/`approved`/`changes_requested`. *(this doc)*
- **7C — Owner dashboard + update controls (frontend)** — owner-facing "Updates
  from your barn" feed, a staff composer, and a manager review queue. *(planned)*
- **7D — Owner dashboard polish + docs/test consolidation** — billing/upcoming
  visibility, recap integration, framework↔implementation map. *(planned)*

## 7A — Owner Update model + lifecycle ✅
An **Owner Update** is a publishable note authored by barn staff about a specific
horse, with an explicit lifecycle and an internal vs owner-facing visibility flag.
This is the first concrete primitive of the Owner Trust Layer.

### Data model — `owner_updates` collection (additive, no migration)
| Field | Notes |
|---|---|
| `id` | uuid |
| `barn_id` | Phase-4 tenant stamp (`stamp_barn`) |
| `horse_id` | validated ∈ barn on create (6A contract; foreign/absent → generic 404) |
| `author_user_id` | creator |
| `kind` | `routine \| training \| wellness \| incident \| billing \| recap` (422 on other) |
| `body` | required, non-empty (422 on empty) |
| `visibility` | `internal \| owner_facing` (default `owner_facing`) |
| `sensitive` | bool, **stored in 7A but publish-blocked** — a sensitive draft cannot be published until the 7B review gate exists (publish returns `409`). Not otherwise acted on in 7A. |
| `status` | `draft \| pending_review \| published \| archived` (full enum; 7A wires only draft→published→archived) |
| `created_at` / `updated_at` | ISO |
| `published_at` / `published_by` | set on publish |
| `reviewed_by` | reserved for 7B |
| `archived_at` / `archived_by` | set on archive (soft — row is never deleted) |

### Endpoints — `routes/owner_updates.py` (prefix `/api/owner-updates`)
| Method / Path | Access | Behavior |
|---|---|---|
| `POST /owner-updates` | `owner_update:create` | create `draft` (validates `horse_id ∈ barn`) |
| `GET /owner-updates?horse_id=&status=` | owner ⇒ own horses' published+owner_facing; staff (create-cap) ⇒ barn-scoped all; else 403 | list (owner sort `published_at`, staff sort `created_at`) |
| `GET /owner-updates/{id}` | same model as list | read one (owner: generic 404 for draft/internal/foreign) |
| `PATCH /owner-updates/{id}` | `owner_update:create` | edit **draft only** (`409` otherwise) |
| `POST /owner-updates/{id}/publish` | `owner_update:publish` | `draft → published` (`409` otherwise); **sensitive drafts are publish-blocked → `409 "Sensitive updates require review"`** (status unchanged, no audit emitted); emits audit on success |
| `POST /owner-updates/{id}/archive` | `owner_update:archive` | `published → archived` (`409` otherwise); soft; emits audit |

### Permissions (additive in `core/permissions.py` — no existing capability changed)
| Capability | Roles | Denial message |
|---|---|---|
| `owner_update:create` | admin, barn_manager, trainer | `Insufficient role to manage owner updates` |
| `owner_update:publish` | admin, barn_manager, trainer | `Insufficient role to publish owner updates` |
| `owner_update:archive` | admin, barn_manager, trainer | `Insufficient role to archive owner updates` |

Staff list/read reuses the `owner_update:create` capability as the read gate in
7A (`403 "Insufficient role to view owner updates"` for non-owner non-staff, e.g.
groom/vet). A dedicated read capability can be split out later if grooms/vets need
read access.

### Isolation
- **Barn:** every read/write goes through `barn_filter`; an other-barn update never
  appears in lists and returns `404` on direct GET (4E contract).
- **Owner:** owners are scoped to horses where `horse.owner_id == user.id` **and**
  the update is `status=published` + `visibility=owner_facing`. Drafts, internal
  notes, and other horses' updates return a **generic 404** (no existence leak).
  *(Compatibility note: this relies on `horses.owner_id` pointing at the owner's
  user id — the same linkage the owner digest uses. The demo seed currently links
  horses to roster-owner records, so seeded owners may see nothing until linkage
  is established; documented, not a 7A regression.)*

### Audit (existing Phase-5 fail-open service — no new subsystem)
- `owner_update.published` and `owner_update.archived` only, via
  `await audit.record(...)` (fail-open — never blocks the action).
- `resource_type="owner_update"`, `resource_id=<update id>`,
  `metadata={"kind", "visibility"}` only — **no body/title/owner/horse/email text**.

### Tests
`tests/test_owner_updates.py` (9) — staff lifecycle + 409 guards; edit-draft-only;
foreign horse 404 + empty body 422; owner/groom cannot create; groom cannot read;
owner sees only own published owner-facing updates (drafts/internal/foreign hidden,
404 on direct GET); **sensitive draft is publish-blocked (409, stays draft, owner
can't see it, no publish audit)**; other-barn update never leaks; publish/archive
emit minimal, non-PII audit. Backend suite: **499 passed / 3 skipped** (490 + 9).

## 7B — Approval flow for sensitive updates ✅
Adds the human-review path so sensitive Owner Updates can reach owners safely.
Backend only — no frontend.

### Lifecycle (7B adds the review transitions)
```
draft ──submit──▶ pending_review ──approve──▶ published ──archive──▶ archived
  ▲                     │
  └──request-changes────┘
draft ──publish──▶ published      (non-sensitive only; sensitive draft publish → 409)
```

### New endpoints — `routes/owner_updates.py`
| Method / Path | Access | Transition | Notes |
|---|---|---|---|
| `POST /owner-updates/{id}/submit` | `owner_update:create` | `draft → pending_review` | any draft may submit; sensitive drafts MUST use this; `409` if not draft; audit `owner_update.submitted` |
| `POST /owner-updates/{id}/approve` | `owner_update:review` | `pending_review → published` | stamps `reviewed_by` + `published_at/by`; **four-eyes**: author cannot approve their own *sensitive* update → `403 "Author cannot approve their own sensitive update"`; `409` if not pending_review; audit `owner_update.approved` |
| `POST /owner-updates/{id}/request-changes` | `owner_update:review` | `pending_review → draft` | optional capped `review_note` (≤500) stored on the update, **never audited**; stamps `reviewed_by`; `409` if not pending_review; audit `owner_update.changes_requested` |

- `publish` unchanged (non-sensitive `draft → published`; sensitive draft still `409`).
- `PATCH` unchanged (draft-only). `archive` unchanged.

### Permissions (additive)
- New `owner_update:review` = {admin, barn_manager, trainer}, deny `"Insufficient role to review owner updates"`. `submit` reuses `owner_update:create`.

### Four-eyes (separation of duties)
- Enforced for **sensitive** updates only: `doc.sensitive and author_user_id == approver.id → 403`. Non-sensitive submissions may be self-approved by the author.

### Audit (existing fail-open service)
- `owner_update.submitted`, `owner_update.approved`, `owner_update.changes_requested`
  — all `resource_type="owner_update"`, metadata `{kind, visibility}` only.
  The `review_note` is **never** written to audit.

### New field
- `review_note` (`str|None`, ≤500) — stored on the update by `request-changes`; defaults `None` on create.

### Tests
`tests/test_owner_updates.py` extended (now 13) — sensitive happy path (publish-blocked →
submit → owner-hidden while pending → four-eyes 403 → second-reviewer approve → owner-visible)
with `submitted`+`approved` audit; `request-changes` stores the note but audits without it;
state guards (`approve`/`request-changes` only from pending_review; `submit` only from draft);
role gates (groom can't submit, owner can't review); non-sensitive submit + self-approve
allowed. Backend suite: **503 passed / 3 skipped** (499 + 4).

## Deferred / backlog (NOT in 7A)
- **Frontend** (owner feed, staff composer, review queue) — **7C**.
- Additive index on `owner_updates(barn_id, horse_id, status)` if read volume warrants.
- `owner_update:read` split (grooms/vets read access) if needed.
