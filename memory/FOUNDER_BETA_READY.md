# EquineSync — Founder-Beta Readiness Snapshot
_Feb 20 2026 · single read-in-three-minutes assessment before the first barn comes online_

> This is not a launch announcement. It is a quiet checkpoint.
> Read it before the first founder-barn conversation. Read it before
> watching how the first real Monday lands. Then read it again afterwards.
>
> The goal is not to claim we are finished. The goal is to be honest about
> what is operationally trustworthy today, what is intentionally postponed,
> and what we want to learn.

---

## 1 · What is operationally complete

The following workflows now survive a real barn day:

- **Today** — unified urgency-ordered task stream with optimistic completion, swipe-right complete / swipe-left skip, outcome capture per category, and bulk mode (with per-group "Select all" for turnout rounds).
- **Care plan execution** — feed, medications, turnout, stall cleaning, blanket changes, vet visits, farrier work, and rehab all routed through the single Task Engine. Every completion writes one `task_event` row — no parallel scheduling silos.
- **Onboarding (Setup Concierge)** — staff, horses, owners, feed plans, vet/farrier records, inventory baseline. Resumable mid-flow. Drafts autosave on every change.
- **Day-2 CRUD continuity** — Add Horse / Owner / Rider / Inventory item / Incident report / Lesson / Training session, all materialised post-onboarding via the reusable `QuickAddSheet` pattern.
- **Owner Trust Loop** — daily digest (07:00 UTC), weekly Sunday recap (18:00 UTC), Wellness Pulse (rule-based, never speculative), curated owner timeline, in-portal service-request submission, and admin-side one-tap Approve / inline-Decline-with-note from inside the notification drawer.
- **Incident reporting** — calm, fast, type + severity + horse-or-facility + occurred-at + description + optional follow-up. One-handed mobile workflow.
- **Soft scheduling awareness** — lessons and training surface ±60-minute overlaps for the same rider or horse with calm informational copy. Never blocks. Real barns can intentionally overlap.
- **Notification reliability** — dispatcher now retries up to three times on transient errors before giving up. No silent drops from a momentary DB hiccup or email-provider blip.

---

## 2 · What we intentionally did NOT build

This list matters. It communicates restraint, not absence.

- **Recurring schedule materialization.** The data model exists and onboarding still collects the intent. The materializer is deferred to v1.1. Founder-facing exposure has been hidden — a broken scheduling promise is worse than a temporarily missing one.
- **Speculative AI features.** No LLM-driven dashboard widgets, no predictive horse-health text, no "AI suggestions" panels. The Wellness Pulse is rule-based, confidence-limited, and observational only. Veterinary liability is not a place to experiment.
- **Advanced analytics & reporting dashboards.** A founder-barn does not need pivot tables. They need their morning to go smoothly. Analytics are intentionally postponed until barn behaviour data tells us which numbers actually matter.
- **Marketplace, community, or social features.** Out of scope. Other products do this; ours is operational software, not a social network.
- **Hardcoded "demo theater"** — no fake weather card, no invented stats, no placeholder navigation linking to empty pages. If something is in the sidebar, it works.
- **Owner-side urgent push for in-the-moment events.** Deferred. Today the digest is daily; an owner finding out their horse went off-feed via a 24-hour-old email is suboptimal. We will add this only after we see how owners actually react to the digest cadence.
- **In-place inventory quantity edits.** Add and remove only, for now. The pattern for in-row +/- adjustment is sketched but the founder beta does not need it on day one.
- **Messaging compose draft preservation.** The QuickAddSheet pattern preserves drafts; the messaging composer does not yet. Listed in the post-beta queue.
- **httpOnly cookie migration for JWT.** Currently localStorage. Mitigated by short token lifetime + refresh rotation. Migration deferred until after founder-beta to avoid auth disruption during the most observation-critical window.
- **Object storage integration.** Cloudflare R2 stubbed; binary attachments not yet supported on incidents, horses, vet records. Post-beta.

---

## 3 · What was hardened during operational simulation

The full audit lives in `/app/memory/OPERATIONAL_SIMULATION.md`. Highlights:

- **Today filter persistence** — staff no longer lose their `feed` / `turnout` / `med` filter every time the phone locks. Estimated 30 wasted taps per groom per day, eliminated.
- **QuickAddSheet draft preservation** — every add form survives phone lock, accidental dismissal, weak signal. Silent restore on reopen. No "recovery mode" UI; just dependability.
- **Calm error recovery** — failed saves keep the sheet open with the form intact and an inline message reading _"Saved as draft — try again when you have signal."_ Never the panic-toast-and-wipe pattern.
- **Last-synced indicator** — `/today` and `/dashboard` quietly show when data was last fetched. Tap to refresh. No anxious connectivity dramatization.
- **Thumb-zone audit** — every interactive element measured at ≥40-44px tap height. Sticky modal footers so Save never hides under the keyboard. FAB stacking verified against modal sheets at common mobile viewport sizes.
- **HorseProfile tab strip** — soft edge fades hint at horizontal scrollability on mobile without cluttering the desktop view.
- **Bulk group-select** — saves 6-8 taps per turnout round; reversible; respects active filter; visible only in bulk mode.
- **Calm-tone audit as a verified test** — banned strings list ("Conflict", "Duplicate", "Reject", "Deny", "Action Required", "Urgent", "Warning:", "Error") is now machine-checked in the test harness. Tone is part of the architecture, not just a style choice.

---

## 4 · Mobile-readiness highlights

- Single-thumb operation across every primary workflow.
- Sticky footers on all add sheets — Save never disappears under the keyboard.
- FABs only on the four highest-frequency "log it now" pages (Inventory, Incidents, Lessons, Training).
- Pull-to-refresh equivalents are tap-to-refresh badges — more predictable on iOS Safari than gesture-based refresh.
- Horizontal-scroll tab strips fade their edges so users discover overflow without needing a tutorial.
- No layout that requires landscape orientation. Everything functions on a phone in a back pocket.

