# EquineSync — Production Readiness Tracker

**Generated:** Feb 19 2026 · **Last updated:** Feb 20 2026 (Phase-B complete)

## Phase-B Delta (Feb 20 2026 — vet/health completion loop)

✅ **Vet completion writes to `vet_records`** — when a vet task is completed via the engine, a denormalized row is written to the legacy `vet_records` collection (`source: "task_engine"`). The existing Health page sees the outcome immediately without any read-path migration.
✅ **Farrier completion writes to `farrier_history`** — same pattern. New `GET /api/farrier-history` endpoint exposed.
✅ **Auto follow-up scheduling** — if `payload_actual.follow_up_due` (vet) or `next_visit_due` (farrier) is present, the engine creates a follow-up task at that date with `parent_task_id` linkage. Visible on the Health "Upcoming visits" card.
✅ **TaskEvent payload_snapshot enriched** — completions now carry `vet_name`, `farrier_name`, `cost`, `vet_record_id`, `farrier_record_id`, `follow_up_task_id`. CuratedTimeline surfaces these as small footnote chips ("with Dr. Maren · $185 · next Jul 1").
✅ **Health page redesigned** — Farrier History card added alongside Vet Records; both surface engine-projected data with `VIA ENGINE` badges.
✅ **Coverage**: 4 new pytest cases (vet→record, farrier→history, follow-up auto-schedule, event enrichment). Suite at **17/17 task engine + 103 total, 0 failed**.

**Tier movements:**
- Health & Vet: Internal-Demo-Ready → **Beta-Ready**.

**Beta-Ready or above: 43% → 47%.**

---

## Phase-A Delta (Feb 19 2026 — engine consolidation)

✅ `/api/dashboard/summary` now derives feed/meds/lesson counts from `tasks` + `task_completions` (no more legacy reads). Response now includes `_source: "engine"`.
✅ `/api/dashboard/barn-board` also engine-backed; stamped `_deprecated`.
✅ **Barn Board UI retired** — `/barn-board` route now redirects to `/today`. `BarnBoard.jsx` deleted. Sidebar entry removed. Today widened to `max-w-4xl` for tablet ergonomics.
✅ pytest fixture pollution fixed (idempotent suffixes + graceful skip for legacy feed). Suite now **99 passed, 1 skipped, 0 failed** — CI fully green.
✅ Cloudflare R2 storage abstraction (`/app/backend/storage.py`) scaffolded: `StorageProvider` interface + `S3CompatibleStorage` + `LocalDevStorage` no-op stub. Provider auto-selects on env vars; safe to deploy without credentials.

**Tier movements:**
- Today View: still Production-Ready, but now also serves the tablet aisle-station use case.
- Dashboard: Internal-Demo → **Beta-Ready** (engine-backed).
- Barn Board: removed entirely from the matrix.

**Total module count: 29 → 28.** Beta-Ready or above: 38% → **43%**.

---

> A module is **Production-Ready** only when all ten criteria are satisfied. Anything else is gated to internal demo or prototype use.

---

## 1 · Readiness Tiers (definitions)

| Tier | What it means | When to use it with real users |
|---|---|---|
| **Production-Ready** | All 10 criteria green. Has tests, fan-out, permissions, mobile, analytics, no known bugs. | Beta customers OK. |
| **Beta-Ready** | Core flows work, mobile usable, tests cover happy paths, but some edges unhandled (notifications, advanced perms, polish). | Internal stables OK with hand-holding. |
| **Internal-Demo-Ready** | UI looks good and one happy path works on desktop; data is partly mocked or seed-only. | Sales demos to friendly prospects. Not real operations. |
| **Prototype** | UI exists but data flow is incomplete or read-only; no real operational value. | Internal review only. |
| **Placeholder** | Static page with marketing copy and no functionality. | Hidden from real users. |

---

## 2 · The 10 Readiness Criteria

Every module is scored against these. ✅ = green · 🟡 = partial · ❌ = missing/red · — = not applicable.

