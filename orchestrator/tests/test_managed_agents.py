import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.adk import Context
from google.adk.tools import google_search

from orchestrator.contracts import (
    Goal,
    GoalsOnboardingResult,
    ProposedActionRationale,
    ResearchBrief,
    RiskTolerance,
    SpendingNarrative,
    TargetAllocation,
)
from orchestrator.managed_agents import (
    OUTPUT_SCHEMA_BY_SKILL,
    build_worker_managed_agent,
    dispatch_managed_skill,
    get_skill_tools,
    get_worker_agent_id,
)


def test_get_worker_agent_id():
    with patch.dict(os.environ, {"MANAGED_AGENT_ID": "projects/test/agents/worker-1"}):
        assert get_worker_agent_id() == "worker-1"

    with (
        patch.dict(os.environ, {}, clear=True),
        patch("orchestrator.managed_agents.secret_loader._fetch_from_secret_manager", return_value=None),
        patch("orchestrator.managed_agents.secret_loader._CACHED_AGENT_ID", None),
    ):
        assert get_worker_agent_id() == "antigravity-preview-05-2026"


def test_build_worker_managed_agent():
    agent = build_worker_managed_agent(
        name="test-skill-name",
        description="Instructions for test skill",
        output_schema=GoalsOnboardingResult,
        tools=[google_search],
        agent_id="test-agent-id",
    )
    assert agent.name == "test_skill_name"
    assert agent.description == "Instructions for test skill"
    assert agent.agent_id == "test-agent-id"
    assert agent.output_schema == GoalsOnboardingResult
    assert google_search in agent.tools


def test_get_skill_tools():
    assert get_skill_tools("research") == [google_search]
    assert get_skill_tools("private-research") == [google_search]
    assert get_skill_tools("goals-onboarding") == []
    assert get_skill_tools("spending-analysis") == []


def test_output_schema_by_skill():
    from orchestrator.managed_agents.dispatcher import normalize_private_skill_name

    assert OUTPUT_SCHEMA_BY_SKILL["private-goals-onboarding"] == GoalsOnboardingResult
    assert OUTPUT_SCHEMA_BY_SKILL["private-spending-analysis"] == SpendingNarrative
    assert OUTPUT_SCHEMA_BY_SKILL["private-research"] == ResearchBrief
    assert OUTPUT_SCHEMA_BY_SKILL.get(normalize_private_skill_name("goals-onboarding")) == GoalsOnboardingResult
    assert OUTPUT_SCHEMA_BY_SKILL.get(normalize_private_skill_name("private-goals-onboarding")) == GoalsOnboardingResult


@pytest.mark.asyncio
@patch("orchestrator.managed_agents.dispatcher.resolve_skill_instructions")
async def test_dispatch_managed_skill_success_typed_output(mock_resolve):
    mock_resolve.return_value = "Instructions from registry"

    mock_ctx = AsyncMock(spec=Context)
    expected_result = GoalsOnboardingResult(
        user_id="user1",
        primary_goal=Goal(name="Retirement", target_amount_usd=1000000.0, target_date="2045-01-01"),
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[TargetAllocation(asset_class="equity", target_percent=60, min_percent=50, max_percent=70)],
        interview_summary="User seeks retirement growth.",
    )
    mock_ctx.run_node.return_value = expected_result

    result = await dispatch_managed_skill(
        skill_name="private-goals-onboarding",
        node_input={"user_id": "user1"},
        ctx=mock_ctx,
    )

    assert isinstance(result, GoalsOnboardingResult)
    assert result.user_id == "user1"
    assert result.risk_tolerance == RiskTolerance.MODERATE
    mock_resolve.assert_awaited_once_with("private-goals-onboarding", client=None)
    mock_ctx.run_node.assert_awaited_once()


@pytest.mark.asyncio
@patch("orchestrator.managed_agents.dispatcher.resolve_skill_instructions")
async def test_dispatch_managed_skill_dict_coercion(mock_resolve):
    mock_resolve.return_value = "Instructions from registry"

    mock_ctx = AsyncMock(spec=Context)
    raw_dict = {
        "narrative_summary": "Spending is within normal range.",
        "anomaly_commentary": [],
    }
    mock_ctx.run_node.return_value = raw_dict

    result = await dispatch_managed_skill(
        skill_name="private-spending-analysis",
        node_input={"user_id": "user1"},
        ctx=mock_ctx,
    )

    assert isinstance(result, SpendingNarrative)
    assert result.narrative_summary == "Spending is within normal range."


def test_dispatch_managed_skill_spending_uses_narrow_schema():
    assert OUTPUT_SCHEMA_BY_SKILL["private-spending-analysis"] is SpendingNarrative


def test_dispatch_managed_skill_action_drafting_uses_narrow_schema():
    assert OUTPUT_SCHEMA_BY_SKILL["private-action-drafting"] is ProposedActionRationale


