# Phase 8 — Brand Presence / Logo Integration (forward plan)

> Founder request: **Equine-Sync should have its logo/brand more present across the
> platform.** This is a dedicated Phase 8 effort — it was **NOT** started during 7C-3
> (7C-3 only preserved the existing sidebar logo and confirmed non-regression).

## Approved brand / logo guide
> Source of truth: **`docs/brand/22_Brand_and_Logo_Use_Guide.pdf`** (official Guide 22), saved to the repo.

- **Product name:** Equine-Sync
- **Tagline:** *Every Horse. Every Task. In Sync.*
- **Typography:** Cormorant Garamond (or Benjamin) for display/marketing moments · Inter (or Manrope) for operational UI. Hierarchy: serif SemiBold hero headlines · uppercase-tracked sans section headers · regular sans body · medium sans nav.
- **Feel:** premium, calm, trustworthy, organized, equestrian but not rustic, modern but not cold. Avoid cluttered layouts, loud colors, heavy shadows, gradient overuse.

### Palette (full, per Guide 22)
| Role | Name | Hex |
|---|---|---|
| Foundation | Midnight Graphite | `#232734` (sidebar/hero/nav/dark surfaces) |
| Foundation | Slate Navy | `#2E3550` (panels, active nav, buttons, cards) |
| Foundation | Frost White | `#F7F8FA` (app background, forms, canvas) |
| Foundation | Platinum Mist | `#E3E6EB` (dividers, cards, borders, tables) |
| Accent | Smoky Lilac | `#B8AECF` (primary accent, buttons, highlights, notifications) |
| Accent | Frosted Lavender Gray | `#D8D2E3` (soft hover, fills, empty states) |
| Accent | Ice Blue | `#DCEAF4` (informational UI, charts) |
| Accent | Glacier Silver Blue | `#BCC9D6` (secondary chart, inactive states) |
| Text | Rich Charcoal | `#1E2128` (body/headings) |
| Text | Muted Slate | `#667085` (supporting/metadata) |
| Text | Soft Disabled | `#98A2B3` (disabled/placeholder) |
| Status | Success (sage) | `#7FA98B` |
| Status | Warning | `#D7B67A` |
| Status | Critical | `#B46A6A` |

## Brand assets (saved to `docs/brand/`)
**Icon mark — 8 official color variants** (per the contact sheet, transparent-background PNGs unless noted):
| # | Variant | File | Use |
|---|---|---|---|
| 01 | Midnight Graphite | `01_midnight_graphite_transparent.png` | dark mark on light surfaces |
| 02 | Slate Navy | `02_slate_navy_transparent.png` | navy mark on light surfaces |
| 03 | Smoky Lilac | `03_smoky_lilac_transparent.png` | accent / soft contexts |
| 04 | Graphite + Lilac Tech | `04_midnight_graphite_smoky_lilac.png` | graphite body, lilac circuitry |
| 05 | Slate Navy + Lilac Tech | `05_slate_navy_smoky_lilac.png` | navy body, lilac circuitry |
| 06 | Frost on Midnight | `06_frost_on_midnight.png` | **frost mark on Midnight Graphite block** (dark sidebar/hero) |
| 07 | Frost on Slate | `07_frost_on_slate.png` | **frost mark on Slate Navy block** (panels) |
| 08 | Midnight on Frost | `08_midnight_on_frost.png` | dark mark on Frost White block (light) |

- `EquineSync_Icon.png` — high-res master icon mark.
- `EquineSync_icon_color_variations_contact_sheet.png` — master reference sheet (all 8, named).
- `22_Brand_and_Logo_Use_Guide.pdf` — official Guide 22 (source of truth).

**Variant selection rule of thumb:** Frost-on-Midnight/Slate for our dark sidebar & hero surfaces;
Midnight/Slate/Graphite-on-Frost for light surfaces; Lilac-tech and Smoky-Lilac variants for
accent/premium touch-points. Full set received — **brand asset library is complete.**

## Logo usage & placement (per Guide 22)
- **Primary logo** → website hero, splash, investor/print/pitch/marketing.
- **Secondary compact (horizontal) lockup** → dashboard nav, mobile headers, footer, small widths.
- **Icon mark (horse only)** → app icon, favicon, notifications, watermarks, social, mobile launch.
- **Desktop nav:** upper-left, 48–56px height, ≥32px left padding.
- **Dashboard sidebar:** top-left within sidebar (matches our current header).
- **Loading screen:** centered icon mark over Midnight Graphite (or subtle Slate Navy gradient).
- Pick the logo variant by background (frost-on-dark for Midnight/Slate; midnight-on-frost for light).

## Guardrails (must hold for every surface)
- No full redesign; no unauthorized logo variants.
- Do **not** stretch, crop, recolor, shadow, outline, or distort the logo.
- Do **not** reintroduce old brand colors.
- Preserve accessibility (contrast, focus, alt text), spacing, responsiveness, and all existing functionality.
- This is additive brand presence, not a navigation/IA redesign.

## Logo-presence checklist (surfaces to cover in Phase 8)
- [ ] Main app shell / sidebar (header lockup; collapsed/mobile states)
- [ ] Login screen
- [ ] Onboarding / setup screens
- [ ] Dashboard / home
- [ ] Reports & insights
- [ ] Owner summaries / recaps (digest + weekly recap emails/views)
- [ ] Billing / invoices
- [ ] Tasteful empty / loading states where appropriate
- [ ] Tagline placement where it adds warmth (login, onboarding, empty states) — used sparingly

## Notes / dependencies
- Reconcile with **Tech Debt #11** (dual-palette `equine-ink/*` vs `equine-platinum/*`) — the brand
  palette above should anchor that reconciliation rather than adding a third palette.
- Likely needs an approved logo asset set (SVG, light/dark, monochrome) before implementation.
- Recommend a `design_agent` pass to produce the brand blueprint before coding Phase 8.
