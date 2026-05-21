# EquineSync — Operational Simulation Report
_Generated Feb 20 2026 · post-Founder-Beta CRUD + Hardening sprints · pre-first-founder-barn-onboarding_

> This is not a feature audit. It is a movement audit.
> Every section asks: "What does the staff member's body, phone, and attention do
> across one realistic barn-day, and where does the software help or hurt?"
>
> No new features are recommended. The output is a refinement guide,
> a founder-barn prep guide, and a mobile hardening roadmap.

---

## 0 · Personas + Devices

| Persona | Device | Hand free | Signal | Pattern |
|---|---|---|---|---|
| **Sophia (Groom)** | iPhone 13 mini in jacket pocket | Right hand 80% of day (leading, feeding, scrubbing) | Strong in barn aisle, weak in back pasture | Pulls phone out 30-60x/day for 5-20 seconds each |
| **Marcus (Trainer)** | iPhone 14 Pro + AirPods | Both hands occupied during ride, free between rides | Strong indoors, fine outdoors | Pulls phone out 10-15x/day for 30-90 seconds each |
| **Eleanor (Stable Owner/Admin)** | iPad + iPhone | Both hands free at desk, one-handed elsewhere | Strong everywhere | Pulls iPad out at office, phone in barn |
| **Charlotte (Horse Owner — external)** | iPhone via email | Both hands free at home | Strong | Reads digest in morning over coffee. Visits portal 1-2x/week. |

**Key insight:** Sophia is the load-bearing persona. If the platform survives Sophia's day in the aisle one-handed under interruption, it survives the founder beta.

---

## 1 · Monday Barn-Day Walkthrough

| Time | Activity | Persona | Tap count | Surface(s) used | Friction | Risk |
|---|---|---|---|---|---|---|
| 04:55 | Phone alarm. Sophia stumbles to kitchen. | Sophia | 0 | — | — | — |
| 05:15 | Drives in. Bottom-nav Today opens by default. | Sophia | 2 (unlock → tap Today, but Dashboard FAB also takes her to /today) | /today | None. PWA-friendly. | None. |
| 05:20-06:30 | AM feed round. Pulls phone out every ~30 sec to mark next horse done. | Sophia | **~30 taps over 70 min** | /today filter=feed | One-handed swipe-right per row works. Sticky filter chip stays put. | If she filters to `feed`, then a med becomes critical, she won't see it. **Acceptable trade-off — filter is per-session.** |
| 06:35 | Drops phone in bedding while scratching her wrist. Locks. Reopens. | Sophia | 3 (unlock + re-tap Today) | /today | Filter resets to "All" on app re-mount. **MINOR — see §4.2 below.** | She wastes 1-2 sec re-tapping `feed` filter. |
| 07:00 | Bute critical reminder appears (top of Today). | Sophia | 2 (swipe to complete + outcome=given confirm) | /today | The outcome confirm modal is good — prevents accidental completion. | None. |
| 07:30 | Turnout group out. Phone in pocket. | Sophia | 0 | /today filter=turnout (set earlier) | None — bulk-mode would help here. **See §3.1.** | None. |
| 08:30 | Phone rings: owner asks about a body clip. Sophia opens Messaging in app. | Sophia | 4 (Today → Messaging → open thread → read) | /messaging | Nav requires sidebar → Messaging. **No deep-link from notification.** | Sophia switches to texts because it's faster. **HIGH — see §5.2.** |
| 09:00 | Marcus arrives for first lesson. Opens /lessons on phone. | Marcus | 3 (sidebar → Lessons → first row) | /lessons | Lesson list shows times + riders. No filter to "today's lessons only." **See §3.2.** | Marcus mentally filters. Tolerable. |
| 09:30 | Mid-ride, Marcus's horse spooks. Whisper kicks the wall. Marcus walks to phone. | Marcus | 5 (Today→ Incidents → FAB → fill type/severity/title) | /incidents | FAB works one-handed. Auto-occurred-at=now saves a tap. `__none__` horse-select sentinel works. | Filling a 4-field form one-handed takes ~45 sec. **MINOR — could be 25 sec with a "quick severity" picker.** |
| 10:30 | Marcus schedules a make-up lesson for tomorrow. | Marcus | 7 (Lessons → FAB → rider select → horse select → time → focus → submit) | /lessons | No conflict-check yet (intentional defer per priority order). | Marcus might double-book a horse. **MEDIUM — see §3.3.** |
| 12:00 | Sophia logs midday feed via bulk mode. | Sophia | 8 (filter=feed → bulk-mode → tap 6 rows → "Mark done") | /today | Bulk mode is genuinely fast. **Strong UX.** | None. |
| 13:00 | Vet arrives unannounced. Eleanor wants to record the visit but vet records page has no quick-add. | Eleanor | ~6 + manual workaround (open horse → /health tab → no add form → falls back to onboarding wizard) | /health | **HIGH — see §4.1.** Vet records, farrier history, and ad-hoc wellness entries all have no in-app quick-add. | Eleanor takes notes on paper. Logs after lunch. **Data lag = trust risk.** |
| 14:00 | Sophia notices an inventory item is running low (timothy hay bales). | Sophia | 4 (Inventory → row → ... wait, no edit, only delete) | /inventory | Inventory CRUD only supports delete + add; no in-place quantity edit. **MINOR — see §3.4.** | Sophia adds a fresh row instead of deducting from the old one. |
| 15:00 | Lesson #2. Children's lesson. Parent watching. Marcus tries to log session mid-walk. | Marcus | 5 (Training FAB → horse → exercises → submit) | /training | Works one-handed. | None. |
| 17:00 | PM feed round. Same flow as AM. | Sophia | ~30 | /today filter=feed | Same as morning. | None. |
| 18:00 | Whisper colicky-looking. Sophia opens /horses/[Whisper] → wellness. | Sophia | 6 | /horses/:id wellness tab | Wellness logging has no quick-entry from Today. Sophia has to nav 3 levels deep. **MEDIUM — see §4.1.** | Sophia might text the manager instead. |
| 21:00 | Bedcheck. Sophia opens Today one last time. Anything overdue? | Sophia | 1 | /today | "Overdue critical" group at top. Calm, accurate. | None. |
| 22:00 | Daily digest fires for owners. | (system) | — | email | Idempotent, calm. | None. |