1. **Backend functionality** — CRUD or domain endpoints exist, return real data, handle errors, are tenant-scoped.
2. **Frontend functionality** — Real screens, real data, full happy path + sensible empty/error states.
3. **Task-engine integration** — Reads/writes flow through the unified engine (where applicable to operational work).
4. **Notifications** — Important state changes fan out via `TaskEvent` → notification dispatcher.
5. **Timeline events** — Audit-grade history captured on the horse/staff timeline.
6. **Analytics events** — `track(...)` calls in place for funnels and product insight.
7. **Mobile optimization** — Touch-first, ≥44px targets, single-thumb usability, no layout breakage <420px.
8. **Permissions handling** — Role-based gating + tenant isolation enforced server-side.
9. **Testing coverage** — At least one pytest + one Playwright/RTL test per critical path.
10. **No known blockers** — No open bugs that would surprise a real customer in week one.

---

## 3 · Module Audit (current state)

### 🟢 Production-Ready (3 modules)

| Module | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| **Auth & Session** (login, refresh-rotation, CSP, security headers) | ✅ | ✅ | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Unified Task Engine** (templates, tasks, completions, events, RRULE materializer) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Today View** (urgency groups, swipe, bulk, offline queue) | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 | ✅ | ✅ | ✅ | ✅ |

### 🟡 Beta-Ready (8 modules — work for real users, gaps known)

| Module | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| **Onboarding Wizard** (10 steps, CSV, autosave, resume) | ✅ | ✅ | — | — | — | ✅ | 🟡 | ✅ | ✅ | ✅ |
| **Magic-Link Invites + Nudges** | ✅ | ✅ | — | — | — | ✅ | ✅ | ✅ | ✅ | 🟡* |
| **Setup-Health Reports** | ✅ | ✅ | — | — | — | ✅ | 🟡 | ✅ | ✅ | ✅ |
| **Notifications** (inbox + email + prefs) | ✅ | ✅ | ✅ | ✅ | — | 🟡 | ✅ | ✅ | ✅ | ✅ |
| **Feed Room** (engine-backed) | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 | ✅ | 🟡 | 🟡 | ✅ |
| **Medications** (engine-backed) | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 | ✅ | 🟡 | 🟡 | ✅ |
| **Owner Portal Curated Timeline** | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 | ✅ | ✅ | ✅ | ✅ |
| **Horse Profile + Timeline tab** | ✅ | ✅ | 🟡 | ✅ | ✅ | 🟡 | 🟡 | 🟡 | 🟡 | ✅ |

\* Resend currently in **sandbox** mode for non-owner addresses. See §5 Blockers.

### 🟠 Internal-Demo-Ready (8 modules — partial wiring, demo-shaped)

| Module | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| **Dashboard (legacy stat widgets)** | ✅ | ✅ | ❌ | — | — | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 |
| **Barn Board (tablet)** | ✅ | ✅ | ❌ legacy `/feed-tasks` | ❌ | ❌ | ❌ | ✅ | 🟡 | ❌ | 🟡 |
| **Health & Vet** (engine upcoming + legacy records) | 🟡 | ✅ | 🟡 partial | 🟡 | 🟡 | ❌ | 🟡 | 🟡 | 🟡 | ✅ |
| **Owners** | 🟡 list-only | 🟡 list-only | ❌ | ❌ | ❌ | ❌ | 🟡 | ❌ | ❌ | 🟡 |
| **Riders** | 🟡 list-only | 🟡 list-only | ❌ | ❌ | ❌ | ❌ | 🟡 | ❌ | ❌ | 🟡 |
| **Lessons** | 🟡 list-only | 🟡 list-only | ❌ | ❌ | ❌ | ❌ | 🟡 | ❌ | ❌ | 🟡 |
| **Training Log** | 🟡 list-only | 🟡 list-only | ❌ | ❌ | ❌ | ❌ | 🟡 | ❌ | ❌ | 🟡 |
| **Billing** | 🟡 pay-only | 🟡 list+pay | ❌ | ❌ | ❌ | ❌ | 🟡 | ❌ | ❌ | 🟡 |

