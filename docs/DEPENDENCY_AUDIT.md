# DEPENDENCY_AUDIT.md
# EquineSync — Frontend Dependency Audit (Phase 10D, report-first)

> **Phase 10D dependency audit (2026-06-11).** Addresses Tech Debt #14
> ("dependency bloat"). This is a **report-only** static import scan of
> `frontend/src/**` against `frontend/package.json`. **Nothing was removed or
> upgraded.** Any pruning/upgrade is a **separate, per-item gated** follow-up.

## Method
- Scanned **116** source files (`src/**/*.{js,jsx,ts,tsx}`) for `import`/`require`
  references to each declared dependency, plus a targeted check of build configs
  (`tailwind.config.js`, `craco.config.js`, `postcss.config.js`).
- A dependency is **USED** if any import path matches `"<dep>"` or `"<dep>/…"`.

## Summary
- **38 of 43** runtime dependencies are directly imported in `src/`.
- **2** are build tooling (keep): `react-scripts`, `cra-template`.
- **1** is a Tailwind plugin used via config (keep): `tailwindcss-animate`
  (`tailwind.config.js` → `plugins: [require("tailwindcss-animate")]`).
- **4** have **no import anywhere in `src/`** → removal candidates (below).
- **1 secondary candidate**: `react-hook-form` is imported only by an
  **unused** shadcn boilerplate component.

## Removal candidates (NOT removed — proposal only)
| Package | Finding | Risk if removed | Recommendation |
|---|---|---|---|
| `recharts` | No import in `src/`. No charts implemented yet. | None found. | Safe to remove **unless** charting is on the near-term roadmap (Reporting phase) — then keep intentionally. |
| `date-fns` | No import in `src/`. Date UI uses `react-day-picker` directly. | None found. | Likely safe to remove. |
| `zod` | No import in `src/`. No schema validation in use. | Pairs with `@hookform/resolvers`. | Remove together with the two below, or keep if form-validation is planned. |
| `@hookform/resolvers` | No import in `src/`. | Bridges `zod` ↔ `react-hook-form`. | Remove with `zod` (+ see `react-hook-form`). |

## Secondary candidate (deeper review needed)
| Package | Finding | Recommendation |
|---|---|---|
| `react-hook-form` | Imported **only** by `src/components/ui/form.jsx`, which is **not consumed by any page/component**. | If forms use plain controlled inputs (current pattern), `react-hook-form` + `ui/form.jsx` + `@hookform/resolvers` + `zod` form a removable cluster. Confirm no upcoming form-heavy feature before pruning. |

## Confirmed keep (directly imported in `src/`)
- All `@radix-ui/*` (28), `axios`, `class-variance-authority`, `clsx`, `cmdk`,
  `embla-carousel-react`, `input-otp`, `lucide-react`, `next-themes`, `react`,
  `react-dom`, `react-day-picker`, `react-resizable-panels`, `react-router-dom`,
  `sonner`, `tailwind-merge`, `vaul`.
- Tooling/config (kept, not `src/` imports): `react-scripts`, `cra-template`,
  `tailwindcss-animate`.

> `recharts` is **not** in this list — it has no `src/` import and is a removal
> candidate (see the table above).

## Proposed (gated) follow-up
A single optional pruning PR could drop the cluster
`recharts`, `date-fns`, `zod`, `@hookform/resolvers`, `react-hook-form`
(+ delete the unused `src/components/ui/form.jsx`) **only after**:
1. per-item approval, and
2. confirming none are on the near-term roadmap (Reporting/charts, form validation),
3. a clean `yarn build` + frontend smoke test post-removal.

**No action taken in 10D.** This document is the record; pruning remains
separately gated.
