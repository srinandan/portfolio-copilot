# ADR-0032: Model Armor Runtime Guardrail Plugin (Per-Request Layer)

## Status

Accepted

## Context

ADR-0025 established **Model Armor Floor Settings** — a project-wide (`global`) backstop that inspects/blocks across integrated services (`AI_PLATFORM`, `GOOGLE_MCP_SERVER`). Floor settings are coarse: enforcement is a project-level `INSPECT_ONLY` / `INSPECT_AND_BLOCK` toggle, the check runs outside the ADK Runner, and a block is not surfaced in-band on the orchestrator's own SSE stream or trace.

`google-adk` v2.8.0 (ADR pending the bump, #361) ships a first-class **`ModelArmorPlugin`** (`google.adk.integrations.model_armor`). It screens each user turn and model response against regional Model Armor **templates** through the ordinary `before_model_callback` / `after_model_callback` seams, so a hit is blocked *inside the Runner*, per request, on the specific agent path.

Model Armor **templates** are a different primitive from **floor settings**: templates are regional resources (`projects/{p}/locations/{loc}/templates/{t}`, endpoint `modelarmor.{loc}.rep.googleapis.com`), whereas our floor settings are `global`. Adopting the plugin therefore requires creating template resources — it is a genuinely additive second layer, not a re-wiring of the floor settings.

## Decision

1. **Two complementary layers, one policy.**
   - **Floor settings** (ADR-0025) remain the always-on project backstop, provisioned by `scripts/model_armor_floor_settings.py`.
   - **The runtime plugin** adds a per-request layer wired onto the `Runner` in `orchestrator/src/orchestrator/server.py`. The template filter config created by `scripts/setup_model_armor_templates.py` mirrors the floor-settings policy (RAI at `HIGH`, PI/jailbreak at `MEDIUM_AND_ABOVE`, SDP `ENABLED`, malicious-URI `ENABLED`) so both layers enforce the same rules.

2. **Default OFF, opt-in via environment.** `orchestrator/src/orchestrator/guardrails/model_armor_plugin.py` builds the plugin only when `MODEL_ARMOR_PLUGIN_ENABLED` is truthy **and** at least one template is configured (full resource name in `MODEL_ARMOR_PROMPT_TEMPLATE` / `MODEL_ARMOR_RESPONSE_TEMPLATE`, or assembled from `MODEL_ARMOR_LOCATION` + `*_TEMPLATE_ID`). Otherwise `build_model_armor_plugin()` returns `None` and the Runner is constructed without it. A fresh deploy is unaffected; misconfiguration degrades to "no runtime guardrail" (logged), never a failed startup.

3. **Minimal dependency.** Add `google-cloud-modelarmor` directly rather than the full `google-adk[gcp]` extra, keeping the orchestrator image lean (BigQuery is accessed via MCP, not the GCP client libs).

4. **Blocks are advisory signals, not governance events.** A block surfaces as an `LlmResponse` carrying `custom_metadata={"model_armor_blocked": True}`. `server._drain_runner` detects it and emits an advisory `guardrail_block` SSE frame plus a WARNING log — the same advisory channel as `progress.py` (ADR-0018), deliberately separate from the immutable Firestore audit log.

## Consequences

- **Positive:** Per-request, in-Runtime enforcement on the sensitive planning path, with the block visible on the orchestrator's own SSE stream so the UI can render a notice.
- **Positive:** Rollout is safe and reversible — a single env flag, inert until templates exist.
- **Neutral:** Requires regional Model Armor **template** resources (new infra beyond the global floor settings) created via `scripts/setup_model_armor_templates.py`; templates must share one location per client.
- **Follow-up:** Promoting a guardrail block to a first-class `GUARDRAIL_BLOCKED` audit `EventType` — which spans the Python (`contracts/audit_log.py`) and Go (`pkg/contracts/audit_log.go`) governance contracts — is intentionally deferred and tracked separately, so this change stays confined to the Python orchestrator.
