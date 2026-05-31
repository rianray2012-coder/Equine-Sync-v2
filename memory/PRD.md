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


## 🆕 Governance & Production-Readiness Program (May 30 2026)
The founder-beta "freeze" was lifted. The user supplied a full **23-document governance set** that reframes EquineSync as a phased production-readiness program. **The authoritative source of truth is now `/app/docs/` (project-root `/docs`)** — start at `/app/docs/MASTER_INDEX.md`. The `/app/memory/*` files are retained as historical founder-beta artifacts.

**10-Phase Execution Plan** (`/app/docs/PHASED_EXECUTION_PLAN.md`): 1) Docs & Governance ✅ → 2) Security Stabilization → 3) Backend Modularization → 4) Multi-Tenancy & Permissions → 5) Audit Logging → 6) Care Workflows → 7) Owner Trust Layer → 8) Mobile → 9) Billing → 10) Production Readiness.

**Authoritative palette (Brand Guide 22):** Midnight Graphite `#232734` / Slate Navy `#2E3550` / Frost White `#F7F8FA` / Smoky Lilac `#B8AECF`; Cormorant Garamond (display) + Inter (UI); identity line "Every Horse. Every Task. In Sync." Supersedes the deprecated Warm Ivory/Saddle Brown design-token palette.

### Phase 1 — Documentation & Governance ✅ (May 30 2026)
Documentation-only pass; **zero runtime changes** (services never restarted).
- Created `/app/docs/` with all 23 governance docs + `assets/brand/equinesync-icon.png`.
- Reconciled `DESIGN_TOKENS.md` to Brand Guide 22 (deprecated warm palette).
- Authored a **code-grounded `KNOWN_TECH_DEBT.md`** (15 items, file/line-referenced). Top criticals: `JWT_SECRET='change-me'` fallback (`server.py:70`, `auth.py:31`); `barn_id` absent platform-wide (only in `invites.py`); no centralized permission service; hard-deletes in `onboarding.py`; no `AuditLog`; no rate limiting; non-standard API responses.
- Logged key decisions in `DECISION_LOG.md`.

### Phase 2A — JWT Hardening & Centralized Config ✅ (May 30 2026)
Closed the Critical JWT-fallback debt. Scoped narrowly (no password reset / email / rate-limiting yet).
- New `backend/config.py` = single source of truth; removed `JWT_SECRET='change-me'` fallback from `server.py` + `routes/auth.py`.
- `validate_config()` at startup: **fails fast in production** if `JWT_SECRET`/`MONGO_URL`/`DB_NAME` missing or `JWT_SECRET` insecure; **dev** uses logged ephemeral secret. Added `APP_ENV` toggle to `.env`.
- Tests: `backend/tests/test_config.py` (18 unit tests pass). Verified login + `/auth/me` + 20 `test_phase2.py` integration tests pass — no regression.
- **Next:** Phase 2B (password reset + email verification via Resend `RESEND_API_KEY`), then 2C (rate limiting + CORS tightening), 2D (auth/permission test coverage). Awaiting user go-ahead per "one sub-phase at a time" directive.

### Phase 2B — Auth Rate Limiting & CORS Tightening ✅ (May 30 2026)
Scoped to rate limiting + CORS only (no password reset/email).
- New `backend/rate_limit.py`: IP-based limiter on `/api/auth/login|register|refresh` via a FastAPI dependency (`limits` library). Env-driven: `5/minute` prod, `1000/minute` dev; toggle `RATE_LIMIT_ENABLED`, override `AUTH_RATE_LIMIT`.
- CORS hardened: `config.get_cors_origins()` rejects `*`/empty in **production** (validated at startup); dev still defaults to `*`.
- Switched from slowapi (decorator broke Pydantic bodies → 422) to `limits` dependency; removed unused `slowapi` dep.
- Tests: `tests/test_rate_limit.py` + CORS/rate-limit cases in `tests/test_config.py`. **Full suite: 211 passed, 1 skipped.** E2E proof: real login throttled (200×4 → 429) under a temporary strict limit, then reverted.
- **Next:** Phase 2C (password reset + email verification via Resend `RESEND_API_KEY`), then 2D (brute-force lockout + auth/permission test coverage).

### Phase 2C — Password Reset, Email Verification & Health Probe ✅ (May 30 2026)
- New `backend/auth_tokens.py`: hashed, single-use, expiring tokens (`auth_tokens` collection) for password reset + email verification.
- New endpoints: `/api/auth/forgot-password`, `/reset-password`, `/verify-email`, `/resend-verification` (rate-limited; uniform no-enumeration responses; dev-only `dev_token` when non-production).
- `email_verified` added to `User`; **safe startup backfill** set 63 existing users → `true` (no lockout); login enforcement gated behind `ENFORCE_EMAIL_VERIFICATION` (default off).
- Reused `mailer.py` + Resend; added `_base_auth.html`, `password_reset.html`, `verify_email.html` templates (`render()`/`send()` gained a `base` param).
- New `GET /api/health` readiness probe (DB + config booleans, no secrets).
- Tests: `tests/test_auth_tokens.py` (unit, incl. expiry/single-use/invalid) + `tests/test_phase2c_auth.py` (HTTP). **Full suite: 227 passed, 1 skipped.**
- **Next:** Phase 2D (account-level brute-force lockout via MongoDB `login_attempts` + expanded auth/permission tests). Follow-up: frontend pages for `/reset-password` + `/verify-email` links.

