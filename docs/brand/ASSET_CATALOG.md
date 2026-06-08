# Equine-Sync — Official Brand Asset Catalog (Phase 8, step 8A pre-blueprint)

> Scope: catalogs **only** the official assets currently sitting in `/app/docs/brand/`.
> Source of truth for usage rules: **`22_Brand_and_Logo_Use_Guide.pdf`** (Guide 22).
> Status: documentation only — **no code, no asset bundling into the app yet.**

## 0. Headline findings (read first)

1. **Every standalone asset on disk is the ICON-ONLY horse mark** (a running horse built
   from clean outlines + lilac/grey "tech" circuitry lines). 8 color variants + 1 master +
   1 contact sheet.
2. **No lockup asset files exist on disk.** The Guide 22 PDF *illustrates* the
   Primary Horizontal, Stacked, Wordmark-only, Simplified small-size, Badge/Seal, and
   Tagline lockups (sections 1, 2, 4, 5, 8, 9, 10) — but **none of those lockups are
   present as standalone PNG/SVG files.** Implication: the **"Equine-Sync" wordmark must be
   composed in the app (CSS/markup)** — "Equine-" in ink/frost + "Sync" in Smoky Lilac —
   paired with the icon PNG, OR a wordmark/lockup asset must be exported before any
   lockup-dependent surface ships.
3. **No SVG files** — all marks are **raster PNG at 798×568** (icon art occupies a
   landscape frame). For crisp small sizes (favicon 16–48px) and retina, an **SVG export
   or a high-res square-cropped PNG set is recommended** (documented as a follow-up, not
   blocking 8A).
4. **No frost-on-transparent icon exists.** The frost (white) horse only ships *baked onto
   a solid block* (06 on Midnight, 07 on Slate). The transparent variants (01–05) are all
   **dark/colored** marks meant for light surfaces. **Gap for the dark sidebar/hero** —
   resolved either by (a) using the 06/07 block as a contained tile, or (b) exporting a
   frost-on-transparent icon. Flagged for the 8A blueprint to decide.

---

## 1. Icon-only marks — transparent (for LIGHT surfaces)

| File | Variant type | Mark color | Background | Intended use (Guide 22) | Recommended app surfaces |
|---|---|---|---|---|---|
| `01_midnight_graphite_transparent.png` | Icon-only | Midnight Graphite `#232734` horse | **Transparent** | Dark mark on light surfaces | Light headers, **invoices/billing** header, **reports** header, light empty/loading states, light email headers |
| `02_slate_navy_transparent.png` | Icon-only | Slate Navy `#2E3550` horse | **Transparent** | Navy mark on light surfaces | Alt for light surfaces where navy reads better than graphite (panels, cards) |
| `03_smoky_lilac_transparent.png` | Icon-only | Smoky Lilac `#B8AECF` horse | **Transparent** | Accent / soft premium contexts | Accent/premium touch-points, **owner-summary** soft headers, decorative watermark (low-opacity) |
| `04_midnight_graphite_smoky_lilac.png` | Icon-only (2-tone) | Graphite body + **lilac circuitry** | **Transparent** | Premium "tech" expression on light | Premium light moments: **login** (light panel), onboarding hero, marketing/empty states |
| `05_slate_navy_smoky_lilac.png` | Icon-only (2-tone) | Navy body + **lilac circuitry** | **Transparent** | Premium "tech" expression on light | Alt premium light moment where navy preferred |

## 2. Icon-only marks — on solid block (for DARK surfaces / fixed tiles)

| File | Variant type | Mark color | Background (baked-in) | Intended use (Guide 22) | Recommended app surfaces |
|---|---|---|---|---|---|
| `06_frost_on_midnight.png` | Icon-only on tile | **Frost White** horse + lilac lines | **SOLID Midnight Graphite** `#232734` (sampled 35,39,52) | Frost mark on Midnight block | **Dark sidebar header (expanded)**, **sidebar collapsed/mobile tile**, dark hero, **loading screen** (centered over Midnight) |
| `07_frost_on_slate.png` | Icon-only on tile | **Frost White** horse + lilac lines | **SOLID Slate Navy** `#2E3550` (sampled 46,53,80) | Frost mark on Slate block | Dark **panels/cards**, active-nav tile, alt sidebar accent surfaces |
| `08_midnight_on_frost.png` | Icon-only on tile | Midnight Graphite horse | **SOLID Frost White** `#F7F8FA` | Dark mark on Frost block | Light **app-icon/social tile**, light loading card, light favicon source |

> Note: 06/07/08 carry a **baked rectangular block**. They tile cleanly only where the
> surface color matches the block (or where a rounded container intentionally frames the
> tile). They are **not** drop-in transparent marks.

## 3. Master & reference

| File | Type | Background | Use |
|---|---|---|---|
| `EquineSync_Icon.png` | Master icon (high-res) | **SOLID white** `#FFFFFF` (not transparent) | Master source for re-exports; dark horse on white. **Not** drop-in for non-white surfaces. |
| `EquineSync_icon_color_variations_contact_sheet.png` | Reference contact sheet (816×1364) | Frost White | Internal reference only — shows all 8 named variants. **Never** ship the sheet itself. |
| `22_Brand_and_Logo_Use_Guide.pdf` | Brand guide (source of truth) | — | Authoritative rules (palette, lockups, clear space, min sizes, do-nots). |

