# EquineSync — Module Completion Matrix

**Generated:** Feb 19 2026 · **Companion to:** `PRODUCTION_READINESS_TRACKER.md` · `REMAINING_DEPENDENCIES_MAP.md`

> A side-by-side gap analysis. Each module gets a row per criterion. Cells contain the **specific** thing missing (not a generic ✅/❌).

Legend: **✅** ready · **🟡** partial · **❌** missing · **—** not applicable.

---

## Daily / Care Operations

### Auth & Session
| Criterion | Status | Notes |
|---|---|---|
| Backend | ✅ | `routes/auth.py` (login, refresh, refresh-rotation, logout, logout-all, me). |
| Frontend | ✅ | `AuthContext`, `tokens` helper, 401 auto-refresh interceptor. |
| Task-engine integration | — | n/a |
| Notifications | — | Self-notifications would be noisy. |
| Timeline events | — | n/a |
| Analytics events | ✅ | `auth.login_succeeded` not yet tracked — minor add. |
| Mobile optimization | ✅ | Tablet/phone tested. |
| Permissions | ✅ | Role on every request. |
| Testing coverage | ✅ | 20/20 phase-2 tests cover rotation + revocation. |
| Readiness tier | **Production-Ready** | |
| Top remaining gap | | Add per-user "active sessions" view in Settings (P3). |

### Unified Task Engine
| Criterion | Status | Notes |
|---|---|---|
| Backend | ✅ | Templates, tasks, completions, events, RRULE materializer + indexes. |
| Frontend | ✅ | Today view + Feed + Meds + Health upcoming. |
| Task-engine integration | ✅ | This *is* the engine. |
| Notifications | ✅ | TaskEvent → dispatcher. |
| Timeline events | ✅ | Fan-out per subject horse. |
| Analytics | ✅ | `task.completed/skipped/refused` tracked. |
| Mobile | ✅ | Swipe + bulk + offline. |
| Permissions | ✅ | Tenant-scoped queries. |
| Testing | ✅ | 13 pytest cases. |
| Readiness tier | **Production-Ready** | |
| Top remaining gap | | Owners cannot yet *create* templates from Owner Portal. P2 by design. |

### Today View
| Criterion | Status | Notes |
|---|---|---|
| Backend | ✅ | `/tasks/today` urgency grouper. |
| Frontend | ✅ | 6 groups, swipe, bulk, optimistic, sync queue, manual retry. |
| Engine integration | ✅ | |
| Notifications | ✅ | Indirectly via completion fan-out. |
| Timeline | ✅ | |
| Analytics | ✅ | |
| Mobile | 🟡 | iOS 100% vh quirk on small screens — minor. |
| Permissions | ✅ | |
| Testing | ✅ | |
| Tier | **Production-Ready** | |
| Top gap | | Date-picker to look back/forward (presently only "today"). |

### Feed Room
| Criterion | Status | Gap |
|---|---|---|
| Backend | ✅ | Engine-backed via `/tasks?category=feed`. |
| Frontend | ✅ | Morning/Midday/Evening buckets. |
| Engine | ✅ | |
| Notifications | ✅ | Inbox on completion (admin/owners curated). |
| Timeline | ✅ | |
| Analytics | 🟡 | No "missed meal rate per horse" funnel. |
| Mobile | ✅ | |
| Permissions | 🟡 | Any logged-in staff can complete any meal — could constrain to assignee role. |
| Testing | 🟡 | No pytest specifically targeting category=feed; covered by engine tests. |
| Tier | **Beta-Ready** | |
| Top gap | | "Refuse to feed" with reason (e.g. colic suspicion); add `payload_actual.refused_reason`. |

