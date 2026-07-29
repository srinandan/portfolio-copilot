# Overview

## What this is

Portfolio Copilot is a personal finance/investment assistant, built to
demonstrate Gemini Enterprise Agent Platform capabilities — specifically
**registry-driven dynamic planning**, an approach to agent skill
governance where capabilities are discovered and composed at runtime
rather than hardcoded.

It is a personal-use demo. It is not a business solution, not multi-tenant,
and not intended for production or commercial use.

## Why this shape, not a simpler one

The obvious 2025-era version of this project is a fixed pipeline: a human
designs an org chart of agents (Spending Analyst → Portfolio Analyst →
Reviewer → Human), and the code hardcodes that sequence. That pattern is
commoditized — it's the default reference architecture in nearly every agent
framework's tutorial.

The distinguishing idea here: **the roster isn't fixed in code.** A single
root agent, given a goal, queries an Agent Registry at runtime to discover
which skills it's currently authorized to invoke, and composes its own plan
from what it finds. No skill is hardcoded into the orchestration logic. See
[ADR-0004](../adr/0004-dynamic-planning-over-fixed-pipeline.md).

This makes governance the actual subject of the demo, not a bolted-on
feature: skill revocation, versioning, and audit trail become visible,
live, in-session behaviors — not slides.

## Demo narrative (two centerpieces)

1. **Live skill revocation.** Mid-session, revoke one of the root agent's
   authorized skills (TTL expiry or explicit revocation via the registry).
   The next planning cycle visibly routes around it — no error, no restart,
   just a plan that no longer includes that capability.

2. **Adversarial resilience.** A tool result is deliberately poisoned to try
   to manipulate the agent into proposing an unauthorized trade. The
   Reviewer/Critic and governance layer catch it before it ever reaches the
   human approval gate.

## What "done" looks like

- Root planner (Python, ADK 2.0 dynamic workflows) queries the Agent Registry
  and composes a plan with no hardcoded skill roster
- At least one skill wired end-to-end: goal → plan → research → proposed
  action → Reviewer → human approval → execution
- Live skill revocation demonstrably changes the next planning cycle
- Full audit trail: every action traceable to skill version, registry
  entry, and approval scope
- Deployed on GCP (Agent Engine, Cloud Run), not run locally

## Non-goals

- Multi-tenant / multi-user support
- Real (non-paper) trade execution
- Production-grade reliability or SLAs
- Feature parity with a real robo-advisor
