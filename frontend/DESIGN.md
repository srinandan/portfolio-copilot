---
name: Portfolio Copilot
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#45464d'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#515f74'
  on-secondary: '#ffffff'
  secondary-container: '#d5e3fd'
  on-secondary-container: '#57657b'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#002114'
  on-tertiary-container: '#069669'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#d5e3fd'
  secondary-fixed-dim: '#b9c7e0'
  on-secondary-fixed: '#0d1c2f'
  on-secondary-fixed-variant: '#3a485c'
  tertiary-fixed: '#85f8c4'
  tertiary-fixed-dim: '#68dba9'
  on-tertiary-fixed: '#002114'
  on-tertiary-fixed-variant: '#005137'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  display-lg:
    fontFamily: Geist
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  title-sm:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: '0'
  body-base:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: '0'
  body-mono:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: '0'
  label-caps:
    fontFamily: Geist
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.08em
  headline-lg-mobile:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 20px
  margin-mobile: 16px
  margin-desktop: 32px
  panel-split: 40% 60%
---

## Brand & Style

The brand personality is **authoritative, clinical, and reassuring**. It operates as a high-end financial assistant that balances the precision of an institutional trading desk with the transparency of a developer tool. The UI must evoke a sense of absolute security and intellectual rigor, moving away from "friendly" consumer fintech toward "powerful" professional governance.

The design style is **Corporate Modern with a Minimalist/Technical edge**. It utilizes a structured "Dual-Panel" layout to separate human-centric conversation from data-centric analysis. Key characteristics include:
- **Hairline Precision:** Use of 1px borders to define containment without visual weight.
- **Data Density:** High information density handled through clear typographic hierarchy and monospaced accents.
- **State Clarity:** Explicit color-coding for financial health (Emerald), risk (Amber), and violation (Crimson).
- **Institutional Canvas:** A "Cool Ice" background that provides a glare-free, professional environment for long-form data auditing.

## Colors