### Phase 2D — Brute-Force Lockout + Reset/Verify Frontend Pages ✅ (May 30 2026)
**Phase 2 (Security Stabilization) is now COMPLETE.**
- New `backend/login_attempts.py`: per-account lockout (`login_attempts` collection). After `LOGIN_MAX_ATTEMPTS` (default 5) failures in a window, login returns **423** for `LOGIN_LOCKOUT_MINUTES`; success clears the counter. Env-driven; enabled by default.
- Frontend (**Brand Guide 22**): new `pages/ResetPassword.jsx` (`/reset-password`, token from URL → set new password) + `pages/VerifyEmail.jsx` (`/verify-email`, auto-verify + resend), public routes in `App.js`, Cormorant Garamond + Inter weights in `index.html`, and a minimal "Forgot password?" inline flow on `Login.jsx`.
- Lockout-safety: success clears the counter; threshold 5 sits above the suite's two single-failure admin tests; verified admin still logs in.
- Tests: `tests/test_login_lockout.py` (unit + HTTP). **Full backend suite: 235 passed, 1 skipped.** Frontend verified via screenshots (verify success, reset success, Login forgot panel). Frontend lint clean.
- **Phase 2 complete.** Next major step: **Phase 3 — Backend Modularization** (move `config.py`/`auth_tokens.py`/etc. into `core/`, split `server.py`). Deferred P1: localStorage→httpOnly cookie auth migration.

### Phase 3A — Core Package ✅ (May 30 2026)
First step of Phase 3 (see `docs/PHASE3_MODULARIZATION_MAP.md`). Planning + safe move only; `server.py` not yet split.
- Created `backend/core/` and `git mv`'d `config.py`, `rate_limit.py`, `auth_tokens.py`, `login_attempts.py` into it (history preserved). Updated all 6 importers; internal `core.rate_limit`→`core.config`.
- `/api/health` gained a non-breaking `version` field.
- Authored `docs/PHASE3_MODULARIZATION_MAP.md`: dependency graph, route-group inventory, and the 3A→3G extraction order.
- Tests: 51 core tests pass; **full suite 235 passed, 1 skipped** (no regressions). Health 200, login 200.
- **Next (server.py extraction order):** 3B system/admin/analytics → 3C horses → 3D care/tasks → 3E owner/reports → 3F billing → 3G app-assembly (JWT helpers + bootstrap → `core`).

## What's Been Implemented (Feb 17 2026)

### Operational Hardening — Batch C (Notification trust loop) + Inventory duplicate-detection opener + Dispatcher retry (Feb 20 2026)
Final batch of the Founder-Beta Operational Hardening track. No new feature surface. Closes the §5.3 owner-approval latency gap (4-12 hour median) and the §3.4 inventory fragmentation gap surfaced in OPERATIONAL_SIMULATION.md.

**Inventory duplicate-detection (SoftWarning opener):**
- `/inventory` Add sheet now soft-warns when proposed `name + category` already exists in the items list (case-insensitive name match, strict category match).
- Copy: _"A similar inventory item ('Triple Crown') already exists in grain. You can still add this one — or close and edit the existing row instead."_
- Calm-tone audit verified: no "Duplicate", "Conflict", "Warning:". Submit always remains enabled — never blocks.
- Evolves SoftWarning from "scheduling-conflict awareness" → broader "gentle operational awareness" primitive.

**Notification drawer trust loop (Batch C main):**
- `NotificationsBell.jsx` rewritten — adds a top-of-drawer "Pending requests" section visible ONLY to deciders (`role ∈ {admin, barn_manager, trainer}`). Non-deciders (owners, grooms) see the drawer unchanged.
- Each pending row → one-tap **Approve** + **Decline** buttons. Approve: POST `/api/service-requests/<id>/approve`, calm toast "Approved.". Decline: inline composer expansion (NOT a separate modal) with optional reason textarea + Cancel + Send. POST `/api/service-requests/<id>/decline`, toast "Declined with a note." (empty reason tolerated — backend falls back to default).
- Single-composer-at-a-time semantics: `declineFor` is a single id, so opening composer B auto-collapses composer A.
- Calm-tone audit verified: button labels are "Approve" / "Decline" ONLY — no "Reject", "Deny", "Refuse". Eyebrow is "Pending requests" — no "Action Required" or "Urgent".
- Badge formula: `totalUnread = data.unread + pending.length` (visually capped at "9+"). Decreases immediately after each action via `refresh()`.
- Polls `/api/service-requests` every 30s (only when `canDecide`) alongside the existing `/api/notifications` poll.
- Saves owners the 4-12 hour navigate-to-portal hop documented in simulation §5.3.

