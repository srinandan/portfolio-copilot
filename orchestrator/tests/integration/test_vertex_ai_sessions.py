import json
import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from orchestrator.contracts.ips import RelatedIPSVersion
from orchestrator.contracts.proposed_action import (
    ActionStatus,
    ActionType,
    OrderType,
    ProposedAction,
    Side,
    SkillVersionRef,
)
from orchestrator.contracts.reviewer_verdict import ReviewerVerdict, RuleResult
from orchestrator.session_manager import SessionManager


def _should_skip() -> bool:
    if os.environ.get("RUN_INTEGRATION_TESTS") == "1" and os.environ.get("AGENT_ENGINE_ID"):
        return False
    return True


def test_session_manager_in_memory_default():
    """Verify SessionManager defaults to InMemory services when AGENT_ENGINE_ID is not set."""
    with patch.dict(os.environ, {}, clear=True):
        manager = SessionManager()
        assert manager.session_service.__class__.__name__ == "InMemorySessionService"
        assert manager.memory_service.__class__.__name__ == "InMemoryMemoryService"


def test_session_manager_vertex_ai_services():
    """Verify SessionManager instantiates Agent Platform services when AGENT_ENGINE_ID is set."""
    with (
        patch.dict(
            os.environ,
            {
                "AGENT_ENGINE_ID": "projects/p/locations/l/agentEngines/test-engine",
                "PROJECT_ID": "dummy-project",
                "GOOGLE_CLOUD_PROJECT": "dummy-project",
            },
        ),
        patch("orchestrator.session_manager.VertexAiSessionService") as mock_session_cls,
        patch("orchestrator.session_manager.VertexAiMemoryBankService") as mock_memory_cls,
    ):
        manager = SessionManager()
        mock_session_cls.assert_called_once_with(project="dummy-project", location="us-central1")
        mock_memory_cls.assert_called_once_with(
            project="dummy-project",
            location="us-central1",
            agent_engine_id="projects/p/locations/l/agentEngines/test-engine",
        )
        assert manager.session_service == mock_session_cls.return_value
        assert manager.memory_service == mock_memory_cls.return_value


def test_hitl_state_json_serializable_invariant():
    """Verifies that all structures saved in ctx.state are strictly JSON-serializable

    for Agent Platform Sessions compatibility and round-trip without corruption.
    """
    action = ProposedAction(
        action_id="act_vtx_1",
        session_id="sess_vtx_1",
        type=ActionType.TRADE,
        ticker="GOOGL",
        side=Side.BUY,
        quantity=20.0,
        order_type=OrderType.LIMIT,
        limit_price_usd=175.0,
        estimated_price_usd=175.0,
        estimated_value_usd=3500.0,
        rationale="Rebalancing into equity",
        ips_version_referenced=RelatedIPSVersion(ips_id="ips_1", version=1),
        proposed_by_skill_version=SkillVersionRef(skill_name="private-action-drafting", skill_version="0.1.0"),
        status=ActionStatus.DRAFTED,
        created_at=datetime.now(timezone.utc),
    )
    verdict = ReviewerVerdict(
        verdict_id="verdict_vtx_1",
        action_id="act_vtx_1",
        ips_version_checked_against=RelatedIPSVersion(ips_id="ips_1", version=1),
        rule_results=[RuleResult(rule_id="r1", description="rule 1", passed=True)],
        overall_pass=True,
        requires_human_approval=True,
        reviewer_skill_version=SkillVersionRef(skill_name="private-reviewer", skill_version="0.1.0"),
        reviewed_at=datetime.now(timezone.utc),
    )

    state_payload = {
        "hitl_action": action.model_dump(),
        "hitl_verdict": verdict.model_dump(),
        "hitl_edit_rounds": 0,
        "last_authorized_skills": [
            {"name": "projects/p/locations/l/skills/private-goals-onboarding", "default_revision": "rev1"},
            {"name": "projects/p/locations/l/skills/private-reviewer", "default_revision": "rev1"},
        ],
    }

    # Must serialize cleanly without TypeError (e.g. from non-serializable Pydantic models or datetimes)
    serialized = json.dumps(state_payload, default=str)
    deserialized = json.loads(serialized)

    # Must reconstruct Pydantic models from deserialized session state cleanly
    reconstructed_action = ProposedAction.model_validate(deserialized["hitl_action"])
    assert reconstructed_action.action_id == action.action_id
    assert reconstructed_action.ticker == action.ticker

    reconstructed_verdict = ReviewerVerdict.model_validate(deserialized["hitl_verdict"])
    assert reconstructed_verdict.verdict_id == verdict.verdict_id
    assert reconstructed_verdict.overall_pass == verdict.overall_pass


@pytest.mark.skipif(
    _should_skip(),
    reason="No live AGENT_ENGINE_ID in env (or RUN_INTEGRATION_TESTS!=1); skipping live Agent Platform Sessions test.",
)
@pytest.mark.asyncio
async def test_live_vertex_ai_session_service_smoke():
    """Live smoke test against real Agent Platform Sessions service."""
    from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService

    engine_id = os.environ["AGENT_ENGINE_ID"]
    service = VertexAiSessionService(agent_engine_id=engine_id)

    session_id = f"test-smoke-session-{datetime.now(timezone.utc).timestamp()}"
    await service.create_session(app_name="portfolio_copilot_smoke", user_id="smoke_user", session_id=session_id)
    session = await service.get_session(app_name="portfolio_copilot_smoke", user_id="smoke_user", session_id=session_id)
    assert session is not None
