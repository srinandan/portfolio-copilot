# Portfolio Copilot Frontend

The standalone web interface for **Portfolio Copilot**, an agentic personal finance and investment assistant demonstrating registry-driven dynamic planning on the Google Cloud / Gemini Enterprise Agent Platform.

Built with **Vue 3** (Composition API, `<script setup lang="ts">`), **TypeScript**, **Vite**, and **Tailwind CSS**, and deployable as a containerized Single-Page Application (SPA) on **Google Cloud Run**.

See [ADR-0003](../docs/adr/0003-standalone-ui-not-agentspace.md) for why Portfolio Copilot uses a bespoke standalone UI rather than an out-of-the-box chat surface (like Google Cloud AgentSpace).

---

## What It Does

- **Standalone Gateway-Coupled UI**: Calls the Go API Gateway (`gateway/`) over HTTP/REST and Server-Sent Events (SSE), never communicating directly with the Python orchestrator or GCP services (ADR-0003, F7 contract).
- **Human-in-the-Loop (HITL) Governance Centerpiece**: Renders structured interactive cards (`<ApprovalCard />`) for proposed trades and rebalancing actions. Displays itemized Policy Safety Checklists (`verdict.rule_results`) with individual `PASS` / `FAIL` (`VIOLATION`) status pills and supports inline quantity/rationale editing before human sign-off.
- **Stitch Design System Alignment**:
  - **Dual-Font Typography**: Uses **Geist** for headings, navigation, and conversational text, and **JetBrains Mono** (`tabular-nums`) for all monetary values, tickers, trade quantities, and audit IDs.
  - **Desktop Dual-Panel Layout**: Features a responsive split layout (`>=1024px`) with a **40% Conversational Stream / Live Governance Left Panel** and a **60% Financial Canvas Right Panel**.
  - **Air-Gapped Privacy Manifesto**: Highlights end-to-end local document processing ("Security Through Privacy" — no direct bank connections).
- **Comprehensive Financial Views**:
  - **Dashboard (`/`)**: Combines real-time agent planning messages with summary cards (`NetWorthCard`, `AssetAllocationCard`, `TopHoldingsTable`).
  - **Portfolio (`/portfolio`)**: Itemizes holdings and displays the **Portfolio Drift Report** (`DriftReportCard`), comparing current asset allocation against active Investment Policy Statement (IPS) target bands (`skills/portfolio-analysis/SKILL.md`).
  - **Spending (`/spending`)**: Visualizes 30-day income, outflow, savings rate, reserve months, category breakdown, and anomaly detections (`skills/spending-analysis/SKILL.md`).
  - **Documents (`/documents`)**: Interactive drag-and-drop statement upload dropzone (`UploadDropzone`) and parsing history log.
  - **Security (`/security`)**: Local privacy settings, 2FA toggle, encryption level options, and encrypted backup export.

---

## Project Structure

```
frontend/
├── Dockerfile              # Multi-stage build: Node 22 (SPA) + Go 1.25 (server) -> distroless static
├── cloudbuild.yaml         # Cloud Build CI/CD pipeline configuration
├── server/                 # Go static-file host + authed reverse proxy to the gateway
│   └── main.go             # Serves /dist and proxies /api + /health with a Google ID token
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
    │   ├── dashboard/      # NetWorthCard and AssetAllocationCard
    │   ├── documents/      # UploadDropzone
    │   ├── layout/         # Navbar (brand header with Gateway Online/Offline badge)
    │   ├── portfolio/      # TopHoldingsTable and DriftReportCard (IPS drift analysis)
    │   └── spending/       # SpendingSummaryCard, CategoryBreakdownTable, AnomalyAlertCard
    ├── router/             # Vue Router SPA route definitions
    ├── services/           # GatewayService API client (calls Go API Gateway)
    ├── tests/              # Vitest + @testing-library/vue test suites (100% component coverage)
    ├── types/              # TypeScript contracts matching backend spec (Holdings, IPS, Spending)
    ├── App.vue             # Root application wrapper
    ├── main.ts             # Application entrypoint (Pinia, Vue Router, Tailwind CSS)
    └── style.css           # Tailwind directives and base tabular-nums styling
```

---

## Prerequisites

- **Node.js 22+**
- **npm 9+**

---

## Local Setup & Installation

Navigate to the `frontend` directory:

```bash
cd frontend
```

Install npm dependencies:

```bash
npm install
```

### Local Development Server

Run the development server with Vite:

```bash
make -C frontend local        # or: npm run dev
```

