# EquineSync — Master Documentation Index

This folder (`/app/docs`, i.e. the project-root `/docs`) contains the **governing documents** for EquineSync. Before making major changes, read the relevant documents below.

> **Path note:** The canonical source-of-truth location is the project-root `/docs`. In this Emergent workspace the project root is `/app`, so the physical path is `/app/docs`. Tooling and the start prompt should treat `/app/docs` == `/docs`.

---

## Product Strategy
- [`PRODUCT_VISION.md`](./PRODUCT_VISION.md)
- [`OWNER_TRUST_FRAMEWORK.md`](./OWNER_TRUST_FRAMEWORK.md)
- [`FEATURE_ROADMAP.md`](./FEATURE_ROADMAP.md)

## Engineering Governance
- [`ENGINEERING_RULES.md`](./ENGINEERING_RULES.md)
- [`ARCHITECTURE.md`](./ARCHITECTURE.md)
- [`DATA_MODEL.md`](./DATA_MODEL.md)
- [`API_CONTRACTS.md`](./API_CONTRACTS.md)
- [`SCHEMA_CHANGE_POLICY.md`](./SCHEMA_CHANGE_POLICY.md)
- [`API_VERSIONING.md`](./API_VERSIONING.md)

## AI Development
- [`AI_CODING_PROMPTS.md`](./AI_CODING_PROMPTS.md)
- [`KNOWN_TECH_DEBT.md`](./KNOWN_TECH_DEBT.md)
- [`DECISION_LOG.md`](./DECISION_LOG.md)

## UX & Design
- [`UI_SYSTEM.md`](./UI_SYSTEM.md)
- [`DESIGN_TOKENS.md`](./DESIGN_TOKENS.md)
- [`BRAND_AND_LOGO_GUIDE.md`](./BRAND_AND_LOGO_GUIDE.md)
- [`WORKFLOW_MAPS.md`](./WORKFLOW_MAPS.md)

## Operations
- [`RELEASE_CHECKLIST.md`](./RELEASE_CHECKLIST.md)
- [`INCIDENT_RESPONSE.md`](./INCIDENT_RESPONSE.md)
- [`ONBOARDING_GUIDE.md`](./ONBOARDING_GUIDE.md)

## Process Reference
- [`EMERGENT_START_PROMPT.md`](./EMERGENT_START_PROMPT.md)
- [`PHASED_EXECUTION_PLAN.md`](./PHASED_EXECUTION_PLAN.md)

## Brand Assets
- `assets/brand/equinesync-icon.png` — official horse icon mark (PNG, 798×568).

---

# Required Reading by Task Type

## New Feature
- `PRODUCT_VISION.md`
- `ENGINEERING_RULES.md`
- `DATA_MODEL.md`
- `API_CONTRACTS.md`
- `FEATURE_ROADMAP.md`

## Refactor
- `ENGINEERING_RULES.md`
- `ARCHITECTURE.md`
- `KNOWN_TECH_DEBT.md`
- `DATA_MODEL.md`

## UI Work
- `UI_SYSTEM.md`
- `DESIGN_TOKENS.md`
- `BRAND_AND_LOGO_GUIDE.md`
- `OWNER_TRUST_FRAMEWORK.md`

## Permission Work
- `ROLE_PERMISSION_MATRIX.md`
- `ENGINEERING_RULES.md`
- `API_CONTRACTS.md`

## Owner Portal Work
- `OWNER_TRUST_FRAMEWORK.md`
- `PRODUCT_VISION.md`
- `ROLE_PERMISSION_MATRIX.md`
- `UI_SYSTEM.md`

## Billing Work
- `DATA_MODEL.md`
- `API_CONTRACTS.md`
- `ROLE_PERMISSION_MATRIX.md`
- `OWNER_TRUST_FRAMEWORK.md`

---

## Authoritative-source notes (conflict resolution)

1. **Design palette / brand:** `BRAND_AND_LOGO_GUIDE.md` is the **authoritative** source of truth for the visual palette and typography. Where it conflicts with an older palette, the Brand Guide wins. `DESIGN_TOKENS.md` has been **reconciled** to match the Brand Guide (Midnight Graphite / Slate Navy / Frost White / Smoky Lilac; Cormorant Garamond display + Inter UI). The earlier "Warm Ivory / Saddle Brown / Muted Gold" palette is **deprecated** and must not be used unless explicitly reintroduced later as a secondary seasonal/accent palette.

2. **Tech debt:** `KNOWN_TECH_DEBT.md` is **code-grounded** — every item references the actual file/line where it was observed (as of the Phase 1 documentation pass).

3. **Architecture (target vs current):** `ARCHITECTURE.md` describes the **target** modular structure. The **current** backend does not yet match it (logic concentrated in `server.py` + `routes/`). Gaps are tracked in `KNOWN_TECH_DEBT.md` and sequenced in `PHASED_EXECUTION_PLAN.md`.
