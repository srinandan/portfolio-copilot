import os

import pytest
from google.adk.agents import ManagedAgent

from orchestrator.managed_agents.secret_loader import DEFAULT_MANAGED_AGENT_ID
from orchestrator.managed_agents.worker import get_worker_agent_id


def _should_skip() -> bool:
    if os.environ.get("RUN_INTEGRATION_TESTS") == "1":
        return False
    agent_id = get_worker_agent_id()
    return agent_id == DEFAULT_MANAGED_AGENT_ID


@pytest.mark.skipif(
    _should_skip(),
    reason="No live MANAGED_AGENT_ID in env or Secret Manager (and RUN_INTEGRATION_TESTS!=1); skipping integration smoke test.",
)
def test_managed_agent_provisioned_smoke():
    agent_id = get_worker_agent_id()
    assert agent_id is not None
    assert agent_id != DEFAULT_MANAGED_AGENT_ID, (
        f"Expected real Managed Agent ID from Secret Manager or env, but got placeholder {agent_id}"
    )
    assert (
        "agents/" in agent_id or agent_id.startswith("antigravity-") or "worker" in agent_id or "portfolio" in agent_id
    )

    agent = ManagedAgent(
        name="worker_smoke_test",
        description="A smoke test worker agent",
        agent_id=agent_id,
    )
    assert agent.name == "worker_smoke_test"
    assert agent.agent_id == agent_id
