# EquineSync — Founder-Beta Operational Trust Audit
_Generated Feb 20 2026 · post-Phase-F · pre-founder-barn-onboarding_

This is an honest, operationally-focused audit. **No new features recommended.**
Every item is graded against the question: _"Could a real barn operate daily on this today, and would they trust it?"_

---

## 0 · Topline Verdict

**The platform is architecturally founder-beta-ready.**
**The platform is operationally NOT YET ready — 7 critical workflow gaps remain.**

The unified Task Engine, owner trust loop, mobile Today flow, digest pipeline, role gating and offline-tolerant sync are all real and verified. What is NOT yet real is the post-onboarding daily editorial surface: half a dozen pages ship as read-only lists where founders will reach for an "Add" or "Edit" button and find none. Three nav items still link to a "Coming soon" template. One workflow (Recurring Schedules) is a complete write-only silo. One UI surface (Weather) is hardcoded fake data. One feature (HorseProfile AI Owner Update) directly contradicts the agreed restraint direction.

Fix the 7 critical items below and the platform is genuinely defensible in a real barn.

---

## A · Founder-Beta Critical Path
_Ordered list — these MUST be addressed before onboarding the first founder barn._

| # | Item | Why it blocks | Effort |
|---|---|---|---|
| **1** | **Add owners / riders post-onboarding** — `/owners` and `/riders` pages are read-only lists with NO create form. Onboarding wizard is the only path. A barn that boards a new horse on day 3 has no way to add that owner. | Workflow continuity failure. Forces operator back to onboarding wizard for routine adds. | S (extract `RecordsStep` shell, reuse on these pages) |
| **2** | **Inventory page is a "Coming soon" placeholder** while the backend `/inventory` CRUD + low-stock detection is fully working. Wire the real list/add/remove UI in. | Founder will click the nav item and feel deceived. Worse, low-stock alerts already fire in the dashboard summary code path that references `inventory.reorder_at`. | S |
| **3** | **Recurring Schedules is a write-only silo** — Onboarding collects them, no scheduler reads them, no tasks are generated from them. Either (a) wire them to materialize into TaskTemplate rows via the engine, or (b) hide the step until wired. **Architectural risk per the "no parallel state" directive.** | Quietly broken promise. Founder sets a "Mon-Fri turnout @ 07:30" schedule and nothing happens. | M |
| **4** | **Weather card is hardcoded** (`temp_f: 58, condition: "Light Rain"`) in `routes/dashboard.py`. This is exactly the "fake dashboard surface" pattern flagged in earlier audits. Either remove the card OR wire a real weather API (OpenWeather/Tomorrow.io). | Founder sees the same "Light Rain" every day → trust collapse. | S to remove · M to wire real |
| **5** | **HorseProfile AI buttons** (`Wellness Insight`, `Training Summary`, `Owner Update`) generate speculative LLM text that contradicts the agreed "no speculative AI / no pseudo-veterinary advice" direction. The Wellness Pulse is the calm rule-based replacement; these buttons should be **removed** (not deferred). | Veterinary liability + tone mismatch + violates restraint direction. | XS (delete 3 buttons + handler block) |
| **6** | **Lessons + Training have NO create UI.** `/lessons` shows scheduled lessons read-only — there's no "schedule a lesson" form. Same with Training Log. Backend POST endpoints exist; UI doesn't. | Trainers cannot run their core workflow on the platform. | S each |
| **7** | **Incidents — no "Report incident" form on `/incidents` page.** Read-only browse only. Safety reporting is a foundational workflow. | Real incidents in real barns happen weekly. Cannot rely on the platform without this. | S |

**All seven are S/XS/M-effort. None require new architecture.**

---

## B · Remaining Placeholder Matrix

