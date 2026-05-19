# EquineSync — Remaining Dependencies Map

**Generated:** Feb 19 2026 · **Companion to:** `PRODUCTION_READINESS_TRACKER.md` · `MODULE_COMPLETION_MATRIX.md`

> This map shows what depends on what. If you ship items out of order, you'll create rework. Read it before sequencing the next backlog grooming.

---

## 1 · Critical-Path Graph (text form)

```
                              ┌────────────────────────────────────────┐
                              │      UNIFIED TASK ENGINE (✅ live)     │
                              │  templates · tasks · completions · evts│
                              └──────────────┬─────────────────────────┘
                                             │
                ┌────────────────────────────┼─────────────────────────┐
                ▼                            ▼                         ▼
       ┌────────────────┐          ┌─────────────────┐         ┌──────────────┐
       │ NOTIFICATIONS  │          │   TIMELINES     │         │  ANALYTICS   │
       │   (✅ live)    │          │    (✅ live)    │         │   (🟡 P-B)   │
       └────┬───────────┘          └─────┬───────────┘         └──────┬───────┘
            │                            │                            │
   ┌────────┴──────┐           ┌─────────┴──────────┐         ┌───────┴────────┐
   ▼               ▼           ▼                    ▼         ▼                ▼
EMAIL DIGEST  WEB PUSH   HORSE TIMELINE       STAFF FEED   FUNNELS       WELLNESS
  (🟡 P-C)    (❌ P-3)   (✅ live)            (✅ live)   (🟡 P-B)      AI (❌ P-3)

       ┌──────────────── ENGINE DEPENDS ON ─────────────────┐
       ▼                                                    ▼
RRULE library (✅ python-dateutil)                Mongo collections + indexes (✅)
       ▼                                                    ▼
Materializer loop (✅ live)                         Idempotency contract (✅ live)
```

---

## 2 · Migration Dependencies — what is downstream of what

### A. Legacy → Engine migration (Phase-A)

```
    legacy `feed_tasks`            legacy `medication_logs`
            ▼                              ▼
   /dashboard/summary widgets    /dashboard/barn-board
            ▼                              ▼
       Dashboard.jsx                  BarnBoard.jsx
            │                              │
            └──── BLOCKED BY ────► engine-derived dashboard counts
                                          │
                                          ▼
                                Phase-A migration tasks:
                                  1. Implement `GET /tasks/stats?day=…`
                                  2. Switch Dashboard to it
                                  3. Switch BarnBoard to engine query
                                  4. Stop writing to legacy collections
                                  5. After 2 weeks, drop legacy indexes
```

**Why this order matters:** Both UI pages read from the legacy summaries. If you drop the collections before swapping the reads, the dashboard goes blank. The two-week dual-write window gives you a safe rollback path.

### B. Vet/Health completion loop (Phase-B)

```
Engine vet/farrier tasks
         │
         ▼
Task completion with payload_actual = { notes, follow_up_due, cost }
         │
         ├────► creates a vet_record row (new write path)
         │              │
         │              ▼
         │      Visible in legacy "vet records" tab
         │
         └────► emits richer task.completed event
                        │
                        ▼
                Owner Portal curated timeline shows
                "Spring vaccines completed — next due …"
```

**Blocks:** Vet visit history is currently split (engine future visits / legacy past visits). Phase-B unifies them.

### C. Owner trust loop (Phase-C)

```
Owner email digest
   ▲
   │ requires
   ▼
Resend verified-domain (BLOCKER B1)
   ▲
   │ requires
   ▼
Pick + register `mail.equinesync.com` (or similar)
   ▲
   │ then
   ▼
Set `EMAIL_FROM_OWNER_DIGEST` env var
   ▲
   │ then
   ▼
Implement `notifications.daily_digest(user_id)` writer
   ▲
   │ then
   ▼
Schedule a 7 AM cron task in barn TZ
```

**Risk if order ignored:** Without domain verification, all digest emails bounce in production.

### D. Object storage (Phase-D)

```
Photo/document upload UI
   ▲ requires
   ▼
Signed upload URL endpoint (`POST /uploads/sign`)
   ▲ requires
   ▼
Storage provider decision  ←── BLOCKER B5
   │
   ▼
Possible providers:
  - Emergent-managed storage (preferred — least ops burden)
  - Cloudflare R2 (cheap egress)
  - AWS S3 (standard)
   ▲ requires
   ▼
Bucket + IAM policy + signed-URL service
   ▲ then
   ▼
Backend service: `services/storage.py` with sign() + verify_callback()
   ▲ then
   ▼
Engine completion model extended: `payload_actual.media_ids = [...]`
   ▲ then
   ▼
Frontend upload widget (drag/drop on desktop, camera on mobile)
   ▲ then
   ▼
Unlocks: Documents · Horse photos · Injury photos · Vet receipts
```

### E. Placeholder subsumption (Phase-E)

```
Engine categories already covering:
   rehab        ─►  Stall Rest & Rehab page = filtered Today
   turnout_*    ─►  Turnout & Pastures page = filtered Today
   (nothing)    ─►  Inventory page = build on existing /api/inventory

No new backend needed. UI work only. ~1 day each.
```

### F. Server refactor (Phase-F)