### Medications
| Criterion | Status | Gap |
|---|---|---|
| Backend | ✅ | Engine-backed; `task-templates?category=medication` for prescriptions. |
| Frontend | ✅ | Today doses + Active prescriptions; Refused button maps to outcome=refused. |
| Engine | ✅ | |
| Notifications | ✅ | Skipped/refused medications fan out to admins by default. |
| Timeline | ✅ | |
| Analytics | 🟡 | No "missed dose alert" funnel; could trigger amber banner when 3 misses in 7 days. |
| Mobile | ✅ | |
| Permissions | 🟡 | Same as Feed — any staff can give. Consider locking to assignee or witness. |
| Testing | 🟡 | Engine tests cover; no e2e of "refused → admin notified". |
| Tier | **Beta-Ready** | |
| Top gap | | Withdrawal-period field on medication payload + show warning in profile. |

### Health & Vet
| Criterion | Status | Gap |
|---|---|---|
| Backend | 🟡 | Upcoming via engine; **completion outcomes are not yet attached to vet_records**. |
| Frontend | ✅ | Upcoming card + legacy historical records. |
| Engine | 🟡 | Read-through only; writing back vet visit notes via task `payload_actual` not yet wired. |
| Notifications | 🟡 | Generic completion only; no severity routing. |
| Timeline | 🟡 | Engine events yes; legacy vet records absent from timeline. |
| Analytics | ❌ | No "vet visit booked → completed → follow-up scheduled" funnel. |
| Mobile | 🟡 | Cards work but no swipe action. |
| Permissions | 🟡 | All staff see all records. |
| Testing | 🟡 | List endpoints; no end-to-end flow. |
| Tier | **Internal-Demo-Ready** | |
| Top gap | | Wire vet-task completion → write a `vet_record` row → emit a richer timeline event. |

---

## Operational hub modules

### Today / Barn Board (decision pending)
| Criterion | Status | Gap |
|---|---|---|
| Backend | ✅ legacy | Reads `dashboard/barn-board` from `feed_tasks` + `medication_logs`. |
| Frontend | ✅ | Tablet-optimised. |
| Engine | ❌ | Not wired. |
| Notifications | ❌ | |
| Timeline | ❌ | |
| Analytics | ❌ | |
| Mobile/Tablet | ✅ | |
| Permissions | 🟡 | |
| Testing | ❌ | |
| Tier | **Internal-Demo-Ready** | |
| **Decision needed** | | Either migrate Barn Board to engine (P-A) or retire it and let Today on tablet breakpoint replace it. |

### Dashboard
| Criterion | Status | Gap |
|---|---|---|
| Backend | ✅ legacy | Stats from legacy collections + onboarding progress. |
| Frontend | ✅ | Stat cards + 6 widgets + setup checklist. |
| Engine | ❌ | Stats *should* come from engine for "completion rate today" etc. |
| Notifications | — | |
| Timeline | — | |
| Analytics | 🟡 | Only setup-flow events. |
| Mobile | 🟡 | Some widgets become dense on phone. |
| Permissions | 🟡 | |
| Testing | 🟡 | |
| Tier | **Internal-Demo-Ready** | |
| Top gap | | Migrate `/dashboard/summary` to engine-derived counts (P-A). |

---

## Business modules

### Owner Portal (curated timeline + service requests)
| Criterion | Status | Gap |
|---|---|---|
| Backend | ✅ | Timeline + service-requests. |
| Frontend | ✅ | Picker + day-grouped curated timeline + request form. |
| Engine | ✅ | |
| Notifications | 🟡 | **Owner email digest not yet implemented** (channel exists; default rules empty for owners). |
| Timeline | ✅ | |
| Analytics | 🟡 | No "owner opened portal" event. |
| Mobile | ✅ | |
| Permissions | ✅ | Server-side curated filter. |
| Testing | ✅ | |
| Tier | **Beta-Ready** | |
| Top gaps | | (1) Daily email digest of owner-visible events. (2) Decline service request with reason. |

