# EquineSync — Premium Equestrian Stable Management Platform

## Original Problem Statement
Premium all-in-one operating system for elite show barns, training facilities, lesson programs, rehab facilities, and luxury private equestrian operations. Combines horse care, stable operations, health tracking, rider progress, billing, communication, scheduling, staff management, and BI in a single mobile/tablet/desktop platform.

Brand: "Quiet luxury" — matte black, graphite, platinum, soft ivory, champagne accents. Cormorant Garamond (display) + Inter (body).

## User Choices (Feb 17 2026)
- Scope v1: Polished MVP first (core modules + rich demo data)
- Auth: JWT-based custom auth with role selection
- AI: Claude Sonnet 4.5 via Emergent LLM key
- Media: Object storage (deferred — using curated Unsplash photo URLs in v1)
- Design: Luxury matte black + champagne palette, Cormorant Garamond / Inter fonts

## Architecture
- **Backend**: FastAPI on 0.0.0.0:8001, supervisor-managed, MongoDB via MONGO_URL/DB_NAME from env
- **Auth**: JWT (HS256, 7-day expiry), bcrypt password hashing, role-based field on user
- **AI**: emergentintegrations.llm.chat → anthropic claude-sonnet-4-5-20250929
- **Frontend**: React 19, React Router v7, Tailwind + custom equine palette, lucide-react icons
- **Routes**: 23 routes under `/api/*`; auto-seed on startup if `users` collection empty

## What's Been Implemented (Feb 17 2026)

### Phase-C — Owner Trust Loop COMPLETE (Feb 20 2026)
- **Daily owner digest** (`/app/backend/owner_digest.py`): calm composition (no analytics) over the last 24h + 7d of curated TaskEvents (`{medication, farrier, vet, rehab, feed}`), idempotent daily pass keyed on `(owner_user_id, for_date)`, branded HTML + text renderers, unique index on `notification_digest_log`.
- **Endpoints**: `POST /api/notifications/digest/{preview,send-me}` (owner), `POST /api/admin/digest/run-now` (admin/manager).
- **Scheduler** in `server.py` startup wraps `run_daily_digest_pass` in an asyncio loop with a 6h warmup + 24h cadence; controlled by `DISABLE_AUTO_DIGEST` env var.
- **Service-request decline** (`POST /api/service-requests/{sr_id}/decline`) with optional `reason` (capped at 500 chars), surfaced to owner as "Note from the barn".
- **Backend role gating** on `/decline` AND `/approve` — restricted to `{admin, barn_manager, trainer}`; pending-only state guard (re-mutation returns 409). Closes auth gap surfaced by iteration_10 testing agent.
- **Frontend**:
  - `OwnerDigestCard.jsx` (new): preview + "send to me now" + digest-on/off toggle; calm "All quiet today" empty state; mobile-friendly; surfaces above Care Timeline on /owner-portal for `horse_owner` only.
  - `OwnerPortal.jsx`: Decline button + reason modal (data-testid `decline-modal`, `decline-reason-input`, `decline-confirm-btn`) gated to admin/manager/trainer.
  - `NotificationPrefsCard.jsx`: adds "Morning digest" toggle for `horse_owner` accounts only.
- **Tests**: 9/9 in `test_owner_trust.py` + 6/6 in `test_owner_trust_edges.py` PASS. Full suite **118 passed, 1 skipped** post-changes.

### Phase-F — Incremental `server.py` Refactor (Feb 20 2026 — IN PROGRESS)
- **Goal**: reduce monolithic `server.py` toward the blueprint target (< 700 lines) without behavior changes. Strict no-rewrite policy — extractions only, with pytest gates between moves.
- **Extracted (this session)**:
  - `routes/dashboard.py` (113 LOC) — `/dashboard/summary` engine-derived + `/dashboard/barn-board` deprecated wrapper with RFC 8594 headers.
  - `routes/reports.py` (258 LOC) — `/reports/setup-health`, `/reports/nudge-candidates`, `/admin/send-nudges`. Helpers (`setup_health_payload`, `nudge_candidates`, `send_nudges`) exposed on the router so the startup scheduler reuses them without re-implementation.
  - `routes/invites.py` (290 LOC) — `/invites` CRUD + `/invites/verify` + `/invites/accept` with full dep-injection (mailer, base-url resolver, analytics tracker, jwt issuer, refresh-token, onboarding-steps constant).
  - Auth gating + state-guard hardening on `/service-requests/{approve,decline}`.