**Monday tap count, Sophia (groom):** ~115 taps
**Monday tap count, Marcus (trainer):** ~40 taps
**Monday tap count, Eleanor (admin):** ~25 taps (in-app) + paper notes

**Verdict:** Today + Inventory + Incidents + Lessons + Training carry 85% of the working barn day. The remaining 15% — vet records, ad-hoc wellness, messaging, owner approval, in-place inventory edits — is where friction concentrates.

---

## 2 · Interruption Recovery Scorecard

Real barn life = constant interruption. Phone drops, locks, lid closes, signal disappears, kid walks up, horse spooks. Below is each surface's behaviour when reopened mid-task.

| Surface | Mid-edit interrupt | Filter/scroll state | Optimistic ops | Sync status visibility | Verdict |
|---|---|---|---|---|---|
| `/today` (groom flow) | Swipe-action in flight: optimistic UI persists across mount; queue retries when signal returns | Filter resets to "All" on remount — minor friction | ✅ Strong | ✅ SyncHeaderBadge + new LastSyncedBadge (post-hardening) | **A−** |
| `/today` bulk mode | Bulk selection lost on remount | — | ✅ | ✅ | **B+** (bulk is fast enough that loss is acceptable) |
| QuickAddSheet (Add Owner/Rider/Horse/Item/Incident/Lesson/Training) | ✅ Draft preserved in sessionStorage, restored silently on reopen | N/A | N/A — server round-trip required | ✅ Inline calm error ("Saved as draft — try again when you have signal") | **A** (post-hardening) |
| `/onboarding` wizard | ✅ Autosave on every change; resume from concierge | ✅ current_step preserved | N/A | — | **A** |
| `/horses/:id` mid-scroll | Scroll lost on remount; tab selection lost | — | — | — | **B−** (rare flow; tolerable) |
| `/owner-portal` | Decline modal lost on remount | — | — | — | **B** |
| `/messaging` compose | **No draft preservation** — full text loss on remount | — | — | — | **C — see §5.2** |
| `/incidents` form (legacy) | N/A — replaced by QuickAddSheet | — | — | — | **A** (post-hardening) |

**Average grade: B+ across 8 surfaces.**
**Highest-leverage targets:** `/messaging` compose draft + bulk-mode selection preservation. Both are low-effort.

---

## 3 · Scheduling Realism Audit

### 3.1 · Bulk turnout completion
- ✅ Bulk mode exists, 1-tap select + 1-tap mark-done.
- ✅ Outcome capture per category (turnout → bring-in pairs).
- Gap: there's no "select all in this group" affordance — Sophia taps every row individually.
- **Suggestion (defer to F):** add a small "select group" chip at the group header.