**Dispatcher transient-error retry (notifications.py):**
- `drain_once()` now tracks `dispatch_attempts` per task_event. On exception: increment + leave `dispatched_at` unset so the next poll picks the event up again. Only after `MAX_DISPATCH_ATTEMPTS=3` does the loop finalise the event as `dispatched_channels=['error']`.
- Eliminates the permanent-drop behaviour where a momentary DB hiccup or email-provider blip silently lost an in-app notification.
- New `/app/backend/tests/test_dispatch_retry.py` covers both branches (transient-then-cap + transient-then-success). 2 new tests, pure `asyncio.run` + monkey-patching — no pytest-asyncio dependency added.

**Verification (testing_agent_v3_fork iteration 23):**
- **16/16 Batch C + Inventory checks pass.** **175/175 backend pytest pass** (172 prior + 1 skip + 2 new dispatcher retry tests). Zero ui_bugs, integration_issues, design_issues.
- Role gating verified across admin/owner/groom logins. Approve, decline-with-reason, decline-cancel, decline-empty-reason, one-composer-at-a-time all green. Calm-tone audit: zero banned strings ("Reject", "Deny", "Refuse", "Duplicate", "Conflict", "Warning:") anywhere.



### Operational Hardening — Batch D (Soft scheduling conflicts) + Bulk Select-Group (Feb 20 2026)
Refinement of operational realism per OPERATIONAL_SIMULATION.md §3.1 and §3.3. No new feature surface. Strict adherence to founder direction: "supportive, not corrective — real barns intentionally overlap operations constantly. Help users notice, not enforce rigidity."

**Soft scheduling conflicts (Batch D):**
- New reusable `/app/frontend/src/components/SoftWarning.jsx` — calm slate informational note (NOT amber/red/yellow) with Info icon. Distinct from the existing error banner. Tone separation: supportive vs corrective.
- `QuickAddSheet.jsx` gained a new optional `renderWarnings(form, { prefix }) => ReactNode` prop, rendered between the error banner and the sticky footer. Backward-compatible — existing sheets unaffected.
- **`/lessons` Schedule lesson** now checks the proposed `start_time` against existing lessons within ±60 minutes for both the chosen rider AND the chosen horse (independent — both can fire). Each fires a SoftWarning with calm copy: _"<Rider/Horse name> already has a lesson scheduled nearby in time (May 17, 2026 2:00 PM)."_ NEVER blocks submission. NEVER uses the words "Conflict", "Warning", "Double-booking", or "Error".
- **`/training` Log session** now checks the proposed `date` against existing sessions for the chosen horse. Date-keyed (no time window). Copy: _"<Horse name> already has training logged for <date>."_ Also never blocks.
- `CONFLICT_WINDOW_MIN = 60` constant in Lessons.jsx for future tuning.

**Bulk Select-Group (simulation §3.1):**
- `/today` TodayGroup headers now render a tiny `Select all` / `All selected` chip ONLY when `bulkMode === true`. Operates on the group's already-filtered items prop, so the chip naturally respects the active filter chip. Reversible — second tap deselects all. Saves 6–8 taps per turnout round.
- New `selectGroup(groupKey, items, makeSelected)` callback in Today.jsx uses functional setSelected (race-safe under rapid taps).

**Verification (testing_agent_v3_fork iteration 22):**
- **13/13 Batch D checks pass.** Zero ui_bugs, zero integration_issues, zero design_issues.
- Rider + horse conflict warnings render with the exact expected calm copy; clear when start_time moves >±60 min away; submit always remained enabled in every test.
- Calm-tone audit verified: no banned strings ("Conflict", "Warning:", "Error", "Double-booking") in any warning text. SoftWarning class confirmed slate (`bg-equine-soft/40 border-equine-graphite/40 text-equine-silver`) — NOT amber.
- Select-all chip: hidden in non-bulk mode (count=0), visible per non-empty group in bulk mode (5 chips on demo data), bulk-action-bar count matched items.length, reversible toggle confirmed, filter-respect automatic via upstream-filtered items prop.



### Operational Hardening — Batch F (Thumb-zone polish) + Dashboard LastSyncedBadge (Feb 20 2026)
Refinement pass per the OPERATIONAL_SIMULATION.md findings. No new feature surface. Focus on one-handed reachability, interruption recovery, and stale-state trust.

**Today filter persistence (highest-leverage F item, simulation §4.2):**
- `/today` `filter` state initialized from `sessionStorage["equine_today_filter"]` via lazy `useState` init.
- `useEffect` writes the filter on every change; cleared on "All".
- Phone-lock / app-remount mid-feed-round no longer wipes Sophia's filter.

