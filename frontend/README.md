# Portfolio Copilot Frontend & Web Host

The web interface and host server for **Portfolio Copilot**, an agentic personal finance and investment assistant demonstrating registry-driven dynamic planning on the Google Cloud / Gemini Enterprise Agent Platform.

Built with **Vue 3** (Composition API, `<script setup lang="ts">`), **TypeScript**, **Vite**, **Tailwind CSS**, and a high-performance **Go backend server** (`frontend/server/`), deployable as a single containerized service on **Google Cloud Run**.

See [ADR-0003](../docs/adr/0003-standalone-ui-not-agentspace.md) and [ADR-0017](../docs/adr/0017-unified-gateway-and-frontend.md) for the architecture design.

---

## What It Does

- **Unified Web & API Architecture**: Hosts the compiled Vue 3 SPA and handles `/api/*` data requests (Firestore, BigQuery, Orchestrator SSE streaming) in-process without cross-service network hops (ADR-0017).
- **Human-in-the-Loop (HITL) Governance**: Renders interactive cards (`<ApprovalCard />`) for proposed trades and rebalancing actions, with itemized Policy Safety Checklists (`verdict.rule_results`) showing `PASS` / `FAIL` (`VIOLATION`) status pills and inline quantity/rationale editing before sign-off.
- **Stitch Design System**:
  - **Typography**: **Geist** for headings, navigation, and conversational text; **JetBrains Mono** (`tabular-nums`) for monetary values, tickers, trade quantities, and audit IDs.
  - **Desktop layout**: Responsive split layout (`>=1024px`) — 40% conversational stream / live governance on the left, 60% financial canvas on the right.
  - **Local document processing**: No direct bank connections; documents are processed locally.
- **Financial Views**:
  - **Dashboard (`/`)**: Combines real-time agent planning messages — including a live analysis progress stepper (`AnalysisProgress`) that tracks each pipeline stage during the minutes-long run and clears to reveal the final output (see [ADR-0018](../docs/adr/0018-streaming-progress-events.md)) — with summary cards (`NetWorthCard`, `AssetAllocationCard`, `TopHoldingsTable`).
  - **Portfolio (`/portfolio`)**: Itemizes holdings and displays the **Portfolio Drift Report** (`DriftReportCard`), comparing current asset allocation against active Investment Policy Statement (IPS) target bands (`skills/portfolio-analysis/SKILL.md`). Also hosts the **Research a stock** panel (`EquityAnalyzer` → `EquityRecommendationCard`), an advisory DCF valuation + suitability recommendation for a single ticker (`POST /api/analysis/equity`; see [ADR-0028](../docs/adr/0028-equity-research-and-suitability-advisory-analysis.md)).
  - **Spending (`/spending`)**: Visualizes 30-day income, outflow, savings rate, reserve months, category breakdown, and anomaly detections (`skills/spending-analysis/SKILL.md`).
  - **Documents (`/documents`)**: Typed document ingestion dropzone (`UploadDropzone`) and parsing history log, supporting bank transaction CSVs (streamed into BigQuery with deduplication) and financial snapshot JSONs (persisted to Firestore).
  - **Profile & Policy Hub (`/profile`)**: Comprehensive 6-tab settings hub (Personal & Family, Goals & Timeline, Risk Calibration & Allocation, Liabilities & Debt, Policy Guardrails, Income & Tax) that atomically updates user demographics (`user_profiles/{user_id}`), creates versioned IPS/liabilities records (`ips/{ips_id}_v{version}`, `liabilities/{user_id}`), and stores parsed IRS Form W-2 tax statements (`w2_documents/{w2_id}`) with 1-click profile income synchronization (ADR-0026).
  - **Onboarding (`/onboarding`)**: Guided interactive onboarding wizard with prefill support from active IPS and direct navigation to the unified Profile & Policy hub.

---

## Project Structure