---

## 4. Lockups documented in Guide 22 but NOT on disk (must be composed or exported)

| Guide 22 section | Lockup | Layout | Where it would be used | Asset status |
|---|---|---|---|---|
| 1. Primary Horizontal | Icon left + "Equine-Sync" wordmark right (+ tagline) | Horizontal | Website hero, splash, marketing, **desktop nav** | **Not on disk** — compose (icon PNG + CSS wordmark) or export |
| 2. Secondary | Horizontal / Stacked / Icon+Text / Icon-only / Tagline lockups (2A–2D) | Various | Dashboard nav, mobile headers, footer | **Not on disk** — compose/export |
| 4. Wordmark-only | "Equine-Sync" text mark (4A Modern Premium primary, 4B–4D) | Text | When icon not needed | **Not on disk** — CSS wordmark ("Sync" in Smoky Lilac) |
| 5. Simplified small-size icon | 5A–5E reduced-detail marks for <48px | Icon | favicon, status bars | **Not on disk** — export simplified favicon set |
| 8/9. App / favicon | 9A Full Horse · 9B Horse Head · 9C Speed-lines · 9D "E-S" monogram | Icon | favicon, iOS/Android app icon | **Not on disk** — export from chosen option |
| 10. Tagline lockups | 10A–10E (incl. Dark Hero) | Various | Reinforcement moments | **Not on disk** — compose/export |

---

## 5. Approved palette (Guide 22) — for reference only (NOT applied in this pass)

> Palette reconciliation is **explicitly out of scope** for this first Phase 8 pass
> (per user decision). Keep current app colors stable. Tracked as **Tech Debt #11 /
> Phase 8 follow-up.** Listed here so logo color choices stay brand-correct.

Foundation: Midnight Graphite `#232734` · Slate Navy `#2E3550` · Frost White `#F7F8FA` · Platinum Mist `#E3E6EB`
Accent: Smoky Lilac `#B8AECF` · Frosted Lavender Gray `#D8D2E3` · Ice Blue `#DCEAF4` · Glacier Silver Blue `#BCC9D6`
Text: Rich Charcoal `#1E2128` · Muted Slate `#667085` · Soft Disabled `#98A2B3`
Status: Success `#7FA98B` · Warning `#D7B67A` · Critical `#B46A6A`

Color application (Guide 22 §"Color Application Rules"):
- **On light:** horse = Midnight Graphite / Slate Navy · tech lines = Smoky Lilac / Frosted Lavender Gray · wordmark = Rich Charcoal / Midnight Graphite · "Sync" = Smoky Lilac · tagline = Muted Slate.
- **On dark:** horse = Frost White · tech lines = Smoky Lilac / Frosted Lavender Gray · wordmark = Frost White · "Sync" = Smoky Lilac · tagline = Frost White / Glacier Silver Blue.

---

## 6. Brand-guide restrictions (apply to EVERY surface)

- **Do NOT** stretch, distort, skew, or rotate the logo.
- **Do NOT** add shadows, glows, gradients, or effects to the mark.
- **Do NOT** recolor outside the approved palette.
- **Do NOT** use the **detailed** icon at very small sizes — switch to a **simplified small-size icon (§5)** under ~48px.
- **Do NOT** use western/rustic/unrelated styling.
- **Clear space** = height of the capital "E" in the wordmark around the logo.
- **Minimum sizes (Guide 22):** Primary horizontal w/ tagline ≥220px · w/o tagline ≥160px · Stacked w/ tagline ≥180px · w/o ≥140px · Icon-only (detailed) ≥48px · Wordmark-only ≥120px · Badge/Seal ≥96px · **Favicon ≥16px** · **App icon ≥180px**.
- Preserve accessibility (contrast WCAG AA, focus states, alt text), spacing, responsiveness, and **all existing functionality**. Additive brand presence only — **no IA/navigation redesign.**

---

## 7. Surface → recommended asset quick map (proposed; blueprint will finalize)

| Surface | Recommended asset | Rationale |
|---|---|---|
| Sidebar header (expanded, dark) | `06_frost_on_midnight` **(or** a future frost-on-transparent export**)** + CSS wordmark | Frost mark reads on dark; wordmark composed |
| Sidebar collapsed / mobile (dark) | `06_frost_on_midnight` framed tile, or §9 simplified icon | Needs simplified mark at small width |
| Login | `04`/`05` (light premium panel) or `06` on dark panel | Premium "tech" moment; pick by panel bg |
| Onboarding / setup | `04` or `01` per panel bg + tagline | Warm, premium first-run |
| Dashboard / home | `01` (light) header lockup | Light surface |
| Reports & insights | `01` (light) | Light surface |
| Owner summaries / recaps | `03` soft / `01` | Calm, owner-facing |
| Billing / invoices | `01` (light) | Light surface, professional |
| Favicon / app icon | **export from §9** (9A/9B/9D) — none on disk | Detailed icon not allowed <48px |
| Empty / loading states | `06` centered on Midnight, or `01` on light | Tasteful brand moment |

> **Open items for the 8A blueprint to resolve:** (a) frost-on-transparent sidebar mark vs.
> framed 06 tile; (b) favicon/app-icon source (export simplified §9 mark); (c) whether a
> single composed horizontal lockup component covers nav + login + emails; (d) SVG/retina
> export plan.