**Tap-zone bumps:**
- Today filter chips + bulk-mode-toggle: `px-3 py-1.5` → `px-4 py-2.5 min-h-[40px]` (measured 40px tall — comfortable one-thumb hit).
- HorseProfile tabs: `py-2` → `py-3` + `tap-44` + `whitespace-nowrap` (measured 45.5px tall).

**HorseProfile tab strip ergonomics:**
- Wrapped the scrollable strip in a `relative` container with two `pointer-events-none md:hidden` gradient overlays on the left + right edges. Subtle horizontal-scroll affordance without visual noise on desktop.

**FAB / modal safety:**
- FAB `z-30`, QuickAddSheet `z-60` — sheet always covers FAB cleanly when open.
- QuickAddSheet sticky footer (Cancel + Save) verified within mobile viewport on 390x844 (submit button bottom = 839 of 844 — no scroll required).

**Dashboard LastSyncedBadge extension (simulation §7):**
- `Dashboard.jsx` now uses a unified `loadAll()` callback (Promise.allSettled across 4 endpoints) so the badge can trigger a parallel refetch.
- `LastSyncedBadge` gained two new props:
  - `verb` — `"Synced"` (default, used on /today) or `"Updated"` (used on /dashboard) so the Dashboard reads "Updated just now / 2m ago" per user direction.
  - `tone` — `"primary"` (Today: bordered pill) or `"secondary"` (Dashboard: smaller, borderless, uppercase tracking — visually subordinate, informational only, no anxious red/yellow).

**Verification (testing_agent_v3_fork iteration 21):**
- **9/9 Batch F + Dashboard checks pass.** Zero ui_bugs, zero integration_issues, zero design_issues.
- All filter chips + bulk toggle measured 40px tall; all HorseProfile tabs 45.5px.
- Dashboard badge `text='UPDATED JUST NOW'`, tap fires 4 parallel refetches verified via request listener.
- Today filter persistence verified across full page reload.



### Operational Hardening Sprint — Batches A + B + E (Feb 20 2026)
Pure refinement sprint after the CRUD sprint. No new feature surface. Focus on: interruption recovery, trust under poor signal, aisle-side usability, calm error recovery, real-barn-day survivability.

**Batch A — QuickAddSheet hardening:**
- **Auto-focus** lands on the first focusable element (input / textarea / Radix Select trigger) ~320ms after open via `formRef.querySelector('input,textarea,button[role="combobox"]')`. Works for sheets whose first field is a Select (e.g. Incidents starting on `type`).
- **Enter-to-submit** via native `<form onSubmit>` (textareas excluded by browser default).
- **Smart defaults** wired through new `initialValues` prop:
  - `/incidents` → `occurred_at = now` (datetime-local) + `severity = "moderate"`
  - `/lessons` → `start_time = next half-hour` + `duration_min = 60`
  - `/training` → `date = today` (YYYY-MM-DD)
- **Draft preservation** via `sessionStorage["equine_draft_<endpoint>"]` — debounced save on form change, silent restore on reopen (no banner, no toast — matches founder direction "subtle, automatic, calm"), cleared after a successful POST.
- **Defensive Radix Select guard**: ignores `onValueChange("")` events fired by Radix during its first 600ms of mount (these would otherwise clobber the smart-default). Tracked via `openedAtRef.current` timestamp.
- **shallowEqual gate** on `initialValues` prevents parent re-renders with a new object literal from blowing away in-progress user input.
- **Sticky footer** (Cancel + Save) at the bottom of the sheet so the primary action stays above the fold on tall forms (Incidents on iPhone SE class viewports).

**Batch B — Operational error recovery:**
- POST failure → sheet STAYS OPEN with form intact, calm inline message in `data-testid="<prefix>-error"` reading either the backend's `detail` or the fallback "Saved as draft — try again when you have signal." Toast is no longer the only failure surface.
- New `/app/frontend/src/components/today/LastSyncedBadge.jsx` — quietly dependable "Synced just now / N min ago / HH:mm" pill rendered next to the existing `SyncHeaderBadge` on the Today page. Tap to manually refresh (`onRefresh = reload`). Auto-rerenders every 30s for accurate relative time. Strictly no alarming connectivity banners.

**Batch E — Operational Simulation report:**
- New artifact `/app/memory/OPERATIONAL_SIMULATION.md` (~280 lines) — a movement audit not a feature audit. Walks through a real Monday barn-day across Sophia (groom), Marcus (trainer), Eleanor (admin), Charlotte (owner). Includes tap counts per persona per surface, interruption-recovery scorecard, scheduling realism audit, speed-under-pressure analysis, owner-communication timing, phone-in-one-hand usability matrix, stale-state risk map, list of places staff still revert to texting/paper, founder-barn prep checklist, and the post-batches mobile hardening roadmap (Waves 1-7).
- Document serves as product refinement guide, founder-barn prep guide, and mobile hardening roadmap as requested by user.

