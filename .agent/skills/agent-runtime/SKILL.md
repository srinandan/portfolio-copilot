---
name: agent-runtime
description: >-
  How to inspect, query, and manage Agent Runtime (fka Agent Engine) in
  this repo — the correct Python SDK surface, the concrete helper scripts
  to prefer, and the exact `gcloud` command groups that do not exist and
  must not be attempted. Use this before running any command against
  Agent Runtime for troubleshooting, listing, describing, or deleting
  deployed engines.
metadata:
  audience: coding-agent
  version: "0.1.0"
---

# Agent Runtime (fka Agent Engine)

Agent Runtime is Google Cloud's managed runtime for deploying agents (the
service was renamed from "Agent Engine"; the underlying API surface still
uses the older `ReasoningEngine` resource name). This repo deploys its
orchestrator onto Agent Runtime as a container — see
[ADR-0008](../../../docs/adr/0008-python-for-orchestrator.md).

## Rule 1 — do not invent gcloud commands

Agent Runtime has **no dedicated `gcloud` command group**. When you find
yourself typing any of these, stop:

| Do NOT run                                    | Why                     |
| --------------------------------------------- | ----------------------- |
| `gcloud ai reasoning-engines ...`             | Does not exist          |
| `gcloud ai-platform ...`                      | Legacy group, removed   |
| `gcloud ai agents ...` / `gcloud ai engines`  | Does not exist          |
| `gcloud agent-registry ...`                   | Does not exist          |
| `gcloud alpha agent-registry agents ...`      | Does not exist          |
| `gcloud alpha agents ...`                     | Does not exist          |

These will fail with `ERROR: (gcloud.<x>) Invalid choice ...` — not a
signal to try another guess. The control plane is the Vertex AI SDK.

Do NOT copy the fallback command list in `scripts/deploy_managed_agent.py`
into a fresh troubleshooting session — those `candidate_commands` blocks
exist only because that script has to run against multiple SDK versions
during install; every branch there is expected to fail on a stock
install and is not a menu of "try one of these".

`gcloud` groups that *do* work and are fair game: `gcloud logging read`,
`gcloud projects add-iam-policy-binding`, `gcloud secrets`, `gcloud
builds submit`, `gcloud services enable aiplatform.googleapis.com`.

## Rule 2 — reach for the Python helpers first

Everything you'd want to do to a deployed Agent Runtime instance is
covered by two scripts in `scripts/`. Use them; only drop to raw SDK
calls if the operation is genuinely absent.

| Operation             | Command                                                          |
| --------------------- | ---------------------------------------------------------------- |
| List engines          | `uv run scripts/agent_engine_admin.py list --project=$PROJECT_ID` |
| Filter by display     | `... list --display-name=portfolio-copilot-agent`                |
| Describe one engine   | `... describe --engine=portfolio-copilot-agent`                  |
| Query an engine       | `... query --engine=portfolio-copilot-agent --input="hello"`     |
| Delete an engine      | `... delete --engine=portfolio-copilot-agent` (prompts)          |
| Tail logs (1h, ERROR) | `... logs --engine=portfolio-copilot-agent --severity=ERROR`     |
| Deploy / update       | `scripts/deploy_agent_engine.py --container-uri=...`             |
| First-time setup      | `scripts/setup_agent_engine.sh`                                  |

`--engine` accepts either the full resource name
(`projects/.../locations/.../reasoningEngines/<id>`) or the deployed
`display_name`; the helper resolves the display name for you via
`agent_engines.list`.

## Rule 3 — the SDK surface, if you need it directly

The Python entry point is
[`google-cloud-aiplatform[agent_engines]`](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/deploy)
via the `vertexai` package. Always pin `api_version="v1beta1"` — that's
what the Agent Runtime endpoints live under today.

```python
import vertexai

client = vertexai.Client(
    project="my-project",
    location="us-central1",
    http_options=dict(api_version="v1beta1"),
)

# List
for engine in client.agent_engines.list(config={"filter": 'display_name="foo"'}):
    print(engine.api_resource.name)

# Create / update
client.agent_engines.create(config={"display_name": "foo", "container_spec": {...}})
client.agent_engines.update(name="projects/.../reasoningEngines/123", config={...})

# Query
engine.query(input="hello")

# Delete
client.agent_engines.delete(name="projects/.../reasoningEngines/123")
```

Anything the helper script does not cover should be added there rather
than re-implemented ad hoc — that's how the "don't guess at gcloud"
rule stays enforceable over time.

## Debugging checklist

When Agent Runtime looks broken:

1. `agent_engine_admin.py list` — confirm the engine actually exists
   in the project/region you think it does.
2. `agent_engine_admin.py describe --engine=<name>` — check the
   `state`, `container_spec.image_uri`, and `env_vars` match what you
   deployed.
3. `agent_engine_admin.py logs --engine=<name> --severity=ERROR` —
   Cloud Logging for the `ReasoningEngine` resource type.
4. If the container failed to start, look for image-pull or IAM errors
   in the logs, then check `setup_agent_engine.sh` for the Artifact
   Registry reader grant on the service agent.
5. If the SDK itself errors, verify `aiplatform.googleapis.com` is
   enabled: `gcloud services list --enabled --filter=aiplatform`.