By default, Vite runs on `http://localhost:3000` and proxies `/api` and `/health` requests to `http://localhost:8080` (the default local port for the Go API Gateway).

---

## Build & Test

### Production Build

Compile and bundle the frontend for production:

```bash
npm run build
```

This runs `vue-tsc -b && vite build`, checking types across all `.ts` and `.vue` files and outputting optimized static assets to `dist/`.

### Running Tests

Run the Vitest unit and component test suite:

```bash
npm test
```

Run tests with line coverage reporting:

```bash
npm run test -- --coverage
```

> **Coverage Expectation**: Per [`.agent/skills/code-coverage/SKILL.md`](../.agent/skills/code-coverage/SKILL.md), the `frontend/` directory has an advisory **60% line coverage target** (UI code has a lower ratio of logic to markup). Specifically, the Human-in-the-Loop (`ApprovalCard`) and Policy Safety Checklist governance paths are tested to **100% line coverage** across all conditional rendering states (pending, edit mode, approved, rejected).

---

## Docker & Cloud Run Deployment

The frontend is containerized using a multi-stage `Dockerfile`:
1. **UI Builder Stage**: Uses `node:22-alpine` to execute `npm ci` and `npm run build`, producing static assets in `dist/`.
2. **Go Builder Stage**: Uses `golang:1.25` to compile `./frontend/server` — a small binary that serves the built SPA and reverse-proxies `/api/*` + `/health` to the gateway Cloud Run service.
3. **Runtime Stage**: Uses `gcr.io/distroless/static:nonroot`, ships the Go binary plus the `dist/` assets, and runs on port `8080` as the `nonroot` user.

### Go Static/Proxy Server (`server/main.go`)

nginx cannot mint Google-signed ID tokens, so the frontend container runs a Go binary (`frontend/server/`) instead. Its two jobs:

- **Serve the SPA**: static files from `$STATIC_DIR` (defaults to `/dist` inside the container), with an `index.html` fallback for client-side routes (Vue Router history mode). Paths containing a file extension (`/missing.js`) 404 normally so the browser doesn't eval `index.html` as JavaScript.
- **Proxy `/api/*` and `/health` to the gateway**: reverse-proxies to `$GATEWAY_URL`. When the target is HTTPS (Cloud Run) the proxy attaches an `Authorization: Bearer <id_token>` header per request, using `google.golang.org/api/idtoken.NewTokenSource(ctx, GATEWAY_URL)` — the Cloud Run metadata server mints the token under the frontend service account (`portfolio-copilot-frontend-sa`, granted `roles/run.invoker` on the gateway by `scripts/setup_cloudrun.sh`). When the target is HTTP (local dev against `make -C gateway local`) the proxy forwards without auth.

Env vars:
- `GATEWAY_URL` — required in production; must be the exact `https://portfolio-copilot-gateway-*.run.app` URL (looked up by `frontend/cloudbuild.yaml` at deploy time and injected via `--set-env-vars`). Missing → `/api` and `/health` return `503`.
- `STATIC_DIR` — override the static file root (default `/dist`).
- `PORT` — override listen port (default `8080`).

### Deploying via the Makefile

```bash
make -C frontend deploy
```

This calls `gcloud builds submit --config=frontend/cloudbuild.yaml` with `_COMMIT_SHA=$(git rev-parse --short HEAD)` and the active gcloud region, builds+pushes the image to Artifact Registry, and deploys it to Cloud Run under the `portfolio-copilot-frontend-sa` service account created by `scripts/setup_cloudrun.sh`.

For tag-based automatic releases, see [`install/README.md`](../install/README.md) — pushing `v*` git tags fires the triggers created by `scripts/setup_cloudbuild_triggers.sh`.

---

## Related Specifications & Architecture

- **[ADR-0003](../docs/adr/0003-standalone-ui-not-agentspace.md)**: Standalone UI vs. out-of-the-box AgentSpace
- **[ADR-0013](../docs/adr/0013-api-gateway-pattern.md)**: API Gateway pattern decoupling UI from orchestrator
- **[Functional Spec](../docs/spec/01-functional.md)**: Core user journeys (`U1` - `U4`)
- **[Architecture Spec](../docs/spec/02-architecture.md)**: Frontend-Gateway (`F7`) boundary and contract relationships
- **[Contracts Spec](../docs/spec/03-contracts.md)**: Shared data models (`HoldingsSnapshot`, `ProposedAction`, `ReviewerVerdict`)