### Owners
| Criterion | Status | Gap |
|---|---|---|
| Backend | 🟡 | List + create only; no edit/delete; no detail. |
| Frontend | 🟡 | List-only page. |
| Engine | ❌ | No owner-scoped task linkage. |
| Notifications | ❌ | |
| Timeline | ❌ | |
| Analytics | ❌ | |
| Mobile | 🟡 | |
| Permissions | ❌ | Anyone can list. |
| Testing | ❌ | |
| Tier | **Internal-Demo-Ready** | |
| Top gap | | Owner detail page with horses owned, billing history, recent communications. |

### Billing
| Criterion | Status | Gap |
|---|---|---|
| Backend | 🟡 | List + pay; no invoice creation flow; no payment provider integration (Stripe). |
| Frontend | 🟡 | List with `Pay` button (no real Stripe Checkout). |
| Engine | ❌ | Boarding fees are not engine-derived. |
| Notifications | ❌ | |
| Timeline | ❌ | |
| Analytics | ❌ | |
| Mobile | 🟡 | |
| Permissions | 🟡 | |
| Testing | 🟡 | One test exists. |
| Tier | **Internal-Demo-Ready** | |
| Top gap | | Stripe Connect integration (boarding subscriptions); auto-generate invoice from completed boarding+lessons. |

### Lessons
| Criterion | Status | Gap |
|---|---|---|
| Backend | 🟡 | List + create. |
| Frontend | 🟡 | Schedule + roster list. |
| Engine | ❌ | Lessons could be a category; today they're a separate collection. |
| Notifications | ❌ | |
| Timeline | ❌ | |
| Analytics | ❌ | |
| Mobile | 🟡 | |
| Permissions | 🟡 | |
| Testing | ❌ | |
| Tier | **Internal-Demo-Ready** | |
| Top gap | | Booking flow with rider availability, instructor capacity, lesson outcome notes. |

### Training Log
| Criterion | Status | Gap |
|---|---|---|
| Backend | 🟡 | List + post. |
| Frontend | 🟡 | Daily log list. |
| Engine | ❌ | |
| Notifications | ❌ | |
| Timeline | 🟡 | Ride entries do show on HorseProfile via legacy `training` collection. |
| Analytics | ❌ | |
| Mobile | 🟡 | |
| Permissions | ❌ | |
| Testing | ❌ | |
| Tier | **Internal-Demo-Ready** | |
| Top gap | | Mobile-first quick-log form: pick discipline, rating slider, voice-to-text notes. |

### Riders
| Same shape as Owners. **Internal-Demo-Ready.** Top gap: rider detail + progression chart. |

### Messaging
| Criterion | Status | Gap |
|---|---|---|
| Backend | 🟡 | Send + list. No threading, no read receipts, no attachments. |
| Frontend | 🟡 | Send form + inbox. |
| Engine | ❌ | |
| Notifications | ❌ | |
| Timeline | ❌ | |
| Analytics | ❌ | |
| Mobile | 🟡 | |
| Permissions | 🟡 | Visibility scope exists but minimal. |
| Testing | ❌ | |
| Tier | **Prototype** | |
| Top gap | | Decide: build full Messaging OR delegate to native channels (SMS/email). Recommend the latter for P1. |

### Incidents
| Criterion | Status | Gap |
|---|---|---|
| Backend | 🟡 | Create + list. |
| Frontend | 🟡 | Timeline view. |
| Engine | ❌ | Incidents should be `TaskEvent` of type `incident.*`. |
| Notifications | ❌ | |
| Timeline | ❌ | |
| Analytics | ❌ | |
| Mobile | 🟡 | |
| Permissions | ❌ | |
| Testing | ❌ | |
| Tier | **Prototype** | |
| Top gap | | Incident reporting form with horse linkage + photo + severity + auto-notification routing. |

---

## Onboarding & Insights

