---
name: Portfolio Copilot
aesthetic: Fiduciary Editorial Desk
colors:
  background: '#f4f6f8'
  on-background: '#0b1320'
  surface: '#f4f6f8'
  surface-bright: '#f9fafb'
  surface-dim: '#dfe5ec'
  surface-variant: '#d5dde6'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#edf1f5'
  surface-container: '#e6ecf2'
  surface-container-high: '#dce4ec'
  surface-container-highest: '#d1dce7'
  on-surface: '#0b1320'
  on-surface-variant: '#475569'
  inverse-surface: '#0f2342'
  inverse-on-surface: '#f4f6f8'
  outline: '#64748b'
  outline-variant: '#d5dde6'
  surface-tint: '#334e68'
  primary: '#0f2342'
  on-primary: '#ffffff'
  primary-container: '#162e54'
  on-primary-container: '#e2eaf6'
  inverse-primary: '#93b4f0'
  primary-fixed: '#1e40af'
  primary-fixed-dim: '#3b5fc0'
  on-primary-fixed: '#ffffff'
  on-primary-fixed-variant: '#dbeafe'
  secondary: '#334e68'
  on-secondary: '#ffffff'
  secondary-container: '#dbeafe'
  on-secondary-container: '#1e3a8a'
  secondary-fixed: '#fef3c7'
  secondary-fixed-dim: '#fde68a'
  on-secondary-fixed: '#92400e'
  on-secondary-fixed-variant: '#78350f'
  tertiary: '#065f46'
  on-tertiary: '#ffffff'
  tertiary-container: '#065f46'
  on-tertiary-container: '#047857'
  tertiary-fixed: '#d1fae5'
  tertiary-fixed-dim: '#a7f3d0'
  on-tertiary-fixed: '#064e3b'
  on-tertiary-fixed-variant: '#047857'
  error: '#b91c1c'
  on-error: '#ffffff'
  error-container: '#fee2e2'
  on-error-container: '#991b1b'
typography:
  # Strict 2-font pairing: Newsreader (editorial display) + Geist (UI & tabular numbers)
  # Strict 3 body sizes (meta, body, heading) + exempt display sizes (brand, page-title, display-figure)
  display-figure:
    fontFamily: Newsreader
    fontSize: clamp(2.125rem, 3.4vw, 3rem)
    fontWeight: '500'
    lineHeight: '1.06'
    letterSpacing: -0.03em
  page-title:
    fontFamily: Newsreader
    fontSize: clamp(1.75rem, 2.5vw, 2.25rem)
    fontWeight: '500'
    lineHeight: '1.15'
    letterSpacing: -0.025em
  brand:
    fontFamily: Newsreader
    fontSize: 1.25rem
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  heading:
    fontFamily: Geist
    fontSize: 1.125rem
    fontWeight: '600'
    lineHeight: '1.35'
    letterSpacing: -0.015em
  body:
    fontFamily: Geist
    fontSize: 0.9375rem
    fontWeight: '400'
    lineHeight: '1.55'
    letterSpacing: '0'
  meta:
    fontFamily: Geist
    fontSize: 0.8125rem
    fontWeight: '500'
    lineHeight: '1.45'
    letterSpacing: '0'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.5rem
  lg: 0.625rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 32px
  panel-split: 5 cols (42%) / 7 cols (58%)
motion:
  easing: cubic-bezier(0.22, 1, 0.36, 1)
  fast: 150ms
  base: 200ms
  progress: 300ms
---

## Brand & Visual Direction

Portfolio Copilot uses a **Fiduciary Editorial Desk** visual language: authoritative, calm, and legible under dense financial review. It combines the typographic composure of an institutional investment memorandum with the immediate clarity of a live governance workbench.