The palette is anchored in **Deep Navy (#0F172A)** to signify stability and institutional trust. 

- **Primary & Neutral:** The interface relies on a "High-Contrast White-on-Ice" foundation. Surfaces are Pure White (#FFFFFF), while the background is a subtle Cool Ice (#F8FAFC). Borders use a slate hairline (#E2E8F0) to maintain structure.
- **Action & Health (Emerald):** Emerald Green is used strictly for "Growth" and "Compliance." It signals successful document parsing, approved trades, and healthy portfolio targets.
- **Technical Blue (Electric):** Electric Blue highlights "Agent Activity." It is used for tool execution, research links, and the dynamic planning stream.
- **Alert System:** Amber is reserved for "Portfolio Drift" and "Pending Approvals." Crimson is used exclusively for "Policy Violations" and "Trade Rejections."

## Typography

This system employs a **dual-font strategy** to separate narrative from data.

- **UI & Conversation (Geist):** Used for all interface labels, agent messages, and headings. Its geometric nature provides a modern, clean look that feels contemporary yet serious.
- **Financial & Audit Data (JetBrains Mono):** Crucial for "Portfolio Copilot." All monetary figures, ticker symbols (e.g., AAPL), trade quantities, and audit IDs must use this monospaced font. This ensures tabular alignment of numbers, making it easier for users to compare values vertically.
- **Case Usage:** Use `label-caps` for table headers and category tags to create clear visual separation from content.
- **Numerical Alignment:** Always use `font-variant-numeric: tabular-nums` for data tables to prevent shifting when values update.

## Layout & Spacing

The system follows a **12-column grid** on desktop, but the primary structure is defined by a **Dual-Panel Split**.

- **Desktop (>=1024px):** A fixed split layout. The Left Panel (40%) handles the conversational stream and agent planning. The Right Panel (60%) serves as the primary "Financial Canvas" for cards and data tables.
- **Spacing Rhythm:** Based on an 8px scale. Use 24px (lg) for internal card padding and 32px (xl) for page margins to create a "High-End" breathable feel.
- **Data Density:** In data-heavy tables, reduce vertical cell padding to 10px to maximize information visibility without compromising touch targets.
- **Reflow:** On mobile (<768px), the layout stacks into a single column. The agent chat becomes a collapsible bottom-sheet or a dedicated tab to prioritize the financial data view.

## Elevation & Depth

To maintain a "Clinical" and "Secure" aesthetic, the system avoids heavy shadows in favor of **Tonal Layers and Hairline Borders**.

- **Surfaces:** Use `#FFFFFF` for all primary containers (cards, modals). These sit atop the `#F8FAFC` background.
- **Shadows:** Use a single, extremely subtle "Ambient Shadow" for cards: `0 1px 3px rgba(15, 23, 42, 0.06)`. It should look like the card is barely lifted from the surface.
- **Separation:** Rely on 1px solid borders (`#E2E8F0`) for structural definition.
- **Focus States:** Use a 2px offset ring in Electric Blue (#2563EB) to indicate active input or interactive agent nodes.
- **Depth via Color:** Use the "Deep Navy" (#0F172A) for the most elevated global elements (like the Primary Navigation) to ground the interface.

## Shapes

The shape language is **Rounded**, using `0.5rem` (8px) as the base radius for standard components like buttons and input fields.

- **Standard Cards:** Use `rounded-lg` (16px) to provide a soft, modern container for complex data.
- **Status Chips:** Use a full "Pill" shape for status indicators (e.g., "PASS", "DRIFTED") to distinguish them from interactive buttons.
- **Upload Dropzones:** Use `rounded-lg` with a dashed border to signify a temporary, interactive area.

## Components

### Buttons
- **Primary:** Deep Navy background, white text. Bold and authoritative.
- **Approval:** Emerald Green background. Exclusive to human-in-the-loop confirmations.
- **Reject/Danger:** Crimson outline or text. Used for "Reject Proposal."

### Secure File Upload
- **Dropzone:** 2px dashed Slate (#94A3B8) border. On drag-over, the border turns Emerald Green and the background becomes a light Emerald tint (#D1FAE5 at 30%).
- **Validation Card:** Displays filename, size, and a monospaced "Parsed Record Count." Includes a "Secure Processing" badge with a lock icon.

### Human-in-the-Loop Approval Card
- **Header:** Contains a monospaced Action ID and a timestamp.
- **Body:** A structured grid showing the trade details (Ticker, Side, Amount). Side must be color-coded (BUY: Emerald, SELL: Crimson).
- **Verdict Section:** An itemized list of policy rules with "PASS/FAIL" badges. This creates a "Checklist" of safety before the user clicks execute.

### Financial Visualizations
- **Drift Bars:** A horizontal track (#E2E8F0) with a "Target Range" bracket. The actual value is a solid bar that turns Amber if it falls outside the bracket.
- **Status Pills:** Small, bold, uppercase labels. Use emerald backgrounds for "PASS" and "APPROVED", amber for "PENDING" or "DRIFTED", and crimson for "VIOLATION".

### Input Fields
- White background, 1px Slate border. 
- **Monospaced Inputs:** Any input field for dollar amounts or ticker symbols must use JetBrains Mono.

### Onboarding & Calibration Flow (`/onboarding`)
- **Step Progress Bar:** Header-level animated progress bar showing fractional completion across the 4 setup turns (0% -> 33% -> 66% -> 100%).
- **Interactive Objective Cards:** Single-select objective vectors (Aggressive Capital Appreciation, Balanced Growth & Income, Capital Preservation) with primary-bordered active states.
- **Real-Time Telemetry Canvas:** Desktop 60% right panel dynamically updates model-generated allocation forecasts (Equities, Fixed Income, Cash) and Projected Return metrics as the user explores risk profiles.

### Target Allocation Donut Chart & Sliders
- **SVG Donut Chart:** Inline vector chart computed via stroke-dasharray and stroke-dashoffset based on the circle's circumference ($2\pi r = 251.2$). Segmented by Equities (`#131B2E`), Fixed Income (`#B9C7E0`), and Cash (`#565E74`).
- **Synchronized Sliders & Inputs:** Dual-control range sliders and monospaced number inputs for granular target band overrides.
- **100% Total Validation:** Fail-closed error toast (`bg-error-container text-on-error-container`) warning the user whenever allocations sum to $\ne 100\%$, disabling the "Confirm Allocation" CTA until balanced.