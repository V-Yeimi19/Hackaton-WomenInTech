---
name: Vibrant Peer-to-Peer Fintech
colors:
  surface: '#fff7ff'
  surface-dim: '#e0d7e3'
  surface-bright: '#fff7ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#faf1fc'
  surface-container: '#f4ebf7'
  surface-container-high: '#eee5f1'
  surface-container-highest: '#e8e0eb'
  on-surface: '#1e1a22'
  on-surface-variant: '#4f434f'
  inverse-surface: '#332f37'
  inverse-on-surface: '#f7eef9'
  outline: '#817380'
  outline-variant: '#d3c1d0'
  surface-tint: '#8d3b9c'
  primary: '#59006a'
  on-primary: '#ffffff'
  primary-container: '#742284'
  on-primary-container: '#f196fd'
  inverse-primary: '#f7acff'
  secondary: '#006a63'
  on-secondary: '#ffffff'
  secondary-container: '#56faeb'
  on-secondary-container: '#007169'
  tertiary: '#680036'
  on-tertiary: '#ffffff'
  tertiary-container: '#91004d'
  on-tertiary-container: '#ff99bb'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffd6ff'
  primary-fixed-dim: '#f7acff'
  on-primary-fixed: '#350040'
  on-primary-fixed-variant: '#722082'
  secondary-fixed: '#56faeb'
  secondary-fixed-dim: '#28ddcf'
  on-secondary-fixed: '#00201d'
  on-secondary-fixed-variant: '#00504a'
  tertiary-fixed: '#ffd9e2'
  tertiary-fixed-dim: '#ffb0c9'
  on-tertiary-fixed: '#3e001e'
  on-tertiary-fixed-variant: '#8e004b'
  background: '#fff7ff'
  on-background: '#1e1a22'
  surface-variant: '#e8e0eb'
typography:
  headline-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 40px
    fontWeight: '800'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '800'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 22px
    fontWeight: '700'
    lineHeight: 30px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '500'
    lineHeight: 24px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '700'
    lineHeight: 18px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.03em
  display-amount:
    fontFamily: Plus Jakarta Sans
    fontSize: 48px
    fontWeight: '800'
    lineHeight: 52px
    letterSpacing: -0.03em
  display-amount-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 36px
    fontWeight: '800'
    lineHeight: 42px
    letterSpacing: -0.03em
rounded:
  sm: 0.5rem
  DEFAULT: 1rem
  md: 1.5rem
  lg: 2rem
  xl: 3rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-tablet: 1.5rem
  gutter-desktop: 2rem
  margin: 1rem
  margin-tablet: 2rem
  margin-desktop: 3rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system delivers an energetic, approachable, and frictionless peer-to-peer mobile payments experience. Rooted in daily community commerce, street-level microtransactions, and instant digital transfers, the interface projects unquestioned financial security wrapped in a vibrant, friendly persona.

### Design Philosophy
- **Dynamic Tactility:** Micro-interactions, soft pill controls, and vibrant accent badges transform mundane ledger actions into celebratory exchanges.
- **Immediate Clarity:** Transaction amounts, QR target points, and recipient confirmations dominate the viewport with high legibility to eliminate transfer anxiety.
- **Ergonomic Speed:** All critical transaction vectors (sending money, scanning QR codes, switching payment methods) are concentrated within bottom-sheet thumb zones for single-handed mobile operation.
- **Approachability:** Soft, hyper-rounded geometry paired with punchy cyan and magenta accents dissolves the clinical intimidation typical of legacy banking.

## Colors

The palette is engineered for instant visual brand recall, high daylight legibility at street kiosks, and clear functional hierarchy.

### Role Assignments
- **Primary (`#742284` & `#872b98`):** Anchors brand ownership, primary navigation bars, primary action buttons, key status headers, and active state fills.
- **Secondary (`#00D2C4` & `#00B4A7`):** The functional engine of the app. Powers success confirmation screens, high-visibility QR camera target reticles, live balance callouts, and floating action prompts.
- **Tertiary (`#E6007E`):** Magenta highlight reserved for promotional tags, micro-rewards, alert badges, and urgent validation moments.
- **Neutral Surface Palette:**
  - Canvas base: Warm white (`#FBF9FC`) to soften screen glare.
  - Surface cards: Neutral crisp white (`#FFFFFF`) with ultra-subtle cool gray borders (`#EDE8F0`) and light lavender-tinted gray (`#F3EEF6`) for nested sub-cards.
  - Text & Glyphs: Rich deep violet-charcoal (`#1E1A22`) for body and titles; muted plum-gray (`#6E6575`) for secondary metadata and timestamps.

## Typography

The type system uses **Plus Jakarta Sans** uniformly across all tiers to balance contemporary geometric precision with warm, friendly aperture curves.

### Typography Guidelines
- **Financial Figures (`display-amount`):** Numerical amounts must always render with tabular lining figures and bold tracking (`-0.03em`), ensuring digits do not jump horizontally during live-typing or balance updates.
- **Currency Symbols:** Currency signs (e.g., S/ or $) render at 65% scale relative to the headline amount and align to the cap height.
- **Readability & Weight Hierarchy:** Headlines rely on extra-bold (`800`) cuts to cut through visual noise in outdoor light. Transaction histories and metadata switch down to medium (`500`) and regular (`400`) weights to preserve scan speed.

## Layout & Spacing

A mobile-first 4-column layout governs compact viewports, scaling to 8 columns on tablet and 12 columns on desktop web viewports. 