Core principles:
- **Workspace-first opening:** Every route opens directly into live controls, balances, and ledgers with zero marketing hero banners or decorative splash sections.
- **Architectural hairlines over nested card cages:** Content is grouped on crisp pure-white sheets (`#FFFFFF`) over a cool alabaster canvas (`#F4F6F8`), subdivided internally by `1px` structural hairlines (`#D5DDE6`) and quiet recessed bands (`#EDF1F5`) instead of bordered boxes nested inside bordered boxes.
- **Signal without visual noise:** Sections open directly with their `<h1>` or `<h2>`. The UI omits pre-heading eyebrows, tracked-out `ALL CAPS` micro-labels, decorative pills or badges, background watermarks, and synthetic pulsing telemetry dots.
- **State clarity:** Semantic color is reserved strictly for financial or governance state: Deep Forest Emerald for compliance and approvals, Warm Ochre Amber for portfolio drift and pending sign-offs, Oxblood Crimson for policy violations, sells, and destructive actions, and Cobalt Blue for active agent execution and focus rings.

## Color System

All foreground/background pairings meet WCAG AA (`>= 4.5:1`) contrast:

- **Canvas & Sheets:** Architectural Alabaster (`#F4F6F8`) serves as the page canvas, lifting Pure White (`#FFFFFF`) elevated sheets separated by `#D5DDE6` hairlines and `#EDF1F5` recessed bands.
- **Ink:** Deep Maritime Ink (`#0B1320`) for primary copy and figures; Slate Ink (`#475569`) for secondary copy, table headers, and metadata (`> 6.3:1` on both canvas and white sheets).
- **Brand Anchor (Deep Maritime Oxford Navy):** `#0F2342` (`primary`) and `#162E54` (`primary-container`) ground primary actions, active navigation indicators, chart anchors, and the bespoke shield mark.
- **Deliberate Accent (Cobalt Blue):** `#1E40AF` (`primary-fixed`) highlights active agent spinners, secondary chart series, inline links, and `2px` offset focus-visible rings.
- **Compliance & Approval (Deep Forest Emerald):** `#065F46` (`tertiary`) for Approve Trade CTAs; `#047857` (`on-tertiary-container`) for positive deltas and completed pipeline steps; `#D1FAE5` / `#064E3B` (`tertiary-fixed` / `on-tertiary-fixed`) for `PASS` and `APPROVED` status indicators.
- **Drift & Caution (Warm Ochre Amber):** `#FEF3C7` / `#92400E` (`secondary-fixed` / `on-secondary-fixed`) for `PENDING`, `DRIFTED`, rebalance alerts, and high-APR debt notices.
- **Violation & Danger (Oxblood Crimson):** `#B91C1C` (`error`) for sell sides, negative drift, and Reject controls; `#FEE2E2` / `#991B1B` (`error-container` / `on-error-container`) for `VIOLATION`, `REJECTED`, and `FAILED` states.
- **Chart Series Ramp:** `#0F2342` (Maritime Navy), `#1E40AF` (Cobalt), `#047857` (Forest Emerald), `#334E68` (Steel Slate), `#64748B` (Muted Slate).

## Typography

Portfolio Copilot uses a strict **2-font pairing** loaded with `<link rel="preconnect">` from Google Fonts, without loading a third monospace family:

- **Editorial Display (`Newsreader`, optical size 6-72, weights 400-600):** Used exclusively for the navbar brand wordmark (`brand`), page-level `<h1>` titles (`page-title`), and hero monetary totals (`display-figure`) with tight negative display tracking (`-0.02em` to `-0.03em`).
- **UI, Prose & Tabular Figures (`Geist`, weights 400-700):** Used for all navigation, section headings, conversational text, forms, buttons, tables, and numerical data. All dollar amounts, percentages, tickers, timestamps, and timers apply `font-variant-numeric: tabular-nums lining-nums` so columns align vertically without introducing a third font family.

### 3-Size Body Discipline

Below the exempt display tokens (`brand`, `page-title`, `display-figure`), the entire interface locks to **3 consistent font sizes** with zero text smaller than `13px` (`0.8125rem`):

| Token | Size / Line-Height | Usage |
| :--- | :--- | :--- |
| `text-heading` | `1.125rem` (`18px`) / `1.35` | Section headings (`<h2>`, `<h3>`), summary strip metrics |
| `text-body` | `0.9375rem` (`15px`) / `1.55` | Prose, lists, inputs, buttons, nav links, table values (`<= 65ch` for paragraphs) |
| `text-meta` | `0.8125rem` (`13px`) / `1.45` | Field labels, table column headers, timestamps, helper text, status indicators |

