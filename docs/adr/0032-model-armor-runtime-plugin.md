# ADR-0032: Model Armor Runtime Guardrail Plugin (Per-Request Layer)

## Status

Accepted

## Context

ADR-0025 established **Model Armor Floor Settings** — a project-wide (`global`) backstop that inspects/blocks across integrated services (`AI_PLATFORM`, `GOOGLE_MCP_SERVER`). Floor settings are coarse: enforcement is a project-level `INSPECT_ONLY` / `INSPECT_AND_BLOCK` toggle, the check runs outside the ADK Runner, and a block is not surfaced in-band on the orchestrator's own SSE stream or trace.

`google-adk` v2.8.0 (ADR pending the bump, #361) ships a first-class **`ModelArmorPlugin`** (`google.adk.integrations.model_armor`). It screens each user turn and model response against regional Model Armor **templates** through the ordinary `before_model_callback` / `after_model_callback` seams, so a hit is blocked *inside the Runner*, per request, on the specific agent path.

Model Armor **templates** are a different primitive from **floor settings**: templates are regional resources (`projects/{p}/locations/{loc}/templates/{t}`, endpoint `modelarmor.{loc}.rep.googleapis.com`), whereas our floor settings are `global`. Adopting the plugin therefore requires creating template resources — it is a genuinely additive second layer, not a re-wiring of the floor settings.

## Decision

1. **Two complementary layers, split by scope — broad vs. specific.**
   - **Layer 1 — floor settings** (ADR-0025) remain the always-on, project-wide backstop: the *broad* policy — Responsible AI / abuse, prompt-injection & jailbreak, malicious-URI, and basic SDP. Provisioned by `scripts/model_armor_floor_settings.py`.
   - **Layer 2 — the runtime plugin's template** adds a *per-request* layer wired onto the `Runner` in `orchestrator/src/orchestrator/server.py`, and owns the *specifics*. The template created by `scripts/setup_model_armor_templates.py` uses **advanced SDP** (`sdpSettings.advancedConfig`) referencing a **Cloud DLP inspect template** that declares the exact financial-PII infoTypes we care about — `US_SOCIAL_SECURITY_NUMBER`, `CREDIT_CARD_NUMBER`, `US_BANK_ROUTING_MICR`, `IBAN_CODE`, `US_INDIVIDUAL_TAXPAYER_IDENTIFICATION_NUMBER` — at a tunable likelihood. It combines advanced SDP with the floor-conforming filters (RAI, PI/jailbreak, malicious-URI) required by Model Armor template conformance. The setup script provisions the DLP inspect template first, then the regional Model Armor prompt/response templates that reference it (sharing one location).

2. **Default ON, activated by template presence.** `orchestrator/src/orchestrator/guardrails/model_armor_plugin.py` builds the plugin whenever at least one template is configured (full resource name in `MODEL_ARMOR_PROMPT_TEMPLATE` / `MODEL_ARMOR_RESPONSE_TEMPLATE`, or assembled from `MODEL_ARMOR_LOCATION` + `*_TEMPLATE_ID`) — no separate enable step. `MODEL_ARMOR_PLUGIN_ENABLED` defaults to true and exists only as an explicit kill-switch (`=false`). A deploy with no template configured still returns `None` (inert until templates are provisioned), and misconfiguration degrades to "no runtime guardrail" (logged), never a failed startup. On a PII/RAI match the plugin blocks the turn (detection → block); screening *failures* are fail-closed by default (`MODEL_ARMOR_BLOCK_ON_SCREENING_FAILURE`, override to fail-open).

3. **Minimal dependency.** Add `google-cloud-modelarmor` directly rather than the full `google-adk[gcp]` extra, keeping the orchestrator image lean (BigQuery is accessed via MCP, not the GCP client libs).

4. **Blocks are advisory signals, not governance events.** A block surfaces as an `LlmResponse` carrying `custom_metadata={"model_armor_blocked": True}`. `server._drain_runner` detects it and emits an advisory `guardrail_block` SSE frame plus a WARNING log — the same advisory channel as `progress.py` (ADR-0018), deliberately separate from the immutable Firestore audit log.

## Consequences

- **Positive:** Per-request, in-Runtime enforcement on the sensitive planning path, with the block visible on the orchestrator's own SSE stream so the UI can render a notice.
- **Positive:** On by default but inert until templates exist, so the guardrail activates automatically once provisioned without a separate enable step, and stays reversible via the `MODEL_ARMOR_PLUGIN_ENABLED=false` kill-switch.
- **Positive:** No duplicated policy — the floor owns broad enforcement, the template owns specific PII detection, so tuning one layer doesn't drift from the other.
- **Neutral:** Requires two new regional resources (beyond the global floor settings), both created by `scripts/setup_model_armor_templates.py` and sharing one location: a **Cloud DLP inspect template** (the infoType list) and the **Model Armor templates** that reference it via advanced SDP.
- **Neutral:** Detection-only for now — the template references a DLP *inspect* template (block on match), not a *de-identify* template; redaction/masking of PII instead of blocking is a future option.
- **Follow-up:** Promoting a guardrail block to a first-class `GUARDRAIL_BLOCKED` audit `EventType` — which spans the Python (`contracts/audit_log.py`) and Go (`pkg/contracts/audit_log.go`) governance contracts — is intentionally deferred and tracked separately, so this change stays confined to the Python orchestrator.