| Surface | Status | Risk | Recommended action |
|---|---|---|---|
| `/inventory` | placeholder page over working backend | **A** (founder-beta blocking) | Wire the real UI — see Critical #2 |
| `/shows` | placeholder page, no data model | C (safe defer) | Leave nav item but mark "v2" in label or hide for now |
| `/documents` | placeholder page, no data model | C | Same — hide until R2 storage lands |
| `/maintenance` | placeholder page, no data model | C | Same |
| `/staff` | placeholder page; `/invites` covers most | B (post-beta) | Either fold into Settings → Team OR build real staff roster page |
| Weather card | hardcoded fake data | **A** | Critical #4 — delete or wire real |
| Reports module | real backend, real frontend (`Reports.jsx`) for setup-health + nudges | — | OK; not a placeholder |
| HorseProfile AI buttons | working but speculative | **A** | Critical #5 — delete |
| Recurring Schedules | write-only silo | **A** | Critical #3 — materialize or hide |
| `feed_tasks` legacy collection | back-compat shim, superseded by engine | C | Can be quietly retired after one founder-beta cycle |
| Owner Portal "billing" / "documents" tabs | none today — but Owner Portal is genuinely complete | — | Don't add tabs preemptively |

---

## C · Operational Completeness Per Workflow

Legend: ✅ fully operational · 🟡 partial · 🔴 visually present but incomplete · ⛔ architecturally blocked · ⚪ safely deferrable