- **Sentence case:** UI labels, field labels, buttons, and table headers use sentence case rather than tracked-out uppercase strings. Acronyms (`IPS`, `DCF`, `APR`, `W-2`), ticker symbols (`AAPL`), and explicit governance status tokens (`PASS`, `DRIFTED`, `APPROVED`, `REJECTED`) retain their standard casing.

## Layout, Navigation & Elevation

- **Top Masthead (`Navbar.vue`):** Fixed `64px` single-line header (`max-w-7xl`) featuring a bespoke inline geometric SVG shield mark and `Newsreader` brand wordmark on the left, clean underline-indicated navigation links (`Dashboard`, `Portfolio`, `Spending`, `Documents`, `Profile`) on desktop (`>= 768px`), and a toggleable single-column mobile drawer on `< 768px`. Scroll state (`window.scrollY > 8`) adds crisp bottom separation (`shadow-nav-scrolled`). On `/onboarding`, the global navbar yields to the dedicated fixed onboarding header.
- **Dashboard Workbench (`/`):** 12-column responsive grid on desktop (`>= 1024px`) split **5 columns (~42%)** for the Copilot Command & Governance Desk on the left and **7 columns (~58%)** for the Financial Ledger Canvas on the right. Stacks cleanly into a single column on tablet and mobile without horizontal overflow.
- **Elevation:** Primary sheets use `1px solid #D5DDE6` borders and a quiet hairline shadow (`0 1px 2px rgba(11, 19, 32, 0.04)`). Interactive elements expose a `2px` Cobalt (`#1E40AF`) `focus-visible` outline with `2px` offset.

## Motion & Accessibility

- **Explicit transitions only:** CSS transitions name explicit properties (`transition-colors`, `transition-transform`, `transition-[width]`, `transition-[stroke-dasharray,stroke-dashoffset]`) with brisk durations (`150ms`-`300ms`) and ease-out curve `cubic-bezier(0.22, 1, 0.36, 1)` (`ease-desk`). `transition-all` is prohibited.
- **Reduced motion:** `@media (prefers-reduced-motion: reduce)` collapses all animations and transitions globally in `src/style.css`.
- **No idle loops:** Decorative pulsing dots and ambient glows are omitted. Spin animations appear solely on active loading or streaming indicators (`progress_activity`).

## Components

### Buttons (`Button.vue`)
- **Primary:** Deep Maritime Navy (`#0F2342`) with white text (`hover:bg-primary-container`).
- **Approval:** Deep Forest Emerald (`#065F46`) with white text, reserved exclusively for human-in-the-loop confirmations.
- **Danger:** Crisp white surface with Oxblood Crimson border and text (`hover:bg-error-container/60`) for Reject actions.
- **Secondary:** Crisp white surface with hairline border (`#D5DDE6`) and slate hover fill for Edit and Cancel controls.

### Status Indicators (`StatusPill.vue`)
- Compact rounded-md (`6px`) hairline-bordered semantic indicators used only for genuine governance, drift, and ingestion statuses (`PASS`, `APPROVED`, `SUCCESS`, `PENDING`, `DRIFTED`, `VIOLATION`, `REJECTED`, `FAILED`).

### Copilot Desk & Prompt Directory (`DashboardView.vue`)
- Single elevated sheet combining the prompt composer (`Enter` to run, `Shift+Enter` for newline, single primary `Run` button) above a hairline-divided **Suggested inquiries** list of clickable prompt rows with subtle arrow motion (replacing clustered pill chips).
- Streaming responses appear in clean single-level turns below; active runs render `AnalysisProgress` and clear it once the final reply or `ApprovalCard` arrives.

### Unified Balance & Allocation Sheet (`NetWorthCard.vue`, `AssetAllocationCard.vue`)
- On the Dashboard, `NetWorthCard` and `AssetAllocationCard` compose inside one hairline-divided white sheet (`embedded` mode) so balances and allocation read as one ledger.
- `NetWorthCard` sets the balance in `Newsreader` `text-display-figure` with `tabular-nums`, optional cash summary, and updated timestamp.
- `AssetAllocationCard` dynamically computes the mix from live `holdings` when available (falling back to baseline weights when empty), pairing a segmented proportion bar with a hairline-divided tabular breakdown.