**Verification (testing_agent_v3_fork iterations 19 → 20):**
- Backend: unchanged (165 pytest still green from iter17).
- Frontend iter19 caught two HIGH bugs (auto-focus on non-focusable div + severity default clobbered by Radix mount onValueChange) — both fixed in iter20.
- Frontend iter20: **8/8 hardening checks pass**. Auto-focus correct, smart defaults applied, draft preservation + restore + clear-on-success verified, inline error path works under simulated POST 500, Enter-to-submit closes sheet on success, LastSyncedBadge renders and refreshes on tap.



### Founder-Beta CRUD Sprint (Feb 20 2026 — operational continuity release)
After the Trust Tightening subtraction sprint, the audit's seven critical workflow gaps were closed. Real barns can now operate on day 2 without re-running onboarding.

**New surfaces:**
- **`/inventory` page materialized** (was Placeholder). Calm category-grouped list, low-stock badge per item + header chip when any item is below `reorder_at`, delete-per-item, add via QuickAddSheet. Wires the existing fully-working backend `/api/inventory` CRUD + low-stock detection.
- **`/owners` Add owner** — quick-add modal posts to `/api/owners` (full_name + email + phone).
- **`/riders` Add rider** — full_name + age + skill_level select + goals + emergency contact.
- **`/horses` Add horse** — full HorseIn shape with status select (active / stall_rest / rehab / retired). Empty-state CTA + 'Add horse' header button. Photo-less horses render a calm initial avatar.
- **`/incidents` Report incident** — type + severity + horse association (optional, '__none__' sentinel coerced to null) + occurred_at datetime + description + follow-up. Calm Empty state copy ("A clean record is a good thing").
- **`/lessons` Schedule lesson** — rider (required) + horse (optional) + start_time datetime-local converted to ISO + duration + focus. Add button disabled until at least one rider exists.
- **`/training` Log session** — horse (required) + date + discipline + exercises + notes + rating + homework. Add button disabled until at least one horse exists.

**Reusable primitive — `/app/frontend/src/components/QuickAddSheet.jsx`:**
- Right-side slide-in sheet (max-w-md), backdrop click + ESC close, sticky header w/ eyebrow + title, Cancel + Submit buttons, Field/Select primitives reused from onboarding so the visual vocabulary matches Setup Concierge exactly.
- Supports `text / number / date / datetime-local / email` input types + `kind: 'select' | 'textarea'`. `full: true` per-field for full-width.
- **Defensive Radix-Select guard**: any option with `v === '' | undefined | null` is silently filtered. Callers must use a non-empty sentinel (e.g. `'__none__'`) and coerce it in their `transform()` before POST.

**Backend changes (`/app/backend/routes/operations.py`):**
- `POST /api/lessons`, `POST /api/training`, `POST /api/incidents` now resolve denormalised display names (`rider_name`, `horse_name`, `trainer_name`) server-side. Missing references are tolerated (`name=null`) so existing tests with ghost ids still pass.
- `POST /api/incidents` defaults `status: 'open'` so the safety log doesn't depend on the caller setting it.

**Recurring Schedules — hidden (audit §J.6):**
- Frontend `Onboarding.jsx` filters the `'schedules'` step from the visible stepper. Backend `/api/onboarding/steps` STILL returns all 10 steps and the `recurring_schedules` collection + CRUD endpoints + model remain intact (data preserved for v1.1 when the materializer is wired). Percent calculation now derives from visible steps only, so the wizard can reach 100%.

**Verification (testing_agent_v3_fork iteration_17 + iteration_18):**
- Backend: 165/165 pytest pass (145 + 20 invites/analytics) + 8 new sprint regressions for name resolution and missing-ref tolerance.
- Frontend: 12/12 CRUD flows green. Two critical Radix Select empty-string crashes (`/incidents`, `/lessons`) were caught in iter17 and fixed via sentinel + defensive filter in iter18.
- Zero regressions on Today / Dashboard / Owner Portal / Horse Profile.
- Audit gaps closed: Critical #1 (owners/riders add), #2 (inventory), #3 (schedules hidden), #6 (lessons + training add), #7 (incidents add). Plus the audit's recommended Add-Horse button (Option D).



### Founder-Beta Trust Tightening Sprint (Feb 20 2026 — subtraction-only release)
A deliberate **pure-subtraction release** to reduce fake/demo trust risks before founder-barn onboarding. The release should feel **calmer, tighter, more trustworthy** — never smaller or less capable.

