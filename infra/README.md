# Infrastructure and Security Automation (`infra/`)

This directory contains infrastructure automation and security policy provisioning scripts for **Portfolio Copilot**.

---

## Model Armor Floor Settings

Google Cloud [Model Armor](https://cloud.google.com/model-armor) provides centralized, project-wide inspection, sanitization, and audit logging across Vertex AI (`AI_PLATFORM`) and Google Model Context Protocol servers (`GOOGLE_MCP_SERVER`, e.g., BigQuery MCP and Firestore MCP).

### Scripts

| Script | Description | Usage |
|---|---|---|
| [`setup_model_armor.sh`](setup_model_armor.sh) | Shell wrapper to enable `modelarmor.googleapis.com` and configure Floor Settings. | `./infra/setup_model_armor.sh [PROJECT_ID] [ENABLE_MODEL_ARMOR] [ENFORCEMENT_MODE]` |
| [`model_armor_floor_settings.py`](model_armor_floor_settings.py) | Python CLI & REST client for inspecting and applying Floor Settings. | `python3 infra/model_armor_floor_settings.py --project=<PROJECT_ID> --describe` |

### Configuration Options

- **Enforcement Toggle:** Enabled by default (`--enable` / `ENABLE_MODEL_ARMOR=true`). To disable enforcement, pass `--disable` or set `ENABLE_MODEL_ARMOR=false`.
- **Mode:** Defaults to `INSPECT_ONLY` with Cloud Logging for monitoring without blocking traffic. Can be set to `INSPECT_AND_BLOCK`.
- **RAI Filters:** Hate Speech, Dangerous Content, Sexually Explicit, Harassment (Confidence: `HIGH`).
- **Prompt Injection & Jailbreak:** Confidence `MEDIUM_AND_ABOVE`.
- **SDP:** Basic config enforcement `ENABLED`.
- **Malicious URI:** Enforcement `ENABLED`.
- **Multi-language Detection:** `ENABLED`.