- **Server.py size**: 1949 → 1531 lines (**~21% reduction**); all 118 tests still passing.
- **Pending**: `routes/onboarding.py` (~385 LOC block including CSV preview/commit) and optional `routes/tasks.py` thin wrapper. Frontend sub-component splits for `Today.jsx`/`Dashboard.jsx`/`Onboarding.jsx` remain on the deferred list.

### Phase 2 — Engine Integration, Auth Hardening, Notifications, Partial Refactor (Feb 19 2026)
- **Owner Portal Curated Timeline** — `/app/frontend/src/components/CuratedTimeline.jsx` surfaced on `/owner-portal` (with horse picker) and as a new `Timeline` tab on `/horses/:id`. Server-side filter enforced for `horse_owner` role: only `{medication, farrier, vet, rehab, feed}` events visible.
- **Feed/Medications/Health rewired to unified engine** — `/feed`, `/medications` now read `/api/tasks?category=feed|medication` via shared hook `useEngineTasksToday()` in `/app/frontend/src/lib/engineTasks.js`; complete/skip flow through the offline-tolerant taskSync queue. `/health` shows an engine-sourced "Upcoming visits" card (vet + farrier) above legacy historical records. Legacy `/feed-tasks` and `/medication-logs` collections remain readable for the dashboard summary widget but new writes flow through the engine.
- **Auth hardening** — `/app/backend/auth_security.py`:
  - JWT access TTL reduced from 7d → 4h (configurable via `JWT_EXP_HOURS` env)
  - Refresh-token rotation (30d, sha256-hashed at rest, **single-use enforced**), new endpoints `POST /api/auth/refresh`, `POST /api/auth/logout`, `POST /api/auth/logout-all`
  - `SecurityHeadersMiddleware` applies OWASP headers + CSP on every response (`X-Frame-Options=DENY`, `X-Content-Type-Options=nosniff`, `Referrer-Policy=strict-origin-when-cross-origin`, `Permissions-Policy`, `Strict-Transport-Security`, `Cross-Origin-Opener-Policy`, `Content-Security-Policy`)
  - Frontend axios interceptor (`/app/frontend/src/lib/api.js`) auto-refreshes on 401 with in-flight dedup, falls back to forced logout on refresh failure
- **Notification dispatcher** — `/app/backend/notifications.py`:
  - Background loop drains `TaskEvent` rows every 10s; marks `dispatched_at` to prevent double-send
  - Per-user `notification_preferences` document (inbox/email channel × event_type × category matrix)
  - Channel handlers: in-app inbox (always), email via Resend (P1), push deferred
  - Endpoints: `GET /api/notifications`, `POST /api/notifications/{id}/read`, `POST /api/notifications/read-all`, `GET/PUT /api/notifications/preferences`, `POST /api/notifications/drain` (admin force-drain)
  - Frontend: `NotificationsBell` (header bell with unread badge + dropdown), `NotificationPrefsCard` on Settings (channel toggles + event×category matrix)
  - Recipient routing: actor never self-notified; staff/admin recipients always; owners only for curated categories
- **Partial server.py refactor** — `routes/auth.py` extracted as a self-contained `build_router(db)` factory. Fixed a `load_dotenv` order bug (was running after submodule imports, causing JWT_SECRET fallback to "change-me" in route module). Notifications and task engine already shipped as separate modules earlier this session.
- **Tests**: 20/20 Phase 2 + 13/13 Task Engine regression pass (`/app/backend/tests/test_phase2.py`, `test_task_engine.py`); pre-existing 4 data-pollution failures in legacy tests are unrelated.
- **Testing agent verdict** (iteration_8): backend 100%, frontend 100%, no regressions, no critical issues.