---

## 5 · Interruption-recovery protections

Real barn life means constant interruption. The platform now treats this as a default, not an edge case.

- Optimistic UI on task completion — the swipe registers before the network does.
- `taskSync` offline queue retries with exponential backoff and jitter.
- QuickAddSheet drafts persist in `sessionStorage` keyed by endpoint; restored silently on reopen.
- Onboarding autosaves on every change and resumes from the last step.
- Today filter selection persists across phone-lock and remount.
- Notification dispatcher retries transient failures up to three times before finalising.

---

## 6 · Notification trust protections

- Admin / manager / trainer roles see pending service requests directly in the bell drawer. One tap to approve. Inline composer for decline-with-note. No navigation to a separate page.
- Decline language is calm and explanatory — never transactional. The owner-side message reads _"Note from the barn: …"_ not _"Your request was rejected."_
- Single-composer-at-a-time semantics prevent stale state across reopens.
- 30-second polling refreshes both `/api/notifications` and `/api/service-requests`.
- Owner digest cadence is intentionally restrained — daily at 07:00 UTC, weekly recap on Sundays. Aggressive notification streams erode trust faster than they build it.

---

## 7 · Testing summary

- **Backend pytest:** 175 passing, 1 intentional skip, 0 failures. Coverage includes auth, the unified Task Engine, owner trust loop, weekly recap pipeline, wellness pulse rule logic, operations CRUD, onboarding flow, invites, dispatcher retry, and the founder-beta CRUD sprint regression set.
- **Frontend end-to-end iterations:** 17 through 23 (test reports under `/app/test_reports/`). Combined coverage: CRUD sprint, draft preservation, smart defaults, inline error recovery, last-synced badges, filter persistence, tap-zone geometry, edge-fade affordances, FAB stacking, soft conflict warnings, calm-tone audits, role-gated drawer flows, inline decline composer, dispatcher retry pytest integration.
- **Calm-tone audit results:** zero banned strings detected across all add sheets, all warning surfaces, all notification copy. Re-runnable as part of the regression set.

---

## 8 · Known founder-beta constraints

Honest disclosure before the first barn arrives:

1. Single-tenant. The current backend assumes one barn per deployment. Multi-tenant routing is not built.
2. No SMS or push channel. Email + in-app inbox only. Mobile push deferred to post-beta.
3. No granular permissions UI. Roles (admin, barn_manager, trainer, groom, horse_owner, veterinarian) are hard-coded; per-feature permission editing is not exposed.
4. JWT lives in `localStorage`. Mitigated by short token lifetime + refresh rotation; migration to `httpOnly` cookies deferred.
5. Service-request approval is admin/manager/trainer only. Owners cannot self-approve.
6. No attachment / photo support yet on incidents, horses, vet records.
7. Recurring schedules are collected during onboarding but not yet materialised into actual tasks. We will rebuild the materializer after observing how barns actually want recurrence handled in practice.
8. The first deploy expects a small to mid-size operation (≤80 horses, ≤20 staff, ≤120 owners). Larger barns will surface load characteristics we have not yet measured.

---

## 9 · Recommended founder-barn profile

The first barn should be:

- **30–60 horses.** Enough variance to exercise the system; small enough that the founder can observe every workflow themselves.
- **Mixed-discipline preferred.** Boarding + training + lesson program together stress more code paths than a single-discipline operation.
- **Operationally engaged ownership.** The founder needs to watch their staff use the software during real mornings. Not a hands-off owner.
- **A primary groom or barn manager willing to talk weekly.** This persona generates the most operational signal.
- **Comfortable with iOS Safari.** PWA-style usage; no native app yet.
- **Tolerant of friction in non-core areas.** The post-beta backlog items (in-place inventory edit, ad-hoc vet quick-add, etc.) will create occasional minor workarounds.

The wrong first barn is a large multi-facility operation, a barn with brittle existing software dependencies, or an owner who will not be physically present during the first two weeks.

---

## 10 · What we are actively seeking from the first barn

We are not seeking validation. We are seeking observation.

Specifically:

- **Where staff revert to texting, paper, or whiteboards.** Each instance is a workflow gap.
- **What time-of-day the platform feels heaviest.** Predicted hotspots: 5-7am feed, 12pm mid-day, 9pm bedcheck.
- **Which notifications get tuned out.** Frequency, timing, tone — all need real-barn calibration.
- **Where the calm tone reads as "too soft."** It is possible our restraint becomes ambiguous in safety-critical moments. We want to know.
- **What the owners ask for that we do not yet surface.** Especially around real-time updates between digest cycles.
- **What the trainer does that the platform doesn't help with.** Lesson scheduling, horse workload monitoring, rider development tracking.
- **Where the mobile experience breaks down outdoors, in poor signal, in cold-weather glove use.**
- **What the staff would never tell us in a survey but would say out loud during a Tuesday afternoon.**

These observations matter more than feature requests.

---

## 11 · Closing note

The platform has crossed a real threshold. It is now reasonable to believe that a small careful barn could form daily operational habits around it. That is a serious responsibility.

The next phase is no longer primarily building. It is listening — to actual barn mornings, to how owners read their digest with coffee, to the trainer between rides, to the groom in the aisle one-handed.

We will know we have succeeded when the first founder barn stops saying _"the software told me to do this"_ and starts saying _"this is just how we run the barn now."_

That is the goal. That is the only goal worth measuring.

— End of readiness snapshot. Continue to OPERATIONAL_SIMULATION.md for the deeper movement audit.