### Top Holdings Ledger (`TopHoldingsTable.vue`)
- Institutional HTML `<table>` inside a single hairline-bordered sheet with square ticker monograms, sentence-case column headers (`Holding`, `Asset class`, `Shares`, `Market value`), and right-aligned tabular figures.

### Portfolio Drift Report (`DriftReportCard.vue`)
- Tabular IPS drift audit featuring an inline **Band position** visual track per asset class: a subtle shaded `[min%, max%]` target bracket overlaid with the actual allocation fill bar (Maritime Navy when in-band, Warm Ochre Amber when drifted), paired with right-aligned percentages and semantic `PASS` / `DRIFTED` status pills.

### Advisory Equity Research (`EquityAnalyzer.vue`, `EquityRecommendationCard.vue`)
- Single-ticker lookup panel integrated with an embedded hairline-separated recommendation sheet showing direction indicator, 3-column hairline-divided DCF valuation strip (`Price`, `Intrinsic (DCF)`, `Upside`), rationale prose (`<= 65ch`), side-by-side Suitability and Key risks columns, and advisory disclaimers.

### Human-in-the-Loop Approval Card (`ApprovalCard.vue`)
- Elevated governance sheet accented with a `4px` Maritime Navy left border (`border-l-primary`), displaying Action ID, status indicator, a 3-column hairline-divided trade ticket (`Ticker`, `Side`, `Quantity`), rationale, hairline-divided Policy safety checklist (`PASS`/`FAIL`), inline Edit form, and Approve / Reject / Edit footer controls.

### Analysis Progress Stepper (`AnalysisProgress.vue`)
- Live pipeline list rendered inside an active agent turn with a Cobalt spinning indicator, tabular elapsed timer, and per-stage rows (`running`, `done`, `skipped`, `failed`, `pending`). Clears automatically when the turn completes or pauses for approval.

### Spending Overview (`SpendingSummaryCard.vue`, `AnomalyAlertCard.vue`, `CategoryBreakdownTable.vue`)
- **Cash-flow summary strip:** One hairline-divided 4-column white sheet (`Total income`, `Total outflow`, `Savings rate`, `Liquidity reserve`).
- **Anomaly band:** Left-accented Oxblood Crimson alert sheet (`border-l-4 border-l-error`) with hairline-divided anomaly rows and optional narrative summary.
- **Category breakdown:** Horizontal Maritime Navy progress bars (`transition-[width]`) paired with right-aligned shares and currency totals.

### Document Ingestion (`UploadDropzone.vue`, `DocumentsView.vue`)
- Dropzone with bespoke inline geometric SVG upload emblem, document type & BigQuery table selectors, sentence-case primary CTA (`Browse files` / `Change file`), and a flat hairline-separated privacy footer, paired with a full-width ingestion history table.

### Unified Profile & Policy Hub (`/profile`)
- Direct `Newsreader` page header with IPS version indicator and `Run Guided Setup` trigger, a unified 4-column hairline summary strip, and an underline tab bar switching across 6 tabs: **Personal & Family**, **Goals & Timeline**, **Risk & Allocation**, **Liabilities & Debt**, **Policy Guardrails**, and **Income & Tax (W-2 Document AI)**.
- All form groups sit on clean white elevated sheets with soft alabaster (`#F4F6F8`) inputs and hairline internal row dividers.

### Guided Onboarding Flow (`/onboarding`)
- Dedicated fixed progress header (`transition-[width]`) with bespoke SVG shield mark, back button, step title, and quick link to `/profile`.
- 7 turns (`WelcomeStep`, `GoalsStep`, `LiabilitiesStep`, `RiskCalibrationStep`, `TargetAllocationStep`, `ConstraintsStep`, `SubmissionStep`) featuring clean hairline cards, accessible radio groups, interactive SVG target allocation donut chart (`2πr = 251.2`) with fail-closed 100% validation, and zero pre-heading eyebrows or fake telemetry animations.