### Unified Operational Task Engine (Feb 19 2026 — Phase 1 SHIPPED)
- **Architecture blueprint**: `/app/memory/TASK_ENGINE_ARCHITECTURE.md` — full event-driven design (TaskTemplate → Task → TaskCompletion → TaskEvent), 17 sections, approved by user.
- **Backend module** `/app/backend/task_engine.py` — single self-contained module included into the existing `api_router`. No `server.py` big-bang refactor (deferred until Phase 2 scope grows).
- **Models**: 4 Mongo collections — `task_templates`, `tasks`, `task_completions`, `task_events`. All carry `tenant_id` (default="default", single-tenant for now, forward-compat).
- **Categories**: feed · medication · turnout_out · turnout_in · stall_clean · farrier · vet · rehab · custom — one polymorphic engine; typed `payload` per category.
- **Recurrence**: RFC 5545 RRULE internally (`python-dateutil`), 14-day rolling materialization horizon, materializer loop every 15 min.
- **Lifecycle**: scheduled → due → overdue → in_progress → completed/skipped/cancelled. Skipped vs refused are distinct outcomes preserved on the immutable completion record.
- **Offline-first**: idempotent `client_completion_id` on completion endpoint; concurrent completion appends note to canonical and voids the duplicate; soft-void preserves audit trail.
- **Event fan-out**: All side effects flow through `TaskEvent` — never inline in routes (enforced anti-pattern).
- **Owner visibility layer**: horse_owner role only sees curated `task.completed` events in categories {medication, farrier, vet, rehab, feed} — stall_clean / turnout-only events filtered out.
- **API endpoints** (all under `/api`): `task-templates` (GET/POST/PATCH/DELETE soft), `tasks` (GET filtered, GET /today, POST ad-hoc, PATCH), `tasks/{id}/complete` · `/skip` · `/void` · `/reassign`, `tasks/bulk-complete`, `tasks/materialize`, `tasks/analytics/summary`, `horses/{id}/timeline`, `staff/{id}/activity`.
- **Seed**: 9 demo templates auto-seeded on first boot (AM/PM grain, daily bute, AM turnout + PM bring-in, daily stall pick, 6-week farrier RRULE, one-off spring vaccines, twice-daily rehab hand-walk). Materializer creates ~117 occurrences across the 14-day horizon.
- **Frontend**: new mobile-first **"Today" page** at `/today` (added to sidebar nav). 6 urgency-ordered groups (overdue_critical, due_now, upcoming_next_4h, later_today, completed_today, informational). Swipe-right-to-complete + swipe-left-to-skip on touch; large 44px tap-target buttons on desktop; bulk-select mode with shared note; category filter chips; per-task sync dots (synced/queued/syncing/retry/failed) plus header sync badge with manual "Retry now" affordance when failures surface.
- **Offline queue** `/app/frontend/src/lib/taskSync.js`: localStorage-backed, exponential backoff (1s, 5s, 15s, 60s, 5m, 30m), auto-drains on `online` event, optimistic UI, idempotent on server.
- **Tests**: 13/13 task engine pytest tests PASS (`/app/backend/tests/test_task_engine.py`). Pre-existing 77 tests still passing (3 pre-existing failures in `test_feed_complete` / CSV-commit owners-horses are accumulated-state dedup, not regressions).
- **Testing agent verdict** (iteration_7): backend 100%, frontend 100%, no regressions, two non-blocking suggestions; one (manual Retry-now button) implemented immediately.

### Onboarding / Barn Setup Workflow (Feb 17–19 2026 — added)
- 10-step guided wizard at `/onboarding` with sticky stepper, autosave, resume-where-you-left-off, percent progress
- Steps: Barn Profile · Locations · Owners · Horses · Riders · Feed Templates · Inventory · Staff Invites · Recurring Schedules · Review & Launch
- CSV bulk import for **owners** and **horses**: drag-drop + paste + downloadable template + preview with duplicate detection + commit with server-side dedupe
- Backend models/endpoints: `/barn` (settings), `/locations`, `/feed-templates`, `/inventory` (with low_stock flag), `/recurring-schedules`, `/onboarding/{steps,progress,complete,reset,csv-preview,csv-commit,csv-template}`
- Role gating: only `admin` / `barn_manager` can edit barn-level settings or invite staff