**Deletes:**
- **Weather card** — hardcoded `temp_f:58, "Light Rain"` removed from Dashboard. `WeatherCard` export removed from `SmallCards.jsx`. `weather` key stripped from `/api/dashboard/barn-board` response. Daily Care grid drops 3-col → 2-col (OperationsCard + UpcomingCareCard).
- **HorseProfile speculative AI buttons** — `Wellness Insight`, `Training Summary`, `Owner Update` buttons + the entire AI Insight card removed. `/horses/{id}` still renders profile + 10 tabs + Curated Timeline + all care drill-downs.
- **`/api/ai/generate` endpoint** — handler, `AIRequest` model, and `emergentintegrations` LLM call all deleted. Returns 404. Wellness Pulse remains the calm rule-based observational layer.
- **Sidebar nav cleanup** — removed `/shows`, `/documents`, `/maintenance`, `/staff` items. Lucide icons `Trophy`, `FileText`, `Wrench`, `ClipboardList` removed. Operations section now contains only Inventory + Incidents; Program section contains only Riders + Lessons + Training.

**Redirects** (so legacy bookmarks never 404 or render Placeholder UI):
- `/shows` → `/`
- `/documents` → `/horses`
- `/maintenance` → `/incidents`
- `/staff` → `/settings` (folded into Settings → Team direction)

**`/inventory`** is **intentionally still on Placeholder** — it's Critical #2 of the post-sprint founder-beta-readiness list, scheduled separately.

**Test updates:**
- `test_dashboard_barn_board` now asserts NO `weather` key.
- `test_ai_generate_owner_update` REPLACED by `test_ai_generate_endpoint_is_gone` asserting 404.

**Verification (testing_agent_v3_fork iteration_16):**
- Backend: 100% (19/19 + 1 legacy skip).
- Frontend: 100% (all 18 surviving routes + redirects + dashboard + horse-profile assertions passed).
- Zero leftover dead imports verified by code review (`Sidebar.jsx`, `SmallCards.jsx`, `Dashboard.jsx`, `HorseProfile.jsx` all clean).
- Zero `/ai/generate` or `AIRequest` references remain in the codebase.
- Founder Walkthrough still references only surviving surfaces (Today, Feed, Medications, Horses, Owner Portal).

### Phase-F COMPLETE — `routes/operations.py` extraction (Feb 20 2026)
- **`routes/operations.py`** (233 LOC) — final care-side lift-and-shift: lessons, training, invoices, messages, service-requests (with role-gated `/approve` + `/decline` + 409 state guards), incidents. Eight Pydantic models migrated alongside their handlers.
- **`server.py` is now 836 lines** — **cumulative 57% reduction** since Phase-F began (1949 → 836).
- **Tests**: full suite **152/152 + 1 skipped + 13/13 new `tests/test_operations_routes.py`** regression assertions (lessons, training, invoices /pay, messages stamping, service-request happy/409/403/404 paths, incidents reported_by stamp). Zero regressions across every previous module.

### Founder Walkthrough — calm, read-only, narrated barn-day tour (Feb 20 2026)
- `/app/frontend/src/components/FounderWalkthrough.jsx` — 6-step modal: Today → Feed → Medications → Horse Timeline → Owner Digest → "you're ready". Two minutes max. Hospitality tone, never sales-y.
- **Read-only by design**: each step calls one GET (`/tasks/today`, `/dashboard/summary`, `/horses`) and surfaces 2–3 live stat tiles — **zero non-GET API calls** during the entire traversal (verified by testing agent network audit).
- **Auto-open guardrails**: admin/barn_manager only, gated on `onboarding.completed && !walkthroughSeen()`. Fires once, persists `equinesync.walkthrough.seen=1` in localStorage on finish. Manual "Founder tour" launcher (data-testid `walkthrough-launch`) remains in the Dashboard header for re-opens.
- **Close paths**: Escape, backdrop click, X button, "I've got it" — all verified.
- **Tone matches spec**: calm hospitality, never alarming, never pressuring; final step ends with *"We'll stay quiet from here. The Today view will be your home."*

### Phase-F final sweep — `routes/care.py` extraction (Feb 20 2026)
- **`routes/care.py`** (288 LOC) — every care record endpoint AND its Pydantic model lifted out of server.py together: horses, owners, riders, medications, medication-logs, feed-tasks, vet-records, farrier-history, injuries, wellness. Schemas unchanged; same dependency-injection pattern as the other route modules.
- **`server.py` 1221 → 994 lines** (this iteration ~18% reduction; ~**49% cumulative** since Phase-F began).
- Behaviour preserved: optional filters (`?horse_id` on meds/vet/farrier/injuries/wellness, `?date_str` on feed-tasks) untouched; the `POST /api/wellness` side-effect (heuristic bump of `horses.wellness_score`) verified live by the testing agent — all-5s payload sets the score to 100 as before.
- **Tests**: full pytest suite 141/141 + 1 skipped + new `tests/test_care_routes.py` 11/11 (auth gate, CRUD per resource, query-param filters, wellness score side-effect). Zero regressions.

