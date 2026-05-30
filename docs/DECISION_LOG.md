# DECISION_LOG.md
# Decision Log

## Purpose
Track important architectural and product decisions. Document: decision, reason, risks, alternatives considered, review date.

## Template
```
Date:
Decision:
Reason:
Alternatives Considered:
Risks:
Review Date:
Status:
```

---

## Entries

### 2026-05-30 — Use MongoDB for initial scaling
- **Decision:** Use MongoDB as the primary datastore for the initial platform.
- **Reason:** Flexible schema during rapid product development and growth.
- **Alternatives Considered:** PostgreSQL (relational).
- **Risks:** Complex reporting and relational joins later (see `KNOWN_TECH_DEBT.md` → "Scaling MongoDB Relationships").
- **Review Date:** 2027-Q1
- **Status:** Active

### 2026-05-30 — Brand Guide is the authoritative visual source of truth
- **Decision:** `BRAND_AND_LOGO_GUIDE.md` (Brand Guide 22) is the single source of truth for palette and typography. `DESIGN_TOKENS.md` reconciled to match: Midnight Graphite `#232734`, Slate Navy `#2E3550`, Frost White `#F7F8FA`, Smoky Lilac `#B8AECF`; Cormorant Garamond (display) + Inter (UI); identity line "Every Horse. Every Task. In Sync."
- **Reason:** The earlier `DESIGN_TOKENS.md` (Warm Ivory / Saddle Brown / Muted Gold) conflicted with the Brand Guide and UI System. One authoritative palette is required before any UI work.
- **Alternatives Considered:** Keeping the Warm Ivory/Saddle Brown palette; merging the two.
- **Risks:** Live frontend currently uses a sibling palette and will need reconciliation in Phase 8 (UI). The deprecated warm palette may be reintroduced later only as an explicit secondary seasonal/accent palette.
- **Review Date:** Phase 8 (Mobile/UI optimization)
- **Status:** Active

### 2026-05-30 — Governance docs live at project-root /docs (/app/docs)
- **Decision:** The in-repo source-of-truth documentation lives at the project-root `/docs`, physically `/app/docs` in this Emergent workspace. `MASTER_INDEX.md` and `EMERGENT_START_PROMPT.md` note the path equivalence.
- **Reason:** Matches the Start Prompt's `/docs` reference; the existing `/app/memory` folder holds historical founder-beta artifacts and is retained for reference.
- **Alternatives Considered:** Consolidating into `/app/memory`.
- **Risks:** Two doc locations (`/app/docs` governance vs `/app/memory` history) — mitigated by `MASTER_INDEX.md` being the single entry point.
- **Review Date:** Phase 10
- **Status:** Active

### 2026-05-30 — Phase 1 is documentation-only (no runtime changes)
- **Decision:** The Phase 1 governance pass creates/reconciles documentation and saves brand assets only. No backend or frontend runtime behavior is changed.
- **Reason:** Establish a checkable source of truth before any code changes (Security Phase 2 next), per user directive.
- **Risks:** None to runtime; identified code gaps remain open until their sequenced phases.
- **Review Date:** Start of Phase 2
- **Status:** Active