### Design System v3 — Soft Lavender Pearl + Charcoal Navy (Feb 19 2026)
- **Full palette pivot** from dark saddle/brass to **light lavender pearl** with deep charcoal navy as sidebar / primary brand
- New tokens (Tailwind + CSS vars):
  - **Surfaces**: bg `#F7F5FA` (lavender ivory), surface `#EAE7F2` (lavender mist), card `#FDFBFF` (pearl), elevated `#FFFFFF`
  - **Ink**: primary `#2A2A32`, muted `#666674`, soft `#9A98A8`
  - **Brand**: navy `#2E3448`, navyDeep `#22262F`, navyLift `#3D445A`
  - **Accents**: brass→**icy blue** `#A7B7E7` / `#C2CDEC`, saddle→**dusty lavender** `#C7B6D9` / `#A593C0`, champagne taupe `#B89B7A`, brushed silver `#B8BDC9`
  - **Status**: sage `#7AA08A`, golden sand `#B5894A`, mauve `#8B5E6B`
- Sidebar stays deep navy with icy-blue active rail; main content is pearl + lavender; FAB is icy-blue gradient
- Dark-mode CSS-var scaffolding ready for future toggle
- Tests: 100% pass, zero regressions across 14 routes

### Magic-Link Invites + Email Layer (Feb 19 2026)
- **Resend integration** (`mailer.py` abstraction) — **LIVE** with real API key as of Feb 19 2026.
- Sandbox handling: when Resend rejects non-owner recipients, mailer returns `status='sandbox'`, dev_accept_url surfaced in UI for manual share until domain is verified
- Branded HTML email templates: `_base.html` + `onboarding_invite.html` + `onboarding_nudge.html` (luxury aesthetic)
- Endpoints: `POST /invites`, `/invites/{id}/resend`, `/invites/{id}/revoke`, `GET /invites/verify`, `POST /invites/accept`
- Tokens: sha256-hashed at rest, single-use, 7-day TTL
- AcceptInvite page `/accept-invite?token=...` with password set, auto-launches onboarding for `admin`/`barn_manager`
- `APP_BASE_URL` env-driven with request-origin fallback

### Setup Health Reports + Nudge Automation (Feb 19 2026 — added)
- **`/reports` page** (admin/barn_manager only): 5 KPI cards (setups in progress, completed, completion rate, median time-to-launch, invite acceptance), 10-step funnel chart with status segmentation, invitation pipeline (total/accepted/pending/revoked/expired), low-acceptance amber coaching banner
- **Manual nudge trigger** `POST /admin/send-nudges` with configurable `min_days`/`cooldown_hours` (cooldown only persists on successful send), candidate list preview, "Send reminders" button
- **Daily automated scheduler** — asyncio task on backend startup runs every 24h after 6h warmup, controlled by `DISABLE_AUTO_NUDGES` env var
- Branded nudge email template with personalised "Pick up where you left off — X% done, next step: Y" copy
- Endpoints: `GET /reports/setup-health`, `GET /reports/nudge-candidates?min_days=N`, `POST /admin/send-nudges`
- Analytics events: `onboarding.nudge_sent`, `admin.nudges_run` (with auto/manual trigger metadata)
- Tests: 12/12 PASS (in addition to prior 75 passing tests)

### Polish + Analytics (Feb 19 2026)
- Native `<select>` replaced with **shadcn Select** in all onboarding form controls
- **Deep-merge** for `progress.data` (sibling keys in nested dicts preserved)
- **Tenant-level reset** endpoint `/admin/tenant-reset` (admin-only, requires confirm="RESET", scopes: onboarding | all_setup_data)
- **Settings page** exposes `Re-open setup` (per-user) and tenant-reset controls (admin only)
- **Dashboard checklist widget** — 10-tile detailed setup status grid with click-to-step navigation, replaces simple progress bar
- **Analytics events**: `POST /events` + `GET /events/onboarding-funnel` (admin) + frontend `track()` helper; events fire on step_completed, step_skipped, completed, invite_sent, invite_resent, invite_revoked, invite_accepted, csv_imported, tenant.reset

### Testing (Feb 19 2026)
- Backend: **20/20** invite/analytics/tenant-reset tests PASS (in addition to prior 35 passing onboarding+core tests)
- Frontend: 100% — all checklists, shadcn Select, accept-invite redirect, dev-link banner, tenant-reset UI verified by testing agent