| Workflow | Status | Notes |
|---|---|---|
| **Onboarding** | ✅ | 10-step wizard, autosave, CSV import, resume, role-aware. Strong. |
| **Horse creation** | 🟡 | Via onboarding ✅. Post-onboarding `/horses` page has search + drill-down but no "Add horse" button. |
| **Owner creation** | 🔴 | Critical #1. Backend works, page is read-only. |
| **Rider creation** | 🔴 | Critical #1. Same. |
| **Feed (today)** | ✅ | Engine-backed, mobile-first, swipe-to-complete, offline-tolerant, syncs to timeline. Best-of-class. |
| **Medications (today)** | ✅ | Same engine, outcome tracking (given/refused/skipped), follow-up auto-scheduling. |
| **Turnout** | ✅ | Phase-E filtered engine view. Out + Bring-in grouping. |
| **Rehab** | ✅ | Phase-E filtered engine view. |
| **Vet records** | 🟡 | Engine completion writes vet_records ✅. `/health` page is read-only — no "add ad-hoc vet visit" form. |
| **Farrier history** | 🟡 | Engine writes farrier_history ✅. Display only on /health. No retrospective entry. |
| **Wellness logging** | 🔴 | Backend POST works + bumps horse score. No UI surface to enter a wellness reading. |
| **Owner Portal** | ✅ | Digest + weekly recap + decline modal + curated timeline. Strong. |
| **Notifications** | ✅ | Dispatcher loop + preferences matrix + digest_enabled toggle. |
| **Daily digest** | ✅ | Idempotent, soft-tone, Wellness Pulse layered. |
| **Sunday recap** | ✅ | ISO-week idempotent, scheduled, calm. |
| **Scheduling — recurring** | ⛔ | **Recurring schedules collection write-only.** Critical #3. |
| **Scheduling — ad-hoc** | ✅ | Engine `POST /tasks` works. |
| **Arena coordination** | ⚪ | Not modeled; reasonable to defer until founder feedback. |
| **Service requests** | ✅ | Submit + approve + decline with reason + owner-visible note. |
| **Lessons** | 🔴 | Critical #6. |
| **Training** | 🔴 | Critical #6. |
| **Invoices/billing** | 🟡 | List + mark-paid works. No "create invoice" UI. Manual invoice creation must happen via API today. |
| **Inventory** | 🔴 | Critical #2. |
| **Incidents** | 🔴 | Critical #7. |
| **Messaging** | 🟡 | Compose + inbox works. No recipient targeting (only role-visibility). No threads, no read/unread. Acceptable for v1. |
| **Dashboard summaries** | ✅ | Engine-derived, real data, no fake percentages (already audited). |
| **Today flows** | ✅ | The strongest surface in the app. |
| **Mobile task completion** | ✅ | Swipe + 44px taps + sticky filter + bulk mode. |
| **Task recurrence** | 🟡 | RRULE-based templates work in engine. The Onboarding `recurring_schedules` step is the silo (Critical #3). |
| **Timeline visibility** | ✅ | Curated owner timeline + admin timeline both engine-derived. |
| **Onboarding recovery/resume** | ✅ | Autosave, resume from /dashboard concierge, reassurance copy. |

**Tally: 19 ✅ · 5 🟡 · 6 🔴 · 1 ⛔ · 1 ⚪**

---

## D · Task Engine Consistency Audit

| Question | Answer |
|---|---|
| Is there ONE place writing `task_events`? | ✅ Yes — `task_engine.py:363` (`_record_event`). Plus `seed_pulse_demo.py` for demos. |
| Do all completions route through the engine? | ✅ Feed, Meds, Turnout, Rehab, Vet, Farrier — yes. `/feed-tasks/{id}/complete` (legacy) is a vestige and untested by founders. |
| Is there shadow state? | 🟡 **Yes — one piece**: `recurring_schedules` (write-only, never materialized). Critical #3. |
| Are notifications driven by `task_events`? | ✅ Yes via the dispatcher loop in `notifications.py`. |
| Are timelines derived from `task_events`? | ✅ Yes — owner curated timeline + horse timeline both query the events collection. |
| Does the engine support offline sync? | ✅ Yes via `taskSync.js` queue. |
| Are duplicate operational sources still around? | The legacy `feed_tasks` and `medication_logs` collections still receive writes via care.py back-compat endpoints. Not used by Today. Safe to retire after founder-beta. |

---

## E · Mobile Friction Report
_Top pain points if a barn manager / groom only had a phone._

| # | Surface | Pain | Severity |
|---|---|---|---|
| 1 | `/onboarding` | Stepper sidebar is `sticky top-24` and a 4-column grid — usable but cramped on iPhone SE width. Step content is fine. | Low |
| 2 | `/health`, `/incidents`, `/lessons`, `/training` | No bottom-sheet "Add" pattern; user has to find the right tab/page. Compounds Critical #6, #7. | Medium (after Critical wires land) |
| 3 | `/horses/:id` (HorseProfile) | AI buttons (3) at the top take vertical real estate before the tabs. Remove them (Critical #5). | Low |
| 4 | `/notifications` (bell) | Drawer works, but no swipe-to-dismiss on individual rows. Founder will expect mail-app behavior. | Low |
| 5 | `/dashboard` | Founder Walkthrough fires once — good. But on first paint, hundreds of pixels of stats compete for attention. The Founder Tour helps; the FAB → Today helps. Acceptable. | Low |
| 6 | Settings page | Notification matrix is dense on narrow screens. Tolerable, not friction-blocking. | Low |
| 7 | Service request decline modal | Modal is wide and centered — fine on mobile. Reason textarea defaults to 3 rows; thumb scroll lands inside. | None |

**Today / Feed / Medications / Turnout / Rehab — mobile UX is genuinely strong.**

---

## F · Operational Trust Risk Report

| Risk | Severity | Why |
|---|---|---|
| Founder clicks Inventory → sees "Coming soon" | **HIGH** | Suggests platform isn't real. Critical #2. |
| Founder enters Recurring Schedules, nothing happens | **HIGH** | Quiet broken promise. Critical #3. |
| Weather card always says "Light Rain" | **HIGH** | Founder catches the lie on day 2. Critical #4. |
| Owner enters platform, sees "AI Owner Update" button | **MEDIUM** | If pressed and the output reads off, owner trust evaporates. Critical #5. |
| Barn manager cannot add new owner without rerunning onboarding | **MEDIUM** | Forces clunky workaround. Critical #1. |
| Trainer cannot schedule lessons in-app | **MEDIUM** | Forces reverting to paper/Calendly. Critical #6. |
| No way to record an incident from phone | **MEDIUM** | When it matters, the platform isn't there. Critical #7. |
| `medication_logs` legacy collection still receives writes | Low | Vestigial; cleanup can wait. |
| Notification dispatcher polls vs streams | Low | Acceptable scale until 5+ barns. |

---

## G · Daily Dependency Loop Audit

**Strong loops (founders will return for these):**
- ✅ Today (3-5x daily for grooms; 1-2x for trainers)
- ✅ Owner Portal — owners pull morning email + occasional portal visits
- ✅ Feed completion (mobile, swipe-fast)
- ✅ Medication completion (with outcome capture)
- ✅ Notifications bell + drawer
- ✅ Curated timeline (owner-visible, weekly)

**Weak / missing loops:**
- 🔴 Trainer daily loop — `/lessons` and `/training` are read-only. No reason to open them after onboarding.
- 🔴 Owner approvals — owners can submit requests; staff need to come to /owner-portal to approve. Should surface in the Notifications bell with one-tap approve.
- 🟡 Inventory low-stock — backend computes, but page is placeholder.
- 🟡 Incident reporting — no in-app trigger; staff revert to text messages.

**Recommendation:** the dependency loop weakness is concentrated in the trainer/scheduling axis. Fixing Critical #6 disproportionately strengthens daily reliance.

---

## H · Safe-To-Defer Registry
_Do NOT prioritize before founder-barn feedback._

- Shows & Competitions module
- Documents/file storage (Cloudflare R2)
- Maintenance module
- Dark-mode toggle
- BI / Reports charts beyond setup-health
- Push notifications (web-push) — email + in-app sufficient
- React hook-deps eslint cleanup
- httpOnly cookie migration (intentional defer per prior direction)
- AI Wellness Pulse upgrade to LLM (rule-based version is the agreed restraint)
- Object storage for horse/injury media
- Reports → BI charts
- Threaded messaging / read receipts
- Advanced search / saved views

---

## I · Delete / Consolidate Recommendations

| Item | Recommendation | Why |
|---|---|---|
| `HorseProfile` AI buttons (3) + `/ai/generate` endpoint | **Delete** | Contradicts restraint direction. Wellness Pulse is the calm replacement. |
| Weather card (Dashboard SmallCards) | **Delete the card** (don't replace with real weather yet) | One less fake surface; weather isn't operationally critical for v1. |
| `/shows`, `/documents`, `/maintenance` placeholder pages | **Hide from sidebar** for founder-beta | Reduces broken-promise surface area. Reintroduce when shipping the real thing. |
| `Placeholder.jsx` component | Keep, but stop referencing it in any active route | Useful for staging surfaces during development. |
| Legacy `/feed-tasks` and `/medication-logs` endpoints | **Defer** removal | Tests reference them. Wait until founder-beta wraps. |
| Standalone `/staff` nav item | **Fold into Settings → Team** | One less route. Invites already live in onboarding. |
| `/training` and `/lessons` as separate top-level pages | After wiring create UI (Critical #6), evaluate consolidating into a single `/program` tab with Training + Lessons subviews | Reduces nav clutter; both target the same trainer persona. |

---

## J · Recommended Founder-Beta Sprint Ordering

If you have ~3 incremental days of work before onboarding the first barn, do them in this order. Each is independently testable, none introduce new architecture, each strengthens trust:

1. **Delete weather card + HorseProfile AI buttons + hide placeholder nav items** (~30 min, deletes only — high trust dividend per minute)
2. **Wire `/inventory` page to the real backend** (~2 hr, all CRUD exists already)
3. **Add "Add owner" + "Add rider" forms to their existing pages** (~2 hr, reuse `RecordsStep`)
4. **Add "Report incident" form to `/incidents`** (~1.5 hr, simple POST)
5. **Add "Schedule lesson" + "Log training session" forms** (~3 hr combined)
6. **Decide on Recurring Schedules**: materialize-into-engine (full fix, ~4 hr) or hide-the-step (quick clarity, ~15 min). Recommended: hide the step for beta, keep the data model for v1.1.
7. **Add "Create invoice" UI** (~2 hr) — optional but high trust for billing-oriented barns.

**Total: ~14 hours of focused, low-risk, behavior-preserving work.**

After that, the platform stops feeling "almost there" and starts feeling **operationally real**.

---

## K · What's Genuinely Excellent Right Now

To balance the audit — these are real strengths a founder barn will feel within minutes:

- Unified Task Engine + `task_events` as the single operational source of truth
- Today view (best-of-class mobile execution)
- Offline-tolerant `taskSync` queue with optimistic UI
- Owner Trust Loop (digest + weekly recap + decline-with-reason)
- Curated owner timeline that respects boundaries
- Wellness Pulse — restrained, rule-based, confidence-limited
- Founder Walkthrough — calm, read-only, two-minute tour
- Onboarding concierge with autosave + reassurance copy
- Phase-F architecture: server.py from 1949 → 836 lines with zero behavior change
- 152/152 pytest coverage + zero ui_bugs across 15 testing-agent iterations

**The bones are sound. The remaining work is editorial completion, not architectural.**