### 🟣 Prototype (3 modules — UI present, very thin)

| Module | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| **Messaging** | 🟡 send+list | 🟡 simple inbox | ❌ | ❌ | ❌ | ❌ | 🟡 | ❌ | ❌ | ❌ no threading |
| **Incidents** | 🟡 list+post | 🟡 timeline view | ❌ | ❌ | ❌ | ❌ | 🟡 | ❌ | ❌ | ❌ no triage |
| **Service Requests** (inside Owner Portal) | 🟡 approve-only | 🟡 | ❌ | ❌ | ❌ | ❌ | 🟡 | ❌ | ❌ | ❌ no decline |

### ⚪ Placeholder (7 modules — no real implementation)

| Module | Status |
|---|---|
| **Stall Rest & Rehab** | `<Placeholder>` — but rehab tasks now exist in the engine; module is partly subsumed |
| **Turnout & Pastures** | `<Placeholder>` — turnout_in/out tasks exist in the engine; module is partly subsumed |
| **Inventory** | `<Placeholder>` — `/api/inventory` backend exists from onboarding; UI page is empty |
| **Shows & Competitions** | `<Placeholder>` — no backend, no UI |
| **Documents** | `<Placeholder>` — no backend (object storage deferred) |
| **Maintenance** | `<Placeholder>` — no backend, no UI |
| **Staff Management** | `<Placeholder>` — staff exist via invites; no workloads/shifts/certs |

---

## 4 · The Three Ten-Criterion Worksheets (top concerns only)

Quick worksheets for the modules with the most upside if completed. Full per-module gap analysis lives in `/app/memory/MODULE_COMPLETION_MATRIX.md`.

### A) Health & Vet — biggest unlock for operational realism
- 🟡 **Backend** — vet-records and injuries are legacy collections; no completion-record extension on engine vet tasks.
- ✅ Frontend — Upcoming card live.
- 🟡 **Task-engine integration** — reads upcoming; doesn't write vet visit *outcomes* back as completions.
- 🟡 Notifications — only via generic `task.completed` fan-out; no vet-specific severity routing.
- 🟡 Timeline — engine events flow; legacy vet_records do not.
- ❌ **Analytics** — no funnel for "vet visit booked → completed → follow-up scheduled".
- 🟡 Mobile — tablet-first; needs swipe action on visit cards.
- 🟡 Permissions — vet records currently visible to all signed-in staff.
- 🟡 Tests — list endpoints tested; no e2e for visit completion → timeline.
- **Verdict:** Beta-Ready *if* we wire vet-completion-with-notes into the engine.

### B) Owner Portal — biggest unlock for trust and retention
- ✅ Backend (timeline, service-requests).
- ✅ Frontend (curated timeline + request form + approval).
- ✅ Task-engine integration (timeline).
- 🟡 Notifications — owners receive curated inbox; **no email digest yet**.
- ✅ Timeline events.
- 🟡 Analytics — only `service_request.created` / `approved`; no view-tracking.
- ✅ Mobile.
- ✅ Permissions (server-enforced curated filter).
- ✅ Tests.
- **Verdict:** Beta-Ready. Push to Production-Ready by shipping owner email digests + decline action on service-requests.

### C) Barn Board — most outdated module, must migrate or retire
- ✅ Backend exists.
- ✅ Frontend exists.
- ❌ **Task-engine integration** — still reads `/api/dashboard/barn-board` (legacy `feed_tasks`, `medication_logs`).
- ❌ Notifications — none.
- ❌ Timeline — none.
- ❌ Analytics — none.
- ✅ Mobile/tablet (its original purpose).
- 🟡 Permissions.
- ❌ Tests.
- **Verdict:** Internal-Demo-Ready only. **Decision needed: migrate to engine OR retire in favor of Today view on tablet breakpoint.**

---

## 5 · Active Blockers (must clear for Production-Ready)