### Setup Concierge & Onboarding reassurance copy (Feb 20 2026)
- Dashboard's `SetupConciergeCard.jsx` now ends with a calm, non-pressuring guidance block (data-testid `setup-guidance`): *"Many barns begin with Horses and Feed Templates, then expand from there. You can complete the remaining steps any time from Settings — nothing is locked or required to start operations."*
- `Onboarding.jsx` sticky sidebar adds a parallel reassurance note (data-testid `onboarding-reassurance`): *"Most barns revisit Inventory and Schedules after their first operational week. Nothing here is required to begin running daily care."*
- Both surfaces hide cleanly when onboarding completes (verified by testing agent — POST `/api/onboarding/complete` removes the card AND the guidance from the DOM). Tone matches the platform's emotional-trust direction: reassuring, achievable, never pressuring.

### Frontend complexity reduction — Dashboard.jsx + Onboarding.jsx (Feb 20 2026)
- **`Dashboard.jsx`**: 306 → 158 lines (**48%**). Extracted into `components/dashboard/`:
  - `SetupConciergeCard.jsx` — incomplete-onboarding tile grid (uses shared `STEP_META`).
  - `ActionTile.jsx` — the four high-density "Right Now" tiles.
  - `AlertsCard.jsx` — five-row attention list with tone variants.
  - `SmallCards.jsx` — `WeatherCard`, `OperationsCard`, **and a new engine-derived `UpcomingCareCard`** that lists the next vet/farrier/rehab visits from `/api/tasks?start=…&end=…` (filtered client-side, no new endpoint).
  - **Fake `WellnessPulseCard` with hard-coded 62/22/12/4 percentages DELETED** — exactly the "analytics clutter / dashboard inflation" the spec warned against.
- **`Onboarding.jsx`**: 764 → 211 lines (**72%**). State + stepper + content router only. Step bodies extracted into `components/onboarding/`:
  - `FormPrimitives.jsx` (Field + Select, shared by every step)
  - `BarnStep.jsx`, `CrudStep.jsx` (generic CRUD with `CRUD_CONFIG` for Locations/FeedTemplates/Inventory/Schedules), `RecordsStep.jsx` (Owners/Horses/Riders with CSV import), `StaffStep.jsx`, `ReviewStep.jsx`.
- **Shared single source of truth**: `lib/onboardingMeta.js` exports `STEP_META` used by both Dashboard's SetupConcierge and the Onboarding stepper.
- **Behaviour preserved**: every data-testid from the original Dashboard and Onboarding still resolves; autosave, skip/back/next/launch, CSV preview/commit, dev-link banner — all identical.

### `seed_pulse_demo.py` — demo-scoped pulse seeder (Feb 20 2026)
- Standalone CLI under `/app/backend/seed_pulse_demo.py` (NOT imported by `server.py`).
- **Three workflows**:
  - `python -m seed_pulse_demo` — dry-run preview.
  - `python -m seed_pulse_demo --apply --link-first-horse` — seed 5d of completed task_events (5 med + 2 rehab) tagged `demo_marker="pulse-demo-v1"` and temporarily link the first horse to the demo owner with `_demo_marker` tag.
  - `python -m seed_pulse_demo --apply --reset` — clean only (delete events + restore horse linkage).
  - `python -m seed_pulse_demo --apply --reset --link-first-horse` — clean + reseed in one command.
- **Isolation guarantees**: every write carries the demo marker so cleanup never touches other documents. Verified by testing agent.
- **Live-verified**: after seeding, `POST /api/notifications/digest/preview` as the demo owner returns the calm pulse line — testing agent observed "Valentino completed all scheduled rehab sessions this week." (medication path correctly silenced by an existing 24h med-skip preempt, falling through to rehab as designed).

### Wellness Pulse — quiet operational intelligence (Feb 20 2026)
- `/app/backend/wellness_pulse.py` (new) — **rule-based, pure-function** observational composer derived strictly from `task_events`.
- Discipline:
  - **One line maximum per horse** per pulse pass. Stays silent when nothing is confident enough.
  - Ordered priority: medication adherence → rehab follow-through → turnout steadiness.
  - Confidence thresholds (3 med / 2 rehab / 4 turnout completions in 7d) AND zero skips required.
  - Confidence-limited language — no scoring, predictions, medical interpretation, or speculative phrasing (`recommend`, `diagnose`, `predict`, `likely`, `concerning`, `abnormal` all explicitly forbidden by tests).
- Layered into the **existing daily digest** via `compose_horse_section(events_7d_all=...)`. Zero new endpoints, zero new toggles, zero analytics infrastructure. Try/except around the call means a pulse failure can never break the digest.
- **Tests**: 11/11 in `test_wellness_pulse.py` (priority order, silence on skip, confidence floors, no medical language, irrelevant categories ignored).

