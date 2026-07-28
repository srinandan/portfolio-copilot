# ADR-0003: Standalone custom UI, not Gemini Enterprise/Agentspace

## Status
Accepted

## Context
This is a personal-use demo, not a business solution — Agentspace's
consumer-facing surface is built for enterprise workflows. But the project
also exists specifically to showcase Gemini Enterprise Agent Platform
capabilities, which created an apparent tension: build a custom UI and
seem to be avoiding the platform, or use Agentspace and lose control over
the interaction layer.

## Resolution of the apparent tension
"Gemini Enterprise platform capabilities" and "Agentspace's UI surface"
are separable. What's actually being showcased — Agent Engine runtime, A2A
orchestration, Sessions/Memory Bank, the ADK lifecycle, and the governance
layer — lives entirely in the backend. Agentspace is one possible
*consumer* of that backend, not the thing being demonstrated. A standalone
UI calling Agent Engine-deployed agents via API is a complete
demonstration of the platform.

## Decision
Build a standalone frontend (TypeScript + Vue.js, Cloud Run) that calls
the orchestrator through a thin Go API gateway, rather than fronting the
system with Agentspace.

## Why this is better, not just acceptable
- The human-approval gate is the centerpiece of this demo — a bespoke
  structured card (ticker, quantity, IPS-check status, edit/approve/reject)
  beats whatever a generic enterprise chat surface renders for a
  structured object
- Spending trend charts and tables have a different visual grammar than
  enterprise workflows
- A personal tool should feel personal, not like an internal console

## Why a gateway, not a direct frontend→orchestrator call
Even though Agent Engine exposes the orchestrator via its own API, a thin
Go gateway sits between them, handling:
- Auth — the browser never holds GCP service-account credentials
- Streaming translation — Agent Engine's event stream shaped into
  SSE/WebSocket for the browser
- Fan-out — one UI action may need the orchestrator plus a direct
  BigQuery read, composed server-side
- The approval-write path — the actual "approve" action writes to the
  Firestore audit log and triggers execution; this shouldn't be a
  browser-initiated write with elevated permissions

## Consequences
- One more service to build and deploy, but each layer stays properly
  scoped
- Full control over structured rendering for the approval flow, which
  matters more here than in most demos