```
server.py (1,800 LOC)
   │
   ├─► extract routes/dashboard.py   (independent — start here)
   ├─► extract routes/onboarding.py  (touches CSV helpers — careful)
   ├─► extract routes/invites.py     (touches mailer + nudge scheduler)
   ├─► extract routes/reports.py     (depends on `_track`)
   │
   ▼
Per file: ~150 LOC moves, ~20 minutes if methodical.
After extraction: server.py should drop below 700 LOC.
```

**Dependency:** Each extraction must keep tests green between moves. Don't batch them.

---

## 3 · External / Infra Dependencies

| External dep | Status | Used by | Blocker level |
|---|---|---|---|
| Resend API (verified key in env) | ✅ live, ⚠️ sandbox | Invites, nudges, future digests | **B1 — domain verification required** |
| `python-dateutil` (RRULE) | ✅ | Engine materializer | none |
| MongoDB | ✅ | Everything | replica-set required if we ever want change streams |
| Object storage | ❌ not chosen | Documents, photos | **B5 — decision needed** |
| Stripe | ❌ | Billing | Major decision: Connect vs Standard |
| Emergent LLM key | ✅ available | AI Wellness Pulse (deferred) | none |
| Web push (FCM/APNs/VAPID) | ❌ | Mobile notifications | medium |

---

## 4 · Internal Code Dependencies (which files block which work)

| Work item | Files that need touching | Blocked by |
|---|---|---|
| Dashboard → engine migration | `server.py:/dashboard/summary`, `Dashboard.jsx` | Engine analytics endpoint (already exists) |
| Barn Board → engine | `server.py:/dashboard/barn-board`, `BarnBoard.jsx` | Decision: migrate or retire |
| Vet completion → vet_record | `task_engine.py:complete_task`, new `services/vet_writer.py` | none |
| Owner email digest | `notifications.py`, new `services/digest.py`, mailer template | Resend domain (B1) |
| Stall-rest / turnout pages | `pages/StallRest.jsx`, `pages/Turnout.jsx`, route table | none — pure UI |
| Inventory UI | `pages/Inventory.jsx` (new), uses existing `/api/inventory` | none |
| Server refactor (4 modules) | `server.py`, new `routes/*.py` files | none — but do one at a time |
| Photo uploads on completions | `task_engine.py`, `engineTasks.js`, new `lib/uploads.js`, new backend route | B5 (storage decision) |

---

## 5 · Risk / Sequencing Heuristics

1. **Never delete a legacy collection before two weeks of dual-write.** Even if the new path is "live," operational realism means a barn might catch the bug only on day 8 of a billing cycle.
2. **Refactor (Phase-F) is the easiest to break things invisibly.** Always run the full pytest suite between moves. Already established that auth-extraction caused a `load_dotenv` ordering bug — that pattern will likely reappear.
3. **Object storage and Stripe are big-ticket decisions.** Defer until at least 3 boarding barns are beta-ready and asking for them.
4. **Email digests are habit-forming.** Once owners get used to a 7 AM summary, breaking it (e.g., switching providers) erodes trust faster than a missing feature ever did. So pin Resend domain verification first.
5. **Engine adoption is the wedge.** Every operational module not yet on the engine is a future migration bill. Tilt new feature work toward engine integration unless there's a strong reason not to.

---

## 6 · Recommended Next 8-Week Sequence

> Each row is roughly 1 sprint (1 week).

| Wk | Phase | Modules upgraded | Tracker delta |
|---|---|---|---|
| 1 | A1 | Dashboard summary → engine; Barn Board → engine (or retire) | -2 from Internal-Demo, +2 Beta |
| 2 | A2 | Drop legacy `feed_tasks` + `medication_logs` (after 1-week dual-write) | 0 — cleanup |
| 3 | B1 | Vet/Farrier completion → vet_record row + richer event | +1 Beta (Health & Vet) |
| 4 | B2 | Analytics funnels (completion-rate, missed-meal, missed-dose) | +1 across Reports / Feed / Meds → Production-Ready |
| 5 | C1 | Resend domain verify; Owner daily email digest | +1 (Owner Portal → Production-Ready) |
| 6 | F | server.py refactor finish (dashboard, onboarding, invites, reports) | 0 modules, big maintainability win |
| 7 | E1 | Stall Rest & Rehab + Turnout pages built on engine-filtered Today | +2 (Placeholders → Beta) |
| 8 | E2 | Inventory UI on existing `/api/inventory` | +1 (Placeholder → Beta) |

**End of 8 weeks:** Production-Ready 6 · Beta-Ready 11 · Internal-Demo 5 · Prototype 3 · Placeholder 4.

---

## 7 · "Don't Build These Next" — anti-priorities

To keep the platform focused on operational realism, the following are explicitly **deferred** until a real beta barn requests them:

- Shows & Competitions module (greenfield, no operational urgency)
- Documents module (blocked on storage; can wait)
- Maintenance module (low-frequency events; out-of-band tools work fine)
- Staff Management (workload/cert tracking — not P0 for a single-barn operator)
- AI Wellness Pulse (powerful but premature without 30+ days of engine data per horse)
- Web push notifications (in-app inbox is sufficient for now)
- Dark mode (deferred; scaffolding in place)
- Custom RRULE editor in UI (presets cover 95% of cases)

Resist building these even if they sound exciting in a sprint planning meeting. Operational realism is harder and more valuable.