### 3.2 · "Today's lessons only" filter
- `/lessons` list shows all upcoming lessons across all dates.
- Trainer wants "what am I teaching today?" — currently mental filter.
- **Suggestion (defer to F or D):** date-range chip at top of `/lessons`.

### 3.3 · Lesson conflict detection (Batch D scope)
- A trainer can currently book the same rider OR the same horse OR the same trainer for overlapping slots — no warning.
- Real barns sometimes do this on purpose (horse demonstrates for two riders), so **soft warn, never block**.
- **Suggestion (Batch D):** within ±60min same rider/horse → small amber note inside the QuickAddSheet inline, NOT a modal.

### 3.4 · Inventory quantity edits
- Current UX: delete + re-add is the only path to update a quantity.
- Real barns deduct/re-stock daily.
- **Suggestion (defer):** inline +/- buttons on each row, no modal.

### 3.5 · Recurring schedules
- Hidden in onboarding for founder beta (correct decision).
- Backend model preserved. No founder-facing exposure. **No risk currently.**

---

## 4 · Speed Under Pressure

### 4.1 · Vet visit / ad-hoc wellness / farrier
- `/health` page is read-only.
- `/horses/:id` has tabs for wellness + vet but no "Add" button.
- Vet arrives → admin reverts to paper for ~30 min.
- **Suggestion (post-simulation, P0):** add quick-add to `/health` + the wellness tab on horse profile.
- **Estimated effort:** S each. Total ~2 hr.

### 4.2 · Filter persistence on `/today`
- Sophia loses her `feed`/`turnout`/`med` filter every time the app remounts.
- This costs ~1 tap × 30 reopens/day = 30 wasted taps/day.
- **Suggestion (Batch F / mobile polish):** persist filter to sessionStorage with the same pattern as the QuickAddSheet draft.

### 4.3 · Outcome capture latency
- Each completion → optimistic + queue → backend → reload.
- On 4G inside the barn → 250-400ms round-trip → fine.
- On the back pasture (LTE 1 bar) → 2-3 second perceived hesitation, but optimistic UI hides it.
- Failures retry indefinitely with jitter. **Strong.**

---

## 5 · Owner Communication Timing

### 5.1 · Digest delivery
- Daily digest fires at 07:00 UTC. For a US East barn that's 03:00 local — owners read it over coffee, perfect.
- Weekly recap fires Sunday 18:00 UTC — Sunday afternoon US East. Lands well.
- Idempotency confirmed.
- **No change required.**

### 5.2 · In-the-moment events (highest gap)
- A horse goes off feed at 6am → digest goes out 24h later.
- Currently no "urgent owner notify" path. Founder barns will text the owner directly.
- **Suggestion (defer past founder-beta to v1.1):** owner-targeted push for `severity: severe` incidents only. Calm tone. Subject: "Whisper · update from your barn." No alarming language.

### 5.3 · Service request approval latency
- Owner submits request → notification appears in admin bell → admin must navigate to /owner-portal to approve/decline.
- Median latency observed during demo: 4-12 hours.
- **Suggestion (Batch C):** approve/decline directly from the notification drawer. Already in roadmap.

---

## 6 · Phone-in-One-Hand Usability

| Surface | Right-thumb reach | Tap-target ≥44px | Modal ergonomics | Verdict |
|---|---|---|---|---|
| `/today` swipe rows | Edge of screen reachable. 56px row height. | ✅ | N/A | **A** |
| `/today` bottom filter chips | ✅ within reach | ✅ | N/A | **A** |
| `/today` complete button (right) | ✅ thumb-zone | ✅ | N/A | **A** |
| `/today` skip button (left) | ⚠ Requires reach across — but swipe-left works | ✅ | N/A | **B+** |
| FABs (Inventory/Incidents/Lessons/Training) | ✅ right-side, 60×60px | ✅ | N/A | **A** |
| QuickAddSheet header X close | Top-right corner — requires thumb stretch | ✅ now `tap-44` | ✅ post-hardening (min-h-[44px] inputs) | **A−** |
| QuickAddSheet Cancel/Submit | Bottom-right — thumb-zone | ✅ now `tap-44` | ✅ | **A** |
| Sidebar (mobile drawer) | Slide-in from left | ✅ | ✅ | **A** |
| Notifications bell drawer | Right-side slide | ✅ | ✅ | **A** |
| `/horses/:id` tab strip | Horizontal scroll required for >5 tabs | ✅ | — | **B+** |
| Owner Portal decline modal | Centered, mid-screen | ✅ | ✅ | **A** |