@pytest.mark.asyncio
@patch("orchestrator.managed_agents.dispatcher.resolve_skill_instructions")
async def test_dispatch_managed_skill_raises_on_unvalidatable_output(mock_resolve):
    mock_resolve.return_value = "Instructions from registry"

    mock_ctx = AsyncMock(spec=Context)
    mock_ctx.run_node.return_value = {"unrecognized_field": 123}

    with pytest.raises(RuntimeError, match="could not be constructed from Managed Agent output"):
        await dispatch_managed_skill(
            skill_name="private-action-drafting",
            node_input={"user_id": "user1"},
            ctx=mock_ctx,
        )


@pytest.mark.asyncio
@patch("orchestrator.managed_agents.dispatcher.resolve_skill_instructions")
async def test_dispatch_managed_skill_returns_pydantic_instance_directly(mock_resolve):
    mock_resolve.return_value = "Instructions from registry"

    mock_ctx = AsyncMock(spec=Context)
    instance = ProposedActionRationale(
        rationale="Direct Pydantic instance",
        supporting_research_refs=["ref1"],
    )
    mock_ctx.run_node.return_value = instance

    result = await dispatch_managed_skill(
        skill_name="private-action-drafting",
        node_input={"user_id": "user1"},
        ctx=mock_ctx,
    )
    assert result is instance


@pytest.mark.asyncio
@patch("orchestrator.managed_agents.dispatcher.resolve_skill_instructions")
async def test_dispatch_managed_skill_research_cache_hit(mock_resolve):
    from orchestrator.contracts.research_brief import ConfidenceLevel, ResearchBrief
    from orchestrator.managed_agents.dispatcher import _RESEARCH_CACHE

    _RESEARCH_CACHE.clear()
    mock_resolve.return_value = "Research instructions"

    mock_ctx = AsyncMock(spec=Context)
    expected_brief = ResearchBrief(
        research_run_id="run_123",
        query="market conditions for AAPL",
        summary="Bullish outlook.",
        sources=["https://example.com"],
        confidence=ConfidenceLevel.HIGH,
        as_of=1700000000,
    )
    mock_ctx.run_node.return_value = expected_brief

    # First dispatch -> calls ctx.run_node
    res1 = await dispatch_managed_skill(
        skill_name="private-research",
        node_input={"research_question": "market conditions for AAPL"},
        ctx=mock_ctx,
    )
    assert res1 == expected_brief
    assert mock_ctx.run_node.await_count == 1

    # Second dispatch with same question -> cache hit, does not call ctx.run_node again
    res2 = await dispatch_managed_skill(
        skill_name="private-research",
        node_input={"research_question": "market conditions for AAPL"},
        ctx=mock_ctx,
    )
    assert res2 == expected_brief
    assert mock_ctx.run_node.await_count == 1
    _RESEARCH_CACHE.clear()


@pytest.mark.asyncio
@patch("orchestrator.managed_agents.dispatcher.resolve_skill_instructions")
async def test_dispatch_managed_skill_coerces_goals_onboarding_dict(mock_resolve):
    from orchestrator.contracts.goals_onboarding import GoalsOnboardingResult
    from orchestrator.contracts.ips import RiskTolerance

    mock_resolve.return_value = "Goals onboarding instructions"

    mock_ctx = AsyncMock(spec=Context)
    mock_ctx.run_node.return_value = {
        "user_id": "usr_123",
        "risk_tolerance": "moderate",
        "time_horizon_years": 15,
        "interview_summary": "Balanced portfolio for retirement in 15 years.",
    }

    result = await dispatch_managed_skill(
        skill_name="private-goals-onboarding",
        node_input={"user_id": "usr_123"},
        ctx=mock_ctx,
    )
    assert isinstance(result, GoalsOnboardingResult)
    assert result.user_id == "usr_123"
    assert result.risk_tolerance == RiskTolerance.MODERATE
    assert result.time_horizon_years == 15
    assert len(result.target_allocation) == 3


@pytest.mark.asyncio
@patch("orchestrator.managed_agents.dispatcher.resolve_skill_instructions")
async def test_dispatch_managed_skill_extracts_from_session_events(mock_resolve):
    from google.genai.types import Part

    from orchestrator.contracts.goals_onboarding import GoalsOnboardingResult

    mock_resolve.return_value = "Goals onboarding instructions"

    mock_event = MagicMock()
    mock_event.author = "goals_onboarding"
    mock_event.output = None
    mock_event.content.parts = [
        Part.from_text(text='{"user_id": "usr_456", "risk_tolerance": "aggressive", "time_horizon_years": 20}')
    ]

    mock_session = MagicMock()
    mock_session.events = [mock_event]

    mock_ctx = AsyncMock(spec=Context)
    mock_ctx.run_node.return_value = None
    mock_ctx.session = mock_session

    result = await dispatch_managed_skill(
        skill_name="private-goals-onboarding",
        node_input={"user_id": "usr_456"},
        ctx=mock_ctx,
    )
    assert isinstance(result, GoalsOnboardingResult)
    assert result.user_id == "usr_456"
    assert result.time_horizon_years == 20
