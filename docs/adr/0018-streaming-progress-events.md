# ADR-0018: Streaming Progress Events for Long-Running Analyses

## Status
Accepted

## Context

A planning turn runs a multi-stage pipeline — skill discovery, spending
analysis, portfolio drift, research, action drafting, compliance review, and
(when a trade is drafted) the HITL approval and execution gates. End to end this
takes **2–4 minutes**, dominated by the per-skill Managed Agent dispatches.

During that window the frontend showed a single frozen line
(`"Analyzing portfolio and discovering authorized skills..."`) until the final
result arrived. The user had no signal that anything was happening, how far
along it was, or which stage was active.

The pipeline already emits a `SKILL_INVOKED` audit entry at the start of every
skill (see [ADR-0012](0012-structured-logging.md) and `state/writers.py`), so
the orchestrator *knows* each meaningful checkpoint. But those entries are
written to the **Firestore audit log** — an authoritative, fail-closed ledger —
and never reach the user's stream. The audit log is the wrong transport for UI
hints: it is durable governance data, not a per-request UI channel.

The wire between orchestrator and browser is already an SSE stream
([ADR-0017](0017-unified-gateway-and-frontend.md)): the orchestrator's
`/v1/invoke` and `/v1/resume` endpoints stream ADK Runner events, which the Go
gateway proxies verbatim to the SPA. The question was how to add
human-meaningful progress to that stream without disturbing the delicate ADK
workflow, checkpointing, and HITL resume machinery in `root_planner`
(`rerun_on_resume=True`).

Options considered:

1. **Convert `root_planner` into an async generator that `yield`s progress
   events** interleaved with its work. Idiomatic ADK, but it entangles UI
   feedback with the checkpoint/resume control flow, cannot easily yield from
   inside the `asyncio.gather` parallel group, and re-yields on every HITL
   resume.
2. **A dedicated progress sub-node invoked per checkpoint via `ctx.run_node`.**
   Reuses a proven pattern but risks checkpoint-key collisions when the same
   node is invoked repeatedly in one turn.
3. **An out-of-band progress channel decoupled from the ADK workflow.** The
   planner reports progress as a side effect (mirroring how it already emits
   audit entries); the streaming layer interleaves those reports with the ADK
   event stream.

## Decision

Adopt **option 3: an out-of-band, advisory progress channel** (`orchestrator/progress.py`).

1. **Context-variable channel.** A `contextvars.ContextVar` (`PROGRESS_CHANNEL`)
   holds a per-run `asyncio.Queue`. The FastAPI streaming layer installs the
   queue for the lifetime of a stream and tears it down afterward.

2. **`report_progress(stage, status, label, detail=…)`.** The planner calls
   this at each checkpoint — right next to the existing `emit_skill_invoked_audit`
   call in `_execute_skill`, and around discovery, the HITL gate, and the
   execution gate. It puts a progress dict on the channel, or is a **silent
   no-op** when no channel is installed (non-streaming code paths, unit tests).
   It never raises into the caller: a progress hiccup can never abort the
   analysis it describes. Because context variables propagate to tasks created
   within the run's context, this works from inside the parallel
   `asyncio.gather` group as well.

3. **Interleaving (`server._interleave_progress`).** A single async generator
   drains the ADK Runner's events and the progress queue onto one output stream
   in real arrival order. Both SSE (`/v1/invoke`, `/v1/resume`) and the Agent
   Runtime NDJSON path (`/api/stream_reasoning_engine`) route through it, so the
   two framings share one drain and one error path.

4. **Wire shape.** Each progress event is a JSON object with a discriminating
   `kind`:

   ```json
   {"kind": "progress", "stage": "portfolio-analysis",
    "status": "running", "label": "Analyzing portfolio drift",
    "detail": "8% over target"}
   ```

   `stage` is a stable id the frontend keys its stepper rows on; `status` is one
   of `running | done | skipped | failed`; `detail` is optional. ADK event
   frames are unchanged, so existing consumers are unaffected.

5. **Frontend rendering.** The dashboard routes `kind: "progress"` events into a
   live **stepper** (`AnalysisProgress.vue`): each stage advances
   pending → running (spinner) → done ✓ / skipped / failed, with an elapsed
   timer. When the run completes (or pauses for HITL approval), the stepper is
   cleared and **replaced by the final output** / approval card.

**Progress events are advisory UI signals only.** They carry no governance
weight and never gate execution. The authoritative record of what ran remains
the immutable Firestore audit log; dropping a progress event changes nothing but
the UI. This separation is deliberate and must be preserved.

## Consequences

- **Visibility**: the 2–4 minute analysis is now a live, legible sequence of
  stages instead of a frozen line.
- **Isolation**: `root_planner`'s return value, checkpointing, and HITL resume
  flow are untouched — progress is a pure side effect, so the ADK control flow
  carries no UI concern. The final ADK output event (the planner's results list)
  is still the last frame on the stream.
- **Graceful degradation**: if the channel is absent or context propagation
  fails, `report_progress` no-ops and the run proceeds exactly as before — no
  progress, but no failure.
- **Resume idempotency**: because `root_planner` reruns on HITL resume, stages
  re-report their transitions; the frontend keys rows by `stage`, so re-emission
  updates rows in place rather than duplicating them.
- **New frontend contract surface**: `kind: "progress"` is now part of the SSE
  wire contract the SPA depends on. It is additive and discriminated, so it does
  not collide with ADK event frames, the `event: error` frame, or the HITL
  `hitl_approval_request` payload.
- **Cost**: one extra module, a handful of `report_progress` calls, a stepper
  component, and a per-run unbounded in-memory queue (negligible for a
  single-user demo).