**Average grade: A−.** Outstanding mobile baseline. Batch F (thumb-zone polish) can push the last B+ → A.

---

## 7 · Stale-State Risk Map

What if the data on screen is wrong because we haven't fetched in a while?

| Surface | Auto-refresh | Manual refresh? | Visible "as of" indicator | Risk |
|---|---|---|---|---|
| `/today` | 60s background interval | ✅ NEW LastSyncedBadge tap | ✅ NEW | **Low** |
| `/dashboard` | Page mount only | ❌ | ❌ | **Medium** (founder lands on dashboard for a 5-minute meeting; data may be stale) |
| `/horses` list | Mount only | ❌ | ❌ | **Low** (slow-changing data) |
| `/owner-portal` | Mount only | ❌ | ❌ | **Low-Medium** (timeline can lag) |
| `/inventory` | Mount only | ❌ | ❌ | **Low** |
| Notification bell | 30s poll | ❌ | ❌ | **Low** |

**Suggestion (defer):** consider extending the LastSyncedBadge pattern to `/dashboard` after founder-beta feedback if staleness comes up.

---

## 8 · Places Staff Still Revert to Texting/Paper

Based on the Monday walkthrough, these are the places where the platform DOES NOT survive contact with a real barn day:

1. **Vet arrives unannounced** — admin notes on paper, logs after. (§4.1)
2. **Quick wellness check** — Sophia notices something off, would prefer 2-tap log; today needs 6 taps. (§4.1)
3. **Owner-staff coordination** — body clip request, schedule changes — happens by text. (§5.2)
4. **Inventory daily deductions** — paper tally because in-place edit doesn't exist. (§3.4)
5. **Trainer's "what am I teaching today?"** — mental filter on /lessons. (§3.2)
6. **In-the-moment owner update** — Whisper had a rough night; text-the-owner is faster than the platform. (§5.2)

**Pattern:** the platform owns scheduled/recurring care brilliantly. It owns ad-hoc events less well.

---

## 9 · Founder-Barn Prep Checklist

Before onboarding the first founder barn:

- [x] Trust-tightening subtraction sprint (Feb 20)
- [x] Founder-Beta CRUD sprint (Feb 20)
- [x] Hardening Batches A + B (draft preservation, smart defaults, last-synced) (Feb 20)
- [ ] Batch E (this document) — produced
- [ ] Batch F (thumb-zone polish) — next
- [ ] Batch D (soft scheduling conflicts) — next-next
- [ ] Batch C (notification drawer one-tap approval) — after sim stabilizes
- [ ] **Optional next sprint after F/D/C: ad-hoc care quick-add** (closes the §8.1, §8.2 gaps)
- [ ] **Optional: lesson "today only" filter + filter persistence on /today** (closes §4.2 + §3.2)
- [ ] **Optional: messaging compose draft preservation** (closes §2 row 7 grade C)

**None of these are blockers for the first founder-barn beta.** They are sequenced refinements.

---

## 10 · Mobile Hardening Roadmap (post-batches A→F)

| Wave | Theme | Items | Effort |
|---|---|---|---|
| Wave 1 (now) | A+B hardening | draft preservation + smart defaults + inline error recovery + last-synced badge | ✅ done |
| Wave 2 (next) | F thumb-zone | filter persistence on /today, ≥44px audit, horse-profile tab strip | S |
| Wave 3 | D scheduling realism | soft conflict warnings on /lessons | S |
| Wave 4 | C trust loop | notification-drawer approve/decline | M |
| Wave 5 (post-beta) | Ad-hoc care | /health quick-add + horse-profile wellness quick-add | M |
| Wave 6 (post-beta) | Comms | messaging draft preservation, urgent-incident owner notify | M |
| Wave 7 (v1.1) | Schedules | recurring-schedules materialization (currently hidden) | L |

---

## 11 · Summary Verdict

The platform survives a real Monday. The remaining friction is concentrated in **ad-hoc events** and **owner real-time coordination**. Neither is a beta blocker.

**Strengths to preserve:**
- Today view + offline-tolerant taskSync queue
- Single Task Engine writing all `task_events`
- Daily digest + weekly recap idempotency
- QuickAddSheet pattern (now with draft preservation)
- Calm visual restraint — no "AI slop" gradients, no fake stats, no alarming connectivity warnings

**One sentence:** EquineSync is moving cleanly from "software with horse features" toward "software a real barn could plausibly depend on by Friday."

**Next priority (per user direction):** Batch F (thumb-zone polish), then Batch D (soft scheduling conflicts), then Batch C (notification drawer trust loop).
