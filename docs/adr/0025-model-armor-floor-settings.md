# ADR-0025: Google Cloud Model Armor Floor Settings for MCP Tool Security

## Status

Accepted

## Context

As Portfolio Copilot introduces dynamic agent capabilities via remote Model Context Protocol (MCP) servers (e.g. `https://firestore.googleapis.com/mcp` and `https://bigquery.googleapis.com/mcp`), conversational prompts, generated SQL queries, and financial document contents are exchanged between the agent orchestrator, Managed Agents, and database engines.

To protect the agent execution environment against prompt injection, jailbreaks, malicious URLs, unsafe content, and data leakage, Google Cloud provides **Model Armor** (`modelarmor.googleapis.com`). Model Armor provides project-wide **Floor Settings** (`projects/{PROJECT_ID}/locations/global/floorSetting`) that automatically intercept, sanitize, and log interactions across integrated services.

## Decision

1. **Automated Floor Settings Provisioning (`infra/setup_model_armor.sh` & `infra/model_armor_floor_settings.py`):**
   - Provide an automated, idempotent provisioning script in `infra/setup_model_armor.sh` and Python manager `infra/model_armor_floor_settings.py`.
   - Enabled by default (`ENABLE_MODEL_ARMOR=true`) in end-to-end infrastructure setup (`scripts/setup_all.sh` and `make setup-model-armor`).
   - Provide user options to enable/disable enforcement (`--enable` / `--disable`) and select enforcement modes (`INSPECT_ONLY` or `INSPECT_AND_BLOCK`).

2. **Integrated Services:**
   - `AI_PLATFORM`: Vertex AI and Reasoning Engine agent execution environments.
   - `GOOGLE_MCP_SERVER`: All Google-managed remote MCP servers (Firestore MCP, BigQuery MCP, and future service integrations).

3. **Security Policy & Filter Configuration:**
   - **Responsible AI (RAI) Filters:** Enforce filters for `HATE_SPEECH`, `DANGEROUS`, `SEXUALLY_EXPLICIT`, and `HARASSMENT` at `HIGH` confidence threshold.
   - **Sensitive Data Protection (SDP):** Basic config filter enforcement set to `ENABLED`.
   - **Prompt Injection & Jailbreak Defense:** Filter enforcement set to `ENABLED` at `MEDIUM_AND_ABOVE` confidence level.
   - **Malicious URI Filtering:** Filter enforcement set to `ENABLED`.
   - **Multi-Language Detection:** Enabled project-wide to ensure multi-lingual prompts and responses are analyzed.

4. **Observability & Cloud Logging:**
   - Enable Cloud Logging (`enableCloudLogging: true`) across both `AI_PLATFORM` and `GOOGLE_MCP_SERVER` floor settings.
   - All inspection findings and blocked attempts generate structured audit logs in Cloud Logging for security operations and SIEM integration.

## Consequences

- **Positive:** Project-wide defense-in-depth across all existing and future MCP servers and agent endpoints without requiring per-agent code modifications.
- **Positive:** Centralized compliance and security monitoring via Cloud Logging audit records.
- **Neutral:** Requires `modelarmor.googleapis.com` API enablement and `roles/modelarmor.admin` or `roles/owner` during setup.