### Onboarding Wizard
| Criterion | Status | Gap |
|---|---|---|
| Backend | ✅ | 10 steps + CSV preview/commit + autosave + reset. |
| Frontend | ✅ | Sticky stepper + per-step components + shadcn Select. |
| Engine | — | n/a |
| Notifications | — | Nudge emails are separate. |
| Timeline | — | |
| Analytics | ✅ | step_completed, csv_imported, etc. |
| Mobile | 🟡 | Stepper crowds on narrow viewports. |
| Permissions | ✅ | Admin/Manager only. |
| Testing | ✅ | |
| Tier | **Beta-Ready** | |
| Top gap | | Mobile stepper UX; auto-create engine TaskTemplates from feeding/turnout/medication steps. |

### Magic-Link Invites & Nudges
| Criterion | Status | Gap |
|---|---|---|
| Backend | ✅ | Resend integration + hashed tokens. |
| Frontend | ✅ | AcceptInvite + invite list + nudge UI. |
| Notifications | ✅ | Email channel. |
| Analytics | ✅ | invite.sent/resent/accepted/revoked. |
| Mobile | ✅ | |
| Permissions | ✅ | |
| Testing | ✅ | |
| Tier | **Beta-Ready** | |
| Blocker | | Resend sandbox mode → verify domain. |

### Setup-Health Reports
| Criterion | Status | Gap |
|---|---|---|
| Backend | ✅ | Funnel + KPIs + nudge candidates. |
| Frontend | ✅ | KPI cards + funnel chart + invite pipeline. |
| Mobile | 🟡 | Funnel chart squashes <420px. |
| Tier | **Beta-Ready** | |
| Top gap | | Add task-engine adoption KPIs once Phase-A migration lands. |

### Notifications
| Criterion | Status | Gap |
|---|---|---|
| Backend | ✅ | Dispatcher + inbox + email + prefs. |
| Frontend | ✅ | Bell + dropdown + prefs matrix. |
| Engine integration | ✅ | |
| Timeline | — | |
| Analytics | 🟡 | No "notification opened" tracking. |
| Mobile | ✅ | |
| Permissions | ✅ | |
| Testing | ✅ | |
| Tier | **Beta-Ready** | |
| Top gaps | | (1) Web-push channel. (2) Daily-digest mode (vs. one per event). (3) Owner email digest defaults. |

---

## Placeholders (full audit)

| Module | Backend | Frontend | Engine | Action |
|---|---|---|---|---|
| Stall Rest & Rehab | ❌ no dedicated coll | `<Placeholder>` | ✅ category `rehab` exists | **Convert page to engine-filtered view** (P-E1) |
| Turnout & Pastures | ❌ no dedicated coll | `<Placeholder>` | ✅ categories `turnout_in/out` | **Convert page to engine-filtered view** (P-E2) |
| Inventory | 🟡 `/api/inventory` exists from onboarding | `<Placeholder>` | ❌ | **Build inventory UI on top of existing backend** (P-E3) |
| Shows & Competitions | ❌ | `<Placeholder>` | ❌ | Greenfield — defer to post-beta. |
| Documents | ❌ | `<Placeholder>` | ❌ | Blocked on object storage decision. |
| Maintenance | ❌ | `<Placeholder>` | ❌ | Greenfield — defer to post-beta. |
| Staff Management | 🟡 `/api/staff-invites` exists | `<Placeholder>` | ❌ | Build basic roster + workload view post-Phase-D. |

---

## Summary by tier

| Tier | Count | Modules |
|---|---|---|
| Production-Ready | 3 | Auth · Unified Task Engine · Today View |
| Beta-Ready | 8 | Onboarding · Invites · Reports · Notifications · Feed · Medications · Owner Portal · HorseProfile |
| Internal-Demo-Ready | 8 | Dashboard · Barn Board · Health & Vet · Owners · Riders · Lessons · Training · Billing |
| Prototype | 3 | Messaging · Incidents · Service Requests |
| Placeholder | 7 | Stall Rest · Turnout · Inventory · Shows · Documents · Maintenance · Staff |
| **Total** | **29** | |

**~38% of modules** are at Beta-Ready or above. Phase-A → Phase-E (see Roadmap §7 in Tracker) pushes this to **~62%**.
