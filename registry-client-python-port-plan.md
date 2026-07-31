# Plan: Port Agent Registry client to Python, wire into the planner

This is the natural next step regardless of the `ManagedAgent` finding
— `planner.py`'s `get_skills_from_registry` is currently a hardcoded
stub (`return ["research", "action_drafting"]`), and this is what
replaces it with the real thing.

## Reference implementation

Port `pkg/registry/client.go` behavior faithfully — don't redesign it.
It has exactly two public operations:

1. **`ListAuthorizedSkills`** — `GET .../skills`, paginated, filters
   out anything with `targetState == "TARGET_STATE_DISABLED"`. This is
   the live-revocation mechanism (ADR-0006) — the filter is the whole
   point, not incidental.
2. **`GetSkillContent(skill_id)`** — resolves `private-{skill_id}` (per
   ADR-0006's namespace convention), fetches the skill resource to find
   its `defaultRevision`, downloads that revision as a zip
   (`?alt=media`), extracts `SKILL.md` from it, returns the text.

## Target Python implementation

New file: `orchestrator/src/orchestrator/registry_client.py`

```python
import httpx
import zipfile
import io
from dataclasses import dataclass
from google.auth import default as google_auth_default
from google.auth.transport.requests import Request as GoogleAuthRequest

DEFAULT_BASE_URL = "https://agentregistry.googleapis.com/v1"

@dataclass
class Skill:
    name: str
    target_state: str
    default_revision: str

class AgentRegistryClient:
    def __init__(self, project_id: str, location: str, base_url: str = DEFAULT_BASE_URL, http_client: httpx.AsyncClient | None = None):
        self.project_id = project_id
        self.location = location
        self.base_url = base_url
        self._http_client = http_client  # inject for tests; build authenticated client if None

    async def list_authorized_skills(self) -> list[Skill]:
        """Paginated GET .../skills, filters out TARGET_STATE_DISABLED."""
        ...

    async def get_skill_content(self, skill_id: str) -> str:
        """Resolve private-{skill_id} -> defaultRevision -> zip -> SKILL.md text."""
        ...
```

**Auth:** the Go client uses `golang.org/x/oauth2/google.DefaultClient`
(Application Default Credentials). The Python equivalent is
`google.auth.default()` + attaching the resulting credentials to an
`httpx.AsyncClient`'s auth flow — `google-adk` likely already pulls in
`google-auth` transitively (confirm in `uv.lock` rather than assuming);
add it explicitly to `pyproject.toml` if it isn't already resolvable.

**Why `httpx`, not `requests`:** it's already a `pyproject.toml`
dependency (`httpx>=0.28.1`), and it supports async, which matches
`planner.py`'s `async def` nodes — don't introduce a second HTTP
library for this.

## Wire into `planner.py`

Replace the stub:

```python
@node(name="get_skills", rerun_on_resume=False)
async def get_skills_from_registry(ctx: Context, node_input: Any):
    """Queries the Agent Registry for available skills."""
    project_id = os.environ.get("PROJECT_ID", "dummy-project")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    client = AgentRegistryClient(project_id=project_id, location=location)
    skills = await client.list_authorized_skills()
    return [s.name for s in skills]
```

(Adjust exactly how the client gets constructed/injected — a fresh
client per call vs. one reused across the workflow's lifetime is an
implementation detail worth deciding deliberately, not defaulting to
whichever is easiest. Given the client itself doesn't hold per-call
state, reusing one instance across the orchestrator's lifetime is
probably fine — but that's a judgment call, not dictated by anything
above.)

## Tests

Match `pkg/registry/client_test.go`'s approach — mock the HTTP layer,
never hit the real Agent Registry API in unit tests (per
`.agent/skills/unit-testing/SKILL.md`'s Python section: "External calls
... go behind a small interface/protocol at the point of use, with
fakes for tests"). Cases to cover, mirroring what the Go tests almost
certainly already check:

- `list_authorized_skills` excludes a skill with
  `target_state: "TARGET_STATE_DISABLED"`
- `list_authorized_skills` follows pagination (`nextPageToken`) across
  multiple pages
- `get_skill_content` correctly resolves the `private-{skill_id}`
  prefix
- `get_skill_content` extracts `SKILL.md` specifically from a zip
  containing other files (not just "the only file in the zip")
- `get_skill_content` raises a clear error if a skill has no
  `defaultRevision`, or if `SKILL.md` isn't found in the zip

## Acceptance criteria

- `get_skills_from_registry` in `planner.py` calls the real client, no
  hardcoded skill list remains
- `pytest --cov` passes, including the new registry client tests
- A revocation scenario is testable: mock a skill as
  `TARGET_STATE_DISABLED`, confirm `list_authorized_skills` excludes it
  — this is the Python-side proof of the same property
  `pkg/registry/client_test.go` presumably already verifies on the Go
  side
- `README.md`/`AGENTS.md` need no changes — this fills in work already
  documented as pending, doesn't change scope or structure