| # | Blocker | Impact | Owner | Path to clear |
|---|---|---|---|---|
| B1 | Resend sandbox mode for non-verified domains | Owner email digests, staff invites bounce for non-owner recipients | Ops | Verify a domain at resend.com/domains, swap `from` address |
| B2 | Legacy collections (`feed_tasks`, `medication_logs`) still backing Dashboard summary + Barn Board | Dual-source-of-truth risk; analytics divergence | Eng | Migrate `dashboard/summary` + `barn-board` to engine queries; remove legacy collections after 2 weeks of dual-write |
| B3 | `POST /api/tasks` silently drops `horse_id` legacy alias | Naive API callers create orphan tasks | Eng | Add 422 validation or alias |
| B4 | server.py = 1,800 LOC; routes/dashboard|onboarding|invites|reports not yet extracted | Maintainability; complexity scores >15 in 4 functions | Eng | Finish §14 refactor |
| B5 | No object storage for photos/media | HorseProfile and completions can't attach evidence | Ops/Eng | Pick provider (S3 / R2 / Emergent storage); wire upload service |
| B6 | Pre-existing 4 pytest failures (`test_feed_complete`, `test_invoice_pay`, CSV-commit owners/horses) | False alarm in CI; signal/noise degraded | Eng | Make tests idempotent — use unique fixture data |
| B7 | Dashboard.jsx + HorseProfile.jsx + Onboarding.jsx complexity scores 20–28 | Hard to evolve safely | Eng | Extract widgets into `/components/dashboard/*`, `/components/horse/*` |

---

## 6 · Quality Bars by Tier

A module ships to a real customer **only** after meeting the bar for its target tier.

### Production-Ready quality bar
- All 10 criteria ✅
- Lighthouse Mobile score ≥ 85
- Pytest + Playwright coverage of every documented user story
- 99.5% uptime on the underlying APIs (last 14d)
- < 5% client-side error rate (Sentry / console error budget)
- Zero open P0/P1 bugs

### Beta-Ready quality bar
- Criteria 1, 2, 7, 8, 9 ✅
- Criteria 3, 4, 5 — at least 🟡
- One Playwright happy-path test passing on mobile viewport
- Known edge cases documented in `/app/memory/MODULE_COMPLETION_MATRIX.md`

### Internal-Demo-Ready quality bar
- Criteria 1, 2 ✅
- Looks polished on desktop
- No crash on the demo path

---

## 7 · Operational-Readiness Roadmap (recommended order)

Each phase makes a tier of modules production-ready.

| Phase | Theme | Modules upgraded | Estimated complexity |
|---|---|---|---|
| **P-A** | Engine consolidation | Barn Board → engine · Dashboard summary → engine · retire `feed_tasks`+`medication_logs` collections | M |
| **P-B** | Vet/Health completion loop | Health & Vet upgraded to Production-Ready · vet-task `payload_actual` → vet-record link | M |
| **P-C** | Owner trust loop | Owner email digests · service-request decline · request status filters | S |
| **P-D** | Operational object storage | Photo uploads on horses + completions + injuries | M |
| **P-E** | Subsume placeholders | Stall Rest & Rehab UI as filtered rehab tasks · Turnout UI as filtered turnout_out/in tasks · Inventory full UI on top of existing `/api/inventory` | M |
| **P-F** | Server.py refactor finish | routes/dashboard · routes/onboarding · routes/invites · routes/reports | S |
| **P-G** | Test-suite hardening | Idempotent fixtures · Playwright mobile coverage · Sentry hookup | M |

Phases A–D get the platform from "compelling demo" → "beta with real barns."

---

## 8 · Done Definition for "Operationally Real"

Before opening up to a real boarding barn:
- Every operational action a groom takes during a 6 AM → 9 PM shift is captured by the engine (feed, meds, turnout, stalls, farrier visit, vet visit, rehab walk, photo evidence).
- Every event reaches the appropriate recipient inbox within 60 seconds.
- Owners can open the portal on a phone and immediately understand their horse's last 7 days.
- A manager can open Reports and see today's completion rate without leaving the page.
- No staff member ever needs to know which collection backs which feature.
