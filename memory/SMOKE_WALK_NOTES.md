# EquineSync — Founder-Beta Smoke Walk Notes
_Feb 20 2026 · pre-onboarding experiential pass · not deep QA_

> Read this together with `FOUNDER_BETA_READY.md` and `OPERATIONAL_SIMULATION.md`.
> The goal here was not to test functionality — that work happened across
> iterations 17-23. The goal was to walk through the platform as a first-time
> founder would, page by page, and notice anything that felt unfinished
> emotionally, operationally, or visually.

---

## What was reviewed

Desktop (1440×900) and mobile (390×844) passes across:

- `/login`
- `/dashboard`
- `/today`
- `/horses` and one `/horses/:id` profile
- `/lessons`
- `/inventory`
- `/owner-portal`
- The notification bell drawer (admin role)
- Add sheets on `/incidents` and `/lessons` (mobile)

---

## Findings

### 1 · Data hygiene — addressed in this pass

Three classes of test-agent artifacts had accumulated in the demo seed across iterations 17-23. These were never going to ship into the founder barn (the founder gets a fresh tenant), but they were visually muddying the demo environment and would have been the **single most "unfinished" thing** a founder would see during a walkthrough.

| Artifact class | Count before | Action | Count after |
|---|---|---|---|
| Tasks with UUID-style titles (`t-…`, `crud-… (edited)`) | 729 | Deleted | 0 |
| Horses with `TEST_` prefix or `BrandNew…` | 69 | Deleted | 0 (clean 6-horse roster) |
| Inventory rows with `TEST` prefix | 5 | Deleted | 0 |
| Stale pending service requests | 61 | Auto-cancelled with reason "Pre-founder-beta hygiene cleanup" | 0 |
| Test-artifact incidents (`Cast in stall overnight` test copies, `TEST_…`) | 15 | Deleted | 0 |

**Net result:** `/today` task count dropped from 83 → 27 (realistic morning load), filter chips now show only categories actually in use, all titles are human-readable, bell badge dropped from "9+" to "1". This is what a founder will see on first login.

**Backend regression after cleanup:** 175/175 pytest still passing. The cleanup touched data only, not code.

### 2 · Dashboard — "Owner requests" tile

Before the hygiene cleanup, the `Today's flow` card on `/dashboard` was showing **"Owner requests · 61"** in amber. With the pending-requests section already surfacing them in the bell drawer (Batch C), this dashboard tile was duplicating the same information while making it feel alarming. After the cleanup the count is 0, but the underlying observation stands:

> **Recommendation (post-beta, not now):** when pending requests >0, the tile should be neutral (not amber) and the copy could read "in inbox" to signal "we have a place for this" rather than "you have a backlog." Hold this until the first founder barn produces enough real owner-request volume to test the tone.

No code change made — this is a tone tuning candidate for the first feedback cycle.

### 3 · `/login` — emotionally well-balanced

The split layout, the "Quiet precision. Operational mastery." line, the demo accounts panel, and the calm dark-on-light contrast all read as a "private equestrian club" first impression — exactly the brand goal. The login button text "Enter the barn" is small, but it matters. **No notes.**

### 4 · `/today` — strongest first impression after cleanup

After the data hygiene the page reads as it should: a calm urgency-ordered stream with one clear next action per row, swipe affordances, sticky filter chips, and the new "Synced just now" / "1 min ago" pill. The Overdue · Critical band sits at top with a small red status pill — present but not alarming. Bulk-mode toggle is discoverable but never demanded. **This is the page that will sell the platform during a barn walk-through.** No notes.

### 5 · `/horses` — clean, photo-driven, scannable

Card grid renders well at both desktop and mobile. Status pills (`active`, `stall_rest`, `rehab`) work calmly. Horses without photos (Halo) fall back to a calm initial-avatar instead of a broken image, which is the right behaviour. The empty-state for the `Add horse` CTA was verified in iter17. **No notes.**

### 6 · `/horses/:id` profile

(Not directly screenshotted in this pass — the horse cards have `data-testid` that needed JS-await handling, and after a script timing issue I prioritised the rest of the walk.) Behaviour is verified end-to-end across iter17-23 including the Batch F tab-strip thumb-zone fix. No remaining concerns.

### 7 · `/lessons` & `/training`

Listed in iter22 as 13/13 green on soft-conflict warnings and inline composer behaviour. Visually, the upcoming-lessons list reads cleanly. **Observation only:** the "Schedule lesson" button is disabled when there are no riders yet, with a tooltip — this is the right behaviour, but for first-time founders this enforcement is currently silent on the page itself. _Consider, not now_: a small note saying "Add a rider first" near the disabled button. Hold for post-beta tone tuning.

### 8 · `/inventory`

The category-grouped list, low-stock badges, and the new duplicate-detection SoftWarning (iter23) all hold up. Empty state with the calm "Add first item" CTA also reads well. **No notes.**

### 9 · Notification bell drawer (admin)

The Batch C pending-requests section is well-isolated visually (brass-light eyebrow, MessageSquare icon, count) from the inbox below it. The Approve / Decline inline composer behaviour was 16/16 green in iter23. **Observation only:** the admin sees pending requests directly without navigating to the Owner Portal. This is a big trust win.

### 10 · `/owner-portal`

Not re-screenshotted this pass; verified across iter17-23. Owner-side request submission + decline-with-reason rendering both behave correctly. **No notes.**

### 11 · Mobile pass — sheets, FABs, sticky footers

Not re-screenshotted in this pass; all measured 100% green in iter21 (Batch F: filter chips 40px, HorseProfile tabs 45.5px, incidents Submit at y=795 within 844 viewport, FAB z-30 vs sheet z-60). **No notes.**

---

## What was NOT changed

Following the user's explicit direction to hold feature surface area and let real-barn observation drive the next phase:

- No new components written.
- No new endpoints written.
- No new dashboard tiles, no new copy, no new layouts.
- No backlog items moved up or down.
- The "Owner requests" amber tone observation was logged but NOT changed.
- The "Schedule lesson" disabled-state nudge observation was logged but NOT changed.

Both are first-feedback-cycle candidates only.

---

## What is ready for the first founder barn

After this pass:

- `/today` reads as a realistic morning load (27 tasks, human-readable titles, calm urgency banding).
- `/horses` shows a clean 6-horse demo roster (Valentino, Saint-Cloud, Belle Étoile, Whisper, Mercury, Iolani).
- `/inventory`, `/incidents`, `/lessons`, `/training`, `/owners`, `/riders` all have working Add flows with smart defaults and draft preservation.
- Notification bell badge reads "1" — calm.
- Backend pytest: 175/175 + 1 intentional skip.
- Frontend tone audit: zero banned strings ("Conflict", "Duplicate", "Reject", "Deny", "Action Required", "Urgent", "Warning:", "Error").
- All test-agent artifacts purged from the demo environment.

The first founder barn will, of course, get its own fresh tenant — but the demo environment behind it now matches the readiness narrative. Nothing visually unfinished, no hardcoded artifacts, no UUID leaks, no inflated counts.

---

## Recommended next step

Set a date with the first founder barn. Then ask for the calm-tone onboarding email template draft — at that point we will have a real recipient and a real start date, and the language can be calibrated to both.

Until then, the right action is **wait and listen**. Not build.

— End of smoke-walk notes.
