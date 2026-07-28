# ADR-0004: Registry-driven dynamic planning, not a fixed multi-agent pipeline

## Status
Accepted — this is the architectural pivot the rest of the project hangs
off of.

## Context
The original design was a fixed pipeline: Goals & Onboarding → Orchestrator
→ Spending Analyst → Portfolio Analyst → Research → Action Agent →
Reviewer → Human. That's a well-designed instance of the standard
2025-era multi-agent pattern — orchestrator + sub-agents + HITL approval —
which is also, by 2026, thoroughly commoditized. It's the default
reference architecture in nearly every agent framework's tutorial and
wouldn't distinguish this project from any of them.

## Decision
Replace the fixed roster with a single root agent that, given a goal,
queries the Agent Registry **at runtime** to discover which skills it's
currently authorized to invoke, and composes its own plan from what it
finds — implemented via ADK 2.0's dynamic workflows (`DynamicNode` with
real programmatic control flow: loops, conditionals, recursion — not a
static graph defined in advance).

The former pipeline stages (Goals & Onboarding, Spending Analysis,
Portfolio Analysis, Research, Action Drafting) become *candidate skills*
the planner may discover and compose, not a required sequence. The
Reviewer/Critic and human-approval gate become tools the planner itself
decides to invoke when it assesses an action as high-stakes, not fixed
pipeline stages.

## Why this is the actual differentiator
Most agent demos hardcode the agent graph — a human designed the org
chart in advance. Dynamic discovery-and-compose at plan time is rare, and
it makes this project a genuine demonstration of agent skill governance,
not a generic finance demo with governance added after the fact. It also
produces genuinely different, more compelling demo moments:

- A visible planning trace: "goal received → queried registry → N skills
  available, 1 requires elevated approval scope → composed plan →
  executing step 2 of N"
- **Live skill revocation**: revoke a skill mid-session and watch the
  *next planning cycle* route around it, unprompted — not just watch a
  fixed pipeline stage get skipped
- ADK's automatic checkpointing/resume (successful sub-nodes skipped on
  resume) directly supports this without custom state-tracking code

## Consequences
- More implementation complexity than a fixed pipeline
- Requires the registry to expose a queryable, versioned skill catalog at
  runtime — not just configuration read once at startup
- The root planner must itself decide when an action is high-stakes
  enough to warrant Reviewer/human involvement — this judgment logic is
  now part of the planner rather than a hardcoded pipeline position