### Backend (/app/backend/server.py)
- JWT auth: `/api/auth/register`, `/api/auth/login`, `/api/auth/me`
- CRUD endpoints: horses, owners, riders, medications, medication-logs, feed-tasks, vet-records, injuries, wellness, lessons, training, invoices, messages, service-requests, incidents
- Aggregates: `/api/dashboard/summary`, `/api/dashboard/barn-board` (Mongo-optimized with filters + projections)
- AI: `/api/ai/generate` (wellness_insight, training_summary, owner_update kinds)
- Seed: `/api/seed` (idempotent, no auth) — auto-runs on startup if empty
- Demo seeds: 5 demo users, 6 horses, 3 owners, 3 riders, 18 feed tasks (today), medications + logs, vet records, injuries, wellness, lessons, training, invoices, messages, service requests, incidents

### Frontend (/app/frontend/src/)
- AuthContext with JWT in `localStorage('equine_token')`, axios interceptor
- AppShell + Sidebar (23 nav items, lucide line-art icons, role-based user card)
- Login page with cinematic arena background and 5 demo accounts
- Dashboard: 5 stat cards + 6 widget cards (Feed, Lessons, Weather, Alerts, Wellness pulse)
- Today's Barn Board: tablet-optimised large cards for Feed, Medications, Lessons, Stall Rest, Incidents + Weather strip + quick-complete buttons
- Horses: roster grid with status pills + detail page with 9 tabs (Overview, Feed, Training, Health, Injuries, Medications, Wellness, Billing, Owner) + Claude-powered AI insights (Wellness / Training / Owner Update)
- Medications: today's doses + active prescriptions
- Health & Vet: vaccine/dental/Coggins/exam records + injury timeline with status pills
- Feed Room: morning/midday/evening grouping with sign-off
- Lessons: schedule + rider roster
- Training: daily ride log with ratings/homework
- Owner Portal: service request form + approval flow
- Billing: invoice list with pay action + revenue totals
- Messaging: send form with visibility controls + inbox
- Incidents: timeline view
- Owners, Riders, Settings: list/detail views
- Placeholders: Stall Rest, Turnout, Inventory, Shows, Documents, Maintenance, Staff, Reports

### Testing
- Backend: 20/20 pytest tests passing (auth, all CRUD, dashboard, AI generate)
- Frontend: Login + navigation verified e2e; Dashboard + Horses rendered correctly in screenshot
- Deployment health check: **PASS** ✅ (no blockers, no warnings)

## Deferred to Next Iteration (P1/P2)
- Object storage uploads for photos/documents (currently Unsplash placeholders)
- Stall Rest & Rehab dedicated workspace (hand-walking, icing, rehab log)
- Turnout & Pastures (herd compatibility, mud, rotation)
- Inventory with reorder alerts
- Shows & Competitions calendar with entries/stabling/packing
- Document vault with secure uploads
- Maintenance tickets (fences, gates, waterers, arenas)
- Staff management (workloads, shifts, certifications)
- Reports dashboard (profitability by horse/owner/service)
- QR codes for stalls/horses
- Real-time push notifications
- Mobile PWA install

## Next Tasks (priority order)
1. **Complete server.py refactor (Phase-F continued)** — extract `routes/onboarding.py` (barn + locations + feed_templates + inventory + recurring_schedules + staff_invites + CSV preview/commit) and optional `routes/tasks.py`. Target server.py < 700 lines.
2. **Phase-E — Rehab & Turnout** as filtered views over the unified Task Engine (no parallel systems): /rehab and /turnout pages pull `/api/tasks?category=rehab|turnout_out|turnout_in` with specialized completion payloads.
3. **AI Wellness Pulse** — Claude Sonnet 4.5 over the engine timeline (skipped-X-times-this-week kind of nudges) using Emergent LLM key.
4. **Object storage** — Cloudflare R2 photo/document uploads for horses, completions, vet visits (storage.py scaffold already in place).
5. **Frontend complexity reduction** — Today.jsx / Dashboard.jsx / Onboarding.jsx incremental sub-component extraction. Owner portal request-status filter chips. Pull-to-refresh.
6. **Notifications follow-on** — promote dispatcher to MongoDB change-streams or Redis Streams; add web-push channel; richer email digest formatting.
7. **API hygiene** — `POST /api/tasks` should accept legacy `horse_id` alias or 422-reject naive callers who omit `linked_horse_ids`.
8. **Inventory module** with low-stock alerts.
9. **Dark mode toggle** (CSS-var scaffolding already in place).
10. **Shows & Competitions** module, **Reports / BI dashboard** with charts.
