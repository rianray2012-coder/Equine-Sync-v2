# BRAND_AND_LOGO_GUIDE.md
# EquineSync Brand & Logo Usage Guide

> **This is the authoritative source of truth for EquineSync's visual identity** (palette, typography, logo). Where any other document conflicts, this guide wins. `DESIGN_TOKENS.md` is reconciled to match.

## Brand Identity Overview
**Positioning:** EquineSync is a refined operational platform for modern equestrian care. The brand should communicate operational clarity, calm authority, precision, sophistication, trust, and elevated equestrian culture.

Visual language combines: elite stable aesthetics, refined modern SaaS design, understated luxury, intelligent organization.

**Core Brand Personality** — Quietly powerful · Beautiful but functional · Minimal yet warm · Intelligent without complexity · Premium without arrogance.

## Approved Brand Color System

### Primary Foundation
| Name | Hex | Usage | Emotional purpose |
|---|---|---|---|
| Midnight Graphite | `#232734` | Sidebar bg, hero, navigation, dark UI, footer | Grounding, sophistication, trust |
| Slate Navy | `#2E3550` | Interactive panels, active nav, buttons, dashboard cards, analytics | — |
| Frost White | `#F7F8FA` | App background, forms, light sections, workspace canvas | — |
| Platinum Mist | `#E3E6EB` | Dividers, cards, secondary surfaces, borders, table bg | — |

### Accent System
| Name | Hex | Usage |
|---|---|---|
| Smoky Lilac | `#B8AECF` | Primary accent: buttons, highlights, key metrics, notifications, premium touch-points |
| Frosted Lavender Gray | `#D8D2E3` | Soft hover, background fills, secondary accents, empty states |
| Ice Blue | `#DCEAF4` | Informational UI, charts, operational indicators, data viz |
| Glacier Silver Blue | `#BCC9D6` | Secondary chart elements, inactive states, supporting data |

### Typography Colors
| Name | Hex | Usage |
|---|---|---|
| Rich Charcoal | `#1E2128` | Primary body text, headings, important labels |
| Muted Slate | `#667085` | Supporting text, descriptions, metadata, secondary labels |
| Soft Disabled | `#98A2B3` | Disabled states, placeholders, inactive labels |

### Status Colors
| Name | Hex | Usage |
|---|---|---|
| Success | `#7FA98B` | Muted sage — completed tasks, confirmations, wellness |
| Warning | `#D7B67A` | Soft brass — attention-needed, upcoming care, moderate alerts |
| Critical | `#B46A6A` | Muted oxblood — urgent alerts, health warnings, critical care |

### Gradient System
- **Sidebar:** `#232734 → #2E3550` — sidebar bg, hero panels, premium cards
- **Frost:** `#F7F8FA → #ECEFF4` — dashboard surfaces, cards, modals
- **Lilac Atmosphere:** `#D8D2E3 → #E8E3EF` — premium highlights, onboarding, empty states

## Typography System
- **Primary Display Typeface:** Cormorant Garamond (or Benjamin) — marketing headlines, hero, landing pages, premium statements.
- **Secondary Interface Typeface:** Inter (or Manrope) — dashboard UI, forms, navigation, analytics, data tables.
- **Hierarchy:** Hero headlines = elegant serif SemiBold; Section headers = sans-serif uppercase with tracking; Body = sans-serif Regular; Navigation = sans-serif Medium.

## Logo Usage System
- **Primary Logo:** Horse icon + "EQUINE-SYNC" wordmark + tagline "Every Horse. Every Task. In Sync." — website hero, splash, investor/print/pitch/marketing.
- **Secondary Logo (Horizontal Compact Lockup):** dashboard nav, mobile headers, footer, small-width interfaces.
- **Icon Mark (horse symbol only):** app icon, favicon, notifications, watermarks, social, mobile launch screen. → `assets/brand/equinesync-icon.png`

### Placement Rules
- **Website desktop nav:** upper-left, 48–56px height, min 32px left padding.
- **Dashboard sidebar:** top-left within sidebar.
- **Mobile:** top-center or top-left; compact or icon-only mark.
- **Loading screen:** centered icon mark over Midnight Graphite bg with subtle Slate Navy gradient; optional soft pulse through circuit lines.

## Interface Design Direction
**Dashboard style:** airy, premium, calm, intelligently organized. Avoid cluttered layouts, loud colors, heavy shadows, gradient overuse.

**Card design**
```css
border-radius: 18px;
background: #FFFFFF;
border: 1px solid #E3E6EB;
box-shadow: 0 2px 12px rgba(35,39,52,0.04);
```

**Button system**
- Primary: Slate Navy bg, Frost White text, hover = slight elevation + deepened navy.
- Secondary: white bg, Platinum Mist border, Slate Navy text.
- Accent: Smoky Lilac bg, Midnight Graphite text — use sparingly for premium actions, onboarding, highlighted workflows.

**Navigation**
- Sidebar background: Sidebar Gradient `#232734 → #2E3550`.
- Active item: Smoky Lilac glow, subtle transparency, rounded pill background.

**Motion:** smooth, subtle, elegant; fade transitions, soft hover lifts, gentle panel slides. Avoid bouncing, flashy motion, gaming-style interactions.

## Photography & Imagery Direction
Preferred: cinematic equestrian photography, modern stable architecture, soft luxury, natural movement, emotional connection.
Visual-style prompt keywords: *quiet luxury equestrian, editorial SaaS, modern horse care, calm operational design, premium stable management, soft atmospheric gradients, refined dashboards, high-end equestrian branding.*

## Canonical CSS Variables
```css
:root {
  --es-graphite: #232734;
  --es-navy:     #2E3550;
  --es-white:    #F7F8FA;
  --es-mist:     #E3E6EB;
  --es-lilac:    #B8AECF;
  --es-lavender: #D8D2E3;
  --es-ice:      #DCEAF4;
  --es-silver:   #BCC9D6;
  --es-text:     #1E2128;
  --es-muted:    #667085;
  --es-disabled: #98A2B3;
  --es-success:  #7FA98B;
  --es-warning:  #D7B67A;
  --es-critical: #B46A6A;
}
```

## Brand Asset Folder Structure (target)
```
/assets/brand/
  logos/   primary-logo.svg · compact-logo.svg · icon-only.svg
  colors/  brand-colors.json
  icons/   app-icon.png · favicon.ico
  backgrounds/ sidebar-gradient.png · hero-gradient.png
```
> Currently available in-repo: `docs/assets/brand/equinesync-icon.png` (horse icon mark, PNG 798×568). Other assets to be added as provided.

## Product Experience Goal
The application should ultimately feel like: *"The operating system for horse care which turns the chaos of horse care into calm."* Users should immediately perceive trust, organization, sophistication, emotional calm, and operational mastery. The brand succeeds when users feel: *"This stable is run exceptionally well, and EquineSync makes it possible."*
