import os

import pytest
from google.adk.agents import ManagedAgent


@pytest.mark.skipif(
    not os.environ.get("MANAGED_AGENT_ID"),
    reason="MANAGED_AGENT_ID environment variable not set; skipping live Managed Agent integration test.",
)
def test_managed_agent_provisioned_smoke():
    agent_id = os.environ.get("MANAGED_AGENT_ID")
    assert agent_id is not None
    assert "agents/" in agent_id or agent_id.startswith("antigravity-")

    agent = ManagedAgent(
        name="worker_smoke_test",
        description="A smoke test worker agent",
        agent_id=agent_id,
    )
    assert agent.name == "worker_smoke_test"
    assert agent.agent_id == agent_id
