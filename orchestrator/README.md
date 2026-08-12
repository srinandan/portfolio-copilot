# Portfolio Copilot Orchestrator

The orchestrator is the dynamic planning engine for Portfolio Copilot. Built with Google Agent Development Kit (ADK) 2.0 dynamic workflows, it discovers capabilities at runtime by querying the Google Cloud Agent Registry rather than relying on a static, hardcoded pipeline.

Deployed to Agent Platform Agent Runtime using the Python custom-agent contract (see [ADR-0008](../docs/adr/0008-python-for-orchestrator.md)).

---

## What It Does

- **Registry-Driven Dynamic Planning**: At runtime, the root planner queries the Agent Registry to discover which skills (`research`, `action_drafting`, `spending_analysis`, `portfolio_analysis`, `goals_onboarding`, `reviewer`) are currently authorized and available, composing an execution plan dynamically.
- **Dynamic Workflows**: Uses ADK's programmatic control flow (`@node`, `Workflow`, `Context.run_node`) to coordinate sub-tasks and adapt mid-session without restarting.
- **State Checkpointing & Resumption**: Leverages ADK session management to pause execution for Human-in-the-Loop (HITL) approvals and resume without re-executing already-completed sub-nodes.
- **Governance & Auditability**: Ensures all planned and executed actions map directly to registered skill versions and approved user scopes.

---

## Project Structure

```
orchestrator/
├── Dockerfile              # Python 3.12-slim container build for Agent Runtime
├── README.md               # Orchestrator documentation
├── cloudbuild.yaml         # Cloud Build CI/CD pipeline configuration
├── pyproject.toml          # Project configuration, dependencies, and test settings
├── src/
│   └── orchestrator/
│       ├── __init__.py     # Package initialization and version
│       ├── contracts/      # Typed Pydantic data models (IPS, Holdings, Actions, Audit, etc.)
│       ├── data/           # Firestore and BigQuery data clients
│       ├── executors/      # Broker (Alpaca paper trading) execution client
│       ├── gates/          # HITL approval and execution governance gates
│       ├── logger.py       # Structured JSON logger with trace propagation
│       ├── managed_agents/ # Managed Agent dispatcher, worker wrapper, and secret loader
│       ├── planner.py      # Root dynamic planner workflow, node definitions, and dispatch logic
│       ├── primitives/     # Deterministic evaluation logic (action drafting, portfolio, spending)
│       ├── progress.py     # Advisory streaming progress channel (report_progress) surfaced to the UI
│       ├── registry_client.py # Agent Registry client and runtime skill discovery
│       ├── reviewer/       # Deterministic safety rule evaluation for reviewer verdicts
│       ├── server.py       # FastAPI HTTP server (/livez, /readyz, /v1/invoke, /v1/resume)
│       ├── session_manager.py # ADK session & memory service manager
│       ├── skills/         # SKILL.md metadata parsing and verification
│       └── state/          # State preloader and fail-closed audit log/state writers
└── tests/
    ├── integration/        # End-to-end full pipeline and Agent Platform Sessions integration tests
    ├── primitives/         # Deterministic logic unit tests (drafting, portfolio, spending)
    ├── reviewer/           # Reviewer deterministic and adversarial test suites
    ├── skills/             # Per-skill golden-path and error-path workflow tests
    ├── state/              # Preloader and writer transactional unit tests
    ├── test_testdata_fixtures.py # Canonical test fixtures schema verification
    ├── test_server.py      # Server lifespan and HTTP endpoint tests
    └── test_planner.py     # Root planner dynamic graph, checkpointing, and revocation tests
```

---

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** (recommended) or standard `pip` + `venv`
- Google Cloud credentials configured if connecting to live GCP services (`Agent Registry`, `Agent Platform`)

---

## Local Setup & Installation

Navigate to the `orchestrator` directory:

```bash
cd orchestrator
```

### Using `uv` (Recommended)

Install dependencies and set up the local virtual environment:

```bash
uv sync
```

### Using `pip`

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Running Tests

Run the test suite with `pytest`:

```bash
PYTHONPATH=. uv run pytest
```

Run tests with test coverage reporting:

```bash
PYTHONPATH=. uv run pytest --cov=src
```

---

## How to Use Locally

### 1. Environment Configuration

When interacting with live Google Cloud services, configure the following environment variables (defaults are used for local mocking):

```bash
export PROJECT_ID="your-gcp-project-id"
export GOOGLE_CLOUD_LOCATION="global"
```

### 2. Programmatic Execution with ADK Runner

You can execute and inspect the dynamic planner locally using ADK's `Runner` and `InMemorySessionService`:

```python
import asyncio
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai.types import UserContent
from src.orchestrator.planner import root_agent


async def main():
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="portfolio_copilot",
        agent=root_agent,
        session_service=session_service,
        auto_create_session=True,
    )

    session_id = "local_dev_session"
    print("Running root planner workflow...")

    response_stream = runner.run_async(
        user_id="dev_user",
        session_id=session_id,
        new_message=UserContent("Rebalance portfolio according to IPS"),
    )

    async for event in response_stream:
        if event.output:
            print(f"Workflow output: {event.output}")


if __name__ == "__main__":
    asyncio.run(main())
```

### 3. Checkpointing & Resumption

The planner supports Human-in-the-Loop (HITL) workflows using interrupts (`RequestInput`). When paused, save the `invocation_id` and resume with the user's response:

```python
from google.genai.types import Part

# Resume a paused workflow by providing the interrupt response
resume_stream = runner.run_async(
    user_id="dev_user",
    session_id=session_id,
    invocation_id=last_event.invocation_id,
    new_message=UserContent(
        parts=[
            Part.from_function_response(
                name="adk_request_input",
                response={"interruptId": interrupt_id, "payload": "approved"},
            )
        ]
    ),
)
```

---

## Docker & Cloud Build Deployment

The orchestrator is containerized using `Dockerfile` based on `python:3.12-slim`:
- Installs `uv` for fast dependency resolution.
- Compiles project requirements via `uv pip install --system --no-cache .`.
- Runs under a non-root `orchestrator` user on port `8080`.
- Container CMD runs `uvicorn orchestrator.server:app` — the FastAPI wrapper
  around `root_agent` that serves the Agent Runtime custom-container contract
  (`/livez`, `/readyz`, `POST /v1/invoke`, `POST /v1/resume`; SSE-encoded ADK
  event streams interleaved with advisory pipeline progress events, see
  [ADR-0018](../docs/adr/0018-streaming-progress-events.md)). `PORT` from the
  environment is honored (defaults to 8080).

### Running & deploying via the Makefile

```bash
# Run locally against your current gcloud project
make -C orchestrator local

# Trigger a manual Cloud Build → Agent Runtime deploy
make -C orchestrator deploy
```

The `deploy` target calls `gcloud builds submit --config=orchestrator/cloudbuild.yaml` with `_COMMIT_SHA=$(git rev-parse --short HEAD)` and the active gcloud region. The Cloud Build pipeline builds and pushes the container image to Artifact Registry, then invokes `scripts/deploy_agent_engine.py --container-uri=<image>` — which uses the Agent Platform SDK's `ReasoningEngineSpec.container_spec` path to create or update the Agent Engine identified by `--display-name` (default `portfolio-copilot-agent`). This is the Agent Platform Agent Runtime custom-container deployment path per [ADR-0008](../docs/adr/0008-python-for-orchestrator.md); the orchestrator does not run on Cloud Run.

For tag-based automatic releases, see [`install/README.md`](../install/README.md) — pushing `v*` git tags fires the triggers created by `scripts/setup_cloudbuild_triggers.sh`.