### Today.jsx complexity reduction (Feb 20 2026)
- Sub-components extracted with **zero behaviour changes** (every data-testid preserved):
  - `components/today/SyncBadges.jsx` (58 LOC) — `SyncDot` + `SyncHeaderBadge`.
  - `components/today/TaskCard.jsx` (151 LOC) — swipe-to-complete + bulk-mode card.
  - `components/today/TodayGroup.jsx` (62 LOC) — urgency band with collapse.
  - `lib/todayMeta.js` (38 LOC) — `CATEGORY_META`, `GROUP_META`, `GROUP_ORDER`.
- `Today.jsx` reduced **524 → 261 lines (50%)** and is now state + composition only. Optimistic overlay, periodic 60s refresh, and subscribeSyncState wiring remain in the parent.
- Verified by testing agent: every original testid present, swipe thresholds unchanged, filter chips + bulk action bar + sync badge all functioning identically.

### Phase-E — Rehab + Turnout filtered Engine views (Feb 20 2026)
- **No parallel scheduling**: both pages read the unified Task Engine through the existing `useEngineTasksToday` hook with category filters. Completions flow through the same offline-capable `taskSync` queue.
- `/app/frontend/src/pages/Rehab.jsx` (new) at `/stall-rest` — engine-backed `category=rehab`, calm summary, empty-state messaging, complete/skip via taskSync.
- `/app/frontend/src/pages/Turnout.jsx` (new) at `/turnout` — engine-backed `category∈{turnout_out, turnout_in}` with Turnout-out / Bring-in grouping (Sunrise / Sunset icons).
- Sidebar nav unchanged; placeholders replaced. `/rehab` aliased to `/stall-rest` for forward compatibility.

### Owner weekly recap — calm Sunday-evening update (Feb 20 2026)
- Layered onto the existing digest pipeline in `owner_digest.py` (no parallel reporting infrastructure):
  - Pure composition discipline — max 3 lines per horse, soft "rescheduled" framing for skipped meds (never "missed"), positive farrier/vet/rehab lines, optional "Looking ahead · N upcoming care appointments" tail block.
  - ISO-week idempotency via partial-filter Mongo index on `(owner_user_id, for_week)`.
  - Shares the single `digest_enabled` preference with the daily digest — one toggle governs both surfaces.
- **Endpoints**: `POST /api/notifications/weekly-recap/{preview,send-me}` (owner) + `POST /api/admin/weekly-recap/run-now` (admin/manager).
- **Scheduler**: Sunday 18:00 UTC (configurable via `OWNER_WEEKLY_RECAP_DOW` + `OWNER_WEEKLY_RECAP_HOUR_UTC`), gated by `DISABLE_OWNER_WEEKLY_RECAP`.
- **Frontend**: `OwnerDigestCard.jsx` now tabbed — `digest-tab-daily` + `digest-tab-weekly` (with `role="tablist"` + `aria-selected`), single Send-to-me-now button targets the active tab.
- **Tests**: 12/12 in `test_weekly_recap.py` (8 pure composition + 4 live API). Idempotency verified live — back-to-back admin run-now in the same ISO week returns identical `{sent:0, skipped:1}`.

### Phase-F — Incremental `server.py` Refactor (Feb 20 2026 — IN PROGRESS)
- **Goal**: reduce monolithic `server.py` toward the blueprint target (< 700 lines) without behavior changes. Strict no-rewrite policy — extractions only, with pytest gates between moves.
- **Extracted (this session)**:
  - `routes/dashboard.py` (113 LOC) — `/dashboard/summary` engine-derived + `/dashboard/barn-board` deprecated wrapper with RFC 8594 headers.
  - `routes/reports.py` (258 LOC) — `/reports/setup-health`, `/reports/nudge-candidates`, `/admin/send-nudges`. Helpers (`setup_health_payload`, `nudge_candidates`, `send_nudges`) exposed on the router so the startup scheduler reuses them without re-implementation.
  - `routes/invites.py` (290 LOC) — `/invites` CRUD + `/invites/verify` + `/invites/accept` with full dep-injection (mailer, base-url resolver, analytics tracker, jwt issuer, refresh-token, onboarding-steps constant).
  - `routes/onboarding.py` (466 LOC) — wizard state + barn + locations + feed templates + inventory + recurring schedules + staff invites + CSV preview/commit/template. `ONBOARDING_STEPS` is now the authoritative source here; server.py re-imports for invites/reports.
  - Auth gating + state-guard hardening on `/service-requests/{approve,decline}` (admin/barn_manager/trainer only; 409 on re-mutation).
- **Server.py size**: 1949 → 1221 lines (**~37% reduction**, behavior preserved).
- **Test coverage**: 130 passed + 1 skipped (was 118 — +12 weekly recap tests).
- **Pending**: optional `routes/tasks.py` thin wrapper. Frontend sub-component splits for `Today.jsx`/`Dashboard.jsx`/`Onboarding.jsx` remain on the deferred list.

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