```
frontend/
├── Dockerfile              # Multi-stage build: Node 20 (SPA) + Go 1.25 (server) -> distroless static
├── cloudbuild.yaml         # Cloud Build CI/CD pipeline configuration
├── Makefile                # Local dev and deployment automation
├── server/                 # Go backend server (serves /dist and handles /api/* in-process)
│   ├── handlers.go         # Data endpoint handlers (holdings, spending, drift, documents)
│   ├── main.go             # Entrypoint and router
│   ├── middleware.go       # CORS, recovery, structured logging
│   ├── plan.go             # Orchestrator SSE streaming bridge
│   └── spa.go              # SPA static asset serving & Vue Router history fallback
├── package.json            # Scripts, Vue 3, Pinia, Vue Router, Tailwind, and Vitest dependencies
├── tailwind.config.js      # Stitch design system color palette, typography, and spacing
├── vite.config.ts          # Vite build config and local dev proxy to http://localhost:8080
├── vitest.config.ts        # Vitest + jsdom test configuration and v8 coverage rules
├── public/
│   └── images/             # Static logos, icons, and design graphics
└── src/
    ├── components/
    │   ├── approval/       # ApprovalCard (HITL trade governance centerpiece)
    │   ├── common/         # Button and StatusPill reusable UI components
    │   ├── dashboard/      # NetWorthCard, AssetAllocationCard, AnalysisProgress (live progress stepper)
    │   ├── documents/      # UploadDropzone
    │   ├── layout/         # Navbar (brand header and navigation)
    │   ├── portfolio/      # TopHoldingsTable and DriftReportCard (IPS drift analysis)
    │   └── spending/       # SpendingSummaryCard, CategoryBreakdownTable, AnomalyAlertCard
    ├── router/             # Vue Router SPA route definitions
    ├── services/           # ApiService client (calls /api endpoints)
    ├── tests/              # Vitest + @testing-library/vue test suites (100% component coverage)
    ├── types/              # TypeScript contracts matching backend spec (Holdings, IPS, Spending)
    ├── App.vue             # Root application wrapper
    ├── main.ts             # Application entrypoint (Pinia, Vue Router, Tailwind CSS)
    └── style.css           # Tailwind directives and base tabular-nums styling
```

---

## Prerequisites

- **Node.js 20+**
- **Go 1.25+**

---

## Local Setup & Development

Navigate to the `frontend` directory:

```bash
cd frontend
```

### 1. Run the Full Stack Locally

Build the SPA and run the Go backend server on port `8080`:

```bash
make local-server
```

Open `http://localhost:8080` in your browser.

### 2. UI Development with Vite Hot-Reload

For frontend-only iterations with hot-module reloading:

```bash
make local        # runs Vite on http://localhost:3000, proxying /api to http://localhost:8080
```

---

## Build & Test

### Run All Tests (UI + Server)

```bash
make test
```

### Production Build

```bash
make build
```

---

## Docker & Cloud Run Deployment

The frontend is containerized using a multi-stage `Dockerfile`:
1. **UI Builder Stage**: Uses `node:20-alpine` to execute `npm ci` and `npm run build`, producing static assets in `dist/`.
2. **Go Builder Stage**: Uses `golang:1.25` to compile `./frontend/server`.
3. **Runtime Stage**: Uses `gcr.io/distroless/static:nonroot`, ships the Go binary plus the `dist/` assets, and runs on port `8080` as the `nonroot` user.

### Deploying via Makefile

```bash
make deploy
```

This invokes `gcloud builds submit --config=frontend/cloudbuild.yaml` to build, push, and deploy to Cloud Run under `portfolio-copilot-frontend`.

---

## Related Specifications & Architecture

- **[ADR-0003](../docs/adr/0003-standalone-ui-not-agentspace.md)**: Standalone UI vs. out-of-the-box AgentSpace
- **[ADR-0017](../docs/adr/0017-unified-gateway-and-frontend.md)**: Unified Frontend and Gateway Service Architecture
- **[Functional Spec](../docs/spec/01-functional.md)**: Core user journeys (`U1` - `U4`)
- **[Architecture Spec](../docs/spec/02-architecture.md)**: Architecture boundary and contract relationships
- **[Contracts Spec](../docs/spec/03-contracts.md)**: Shared data models (`HoldingsSnapshot`, `ProposedAction`, `ReviewerVerdict`)