### Grid & Form Factor Rules
- **Mobile Handset (< 600px):** 4 fluid columns with `1rem` outer margins and `1rem` column gutters. Critical interactive buttons and bottom sheets stick to safe-area bottoms with a minimum thumb clearance zone of `56px` above the home bar.
- **Tablet (600px - 1024px):** 8 fluid columns with `2rem` outer margins. Transaction views convert to centered modal bottom sheets with a maximum width of `480px`.
- **Desktop (> 1024px):** 12 fluid columns constrained within a maximum application shell width of `1120px`, centering the ledger dashboard while keeping QR management cards docked.
- **Spacing Rhythm:** Structured on a rigorous 4px baseline, where component padding strictly employs `space-xs` (4px), `space-sm` (8px), `space-md` (16px), `space-lg` (24px), and `space-xl` (32px).

## Elevation & Depth

Visual depth combines warm purple-tinted ambient drop shadows, crisp border definition, and clear surface layering to prevent muddy contrasts.

### Layering Rules
- **Level 0 (Canvas):** Flat base `#FBF9FC` without elevation.
- **Level 1 (Card & List Elements):** Pure white `#FFFFFF` surface resting on a soft perimeter shadow: `0px 4px 16px -2px rgba(116, 34, 132, 0.06)`, with a structural 1px ghost border (`#EDE8F0`).
- **Level 2 (Active Cards & Floating Chips):** Elevated white surface: `0px 8px 24px -4px rgba(116, 34, 132, 0.12)`, used for wallet switchers and transaction receipts.
- **Level 3 (Sticky Action Bars & Modals):** Top sheets and bottom draw-panels: `0px -4px 32px 0px rgba(30, 26, 34, 0.08)`, anchored by solid backplates to maintain continuous thumb control.
- **Level 4 (Scan Reticle & Primary CTA Glow):** Key actions like the central QR scan trigger and the primary payment button carry an energetic ambient glow: `0px 6px 20px 0px rgba(0, 210, 196, 0.35)`.

## Shapes

The design system adopts a pill-shaped (`3`) structural radius. 

### Corner Radius System
- **Pill Elements (`rounded-full` / 9999px):** All interactive buttons, status tags, wallet selector badges, category chips, and search bars use fully pill-shaped terminations.
- **Large Surfaces (`rounded-xl` / 48px):** Modal top corners, sheet overlays, and prominent card headers use generous 32px–48px curves to retain the friendly, tactile nature of the brand.
- **Cards & Input Enclosures (`rounded-lg` / 24px - 32px):** Standard balance containers, QR frames, and input containers maintain pronounced rounded corners to avoid harsh visual edges.

## Components

### Buttons
- **Primary CTA:** Full-width pill (`height: 52px`), solid deep purple (`#742284`), text in white (`#FFFFFF`) `label-lg`, with active state shifting to `#872B98`. Elevated on key screens with a turquoise accent badge or cyan glowing micro-shadow.
- **Secondary CTA:** Vibrant cyan fill (`#00D2C4`) with neutral dark violet text (`#1E1A22`), used for direct transfer executions and instant QR triggers.
- **Ghost/Tertiary:** Transparent fill with a 1.5px border in `#742284` and purple label, or borderless light purple wash (`#F3EEF6`) with dark purple text.

### QR Components & Indicators
- **QR Viewfinder:** Centered square viewport with 32px rounded corners, bounded by a 4px thick vibrant cyan (`#00D2C4`) targeting stroke with animated corner brackets.
- **QR Action Badge:** Floating pill button situated at bottom center containing the cyan QR icon accompanied by high-contrast label typography.

### Wallet Chips & Badges
- **Wallet Account Chips:** Pill-shaped badge with light gray background (`#F3EEF6`), housing a leading circular avatar or card brand icon, balance snippet, and a chevron. 
- **Notification & Status Chips:** Fully pill-shaped containers with 12px horizontal padding. Success chips pair `#00D2C4` at 15% opacity with dark teal text (`#007B72`). Promo and instant-deal chips feature tertiary magenta (`#E6007E`) with crisp white text.

### Cards & Transaction Lists
- **Balance Card:** Elevated white container with a deep purple gradient bleed or full purple surface. Prominent numerical balance rendered using `display-amount`, coupled with secondary action pills (e.g., "Transfer", "Request").
- **Transaction Rows:** Clean flat row layout separated by 8px gaps inside cards (not full hairline dividers). Left avatar circle (44px) with subtle background tint, central two-line vertical stack (Recipient/Vendor + Date/Hour), and right-aligned bold amount (green/cyan for incoming, dark violet for outgoing).

### Input Fields & Keypads
- **Amount Input:** Borderless centered input utilizing `display-amount-mobile` with static currency denominator (`S/`). Focus state indicated by a pulsing turquoise underline bar (`height: 3px`).
- **Standard Inputs:** Pill-shaped or 20px rounded enclosures with warm white backgrounds (`#FFFFFF`), light border (`#EDE8F0`), and focused border transition to `#742284` (2px thickness). No square corner controls.
- **Custom Pin / NumPad:** Oversized circular digits (64px) with tap feedback in light purple tint (`#F3EEF6`), avoiding harsh grid lines.

### Checkboxes & Radios
- **Checkboxes:** 22px rounded squares (8px border-radius) with 2px stroke in `#742284`. Checked state filled with primary purple containing a bold white checkmark.
- **Radio Buttons:** Concentric circles; active state displays a 22px purple boundary containing an 11px solid cyan (`#00D2C4`) centered core.