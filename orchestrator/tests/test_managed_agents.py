import os
from unittest.mock import AsyncMock, patch

import pytest
from google.adk import Context
from google.adk.tools import google_search

from orchestrator.contracts import (
    Goal,
    GoalsOnboardingResult,
    ResearchBrief,
    RiskTolerance,
    SpendingReport,
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
        assert get_worker_agent_id() == "projects/test/agents/worker-1"

    with patch.dict(os.environ, {}, clear=True):
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
    assert OUTPUT_SCHEMA_BY_SKILL["goals-onboarding"] == GoalsOnboardingResult
    assert OUTPUT_SCHEMA_BY_SKILL["spending-analysis"] == SpendingReport
    assert OUTPUT_SCHEMA_BY_SKILL["research"] == ResearchBrief


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
        "user_id": "user1",
        "total_income_usd": 10000.0,
        "total_outflow_usd": 6000.0,
        "savings_rate": 0.4,
        "reserve_months": 6.0,
        "category_breakdown": [],
        "anomalies": [],
        "narrative_summary": "Spending is within normal range.",
    }
    mock_ctx.run_node.return_value = raw_dict

    result = await dispatch_managed_skill(
        skill_name="private-spending-analysis",
        node_input={"user_id": "user1"},
        ctx=mock_ctx,
    )

    assert isinstance(result, SpendingReport)
    assert result.savings_rate == 0.4
    assert result.reserve_months == 6.0
