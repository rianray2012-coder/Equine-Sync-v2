# Phase 8 — Brand Presence / Logo Integration (forward plan)

> Founder request: **Equine-Sync should have its logo/brand more present across the
> platform.** This is a dedicated Phase 8 effort — it was **NOT** started during 7C-3
> (7C-3 only preserved the existing sidebar logo and confirmed non-regression).

## Approved brand / logo guide
- **Product name:** Equine-Sync
- **Tagline:** *Every Horse. Every Task. In Sync.*
- **Palette:** Midnight Graphite `#232734` · Slate Navy `#2E3550` · Frost White `#F7F8FA` · Smoky Lilac `#B8AECF`
- **Typography:** Cormorant Garamond for refined display moments · Inter for operational UI
- **Feel:** premium, calm, trustworthy, organized, equestrian but not rustic, modern but not cold

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
