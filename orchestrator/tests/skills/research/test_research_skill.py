from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.adk.events import Event

from orchestrator.contracts import ConfidenceLevel, ResearchBrief
from orchestrator.skills.research import managed_research_agent_node


@pytest.mark.asyncio
async def test_managed_research_agent_node_success():
    """Verifies that research skill executes ManagedAgent and returns structured ResearchBrief."""
    ctx = MagicMock()
    ctx.run_node = AsyncMock()

    now = datetime.now(timezone.utc)
    expected_brief = ResearchBrief(
        research_run_id="run-123",
        summary="Tech sector sentiment remains bullish ahead of earnings.",
        sources=["https://example.com/msft-analysis"],
        confidence=ConfidenceLevel.HIGH,
        as_of=now,
    )
    ctx.run_node.return_value = expected_brief

    with patch("orchestrator.skills.research.AgentRegistryClient.get_skill_content", new_callable=AsyncMock) as mock_get_content:
        mock_get_content.return_value = "# Research Skill\nPerform market analysis."

        result = await managed_research_agent_node._func(
            ctx,
            {"research_question": "Provide market sentiment for Microsoft (MSFT)"},
        )

        mock_get_content.assert_awaited_once_with("research")
        assert isinstance(result, ResearchBrief)
        assert result.research_run_id == "run-123"
        assert result.summary == "Tech sector sentiment remains bullish ahead of earnings."
        assert result.confidence == ConfidenceLevel.HIGH
        assert result.sources == ["https://example.com/msft-analysis"]


@pytest.mark.asyncio
async def test_managed_research_agent_node_dict_response():
    """Verifies that research skill converts and validates a raw dict output into ResearchBrief."""
    ctx = MagicMock()
    ctx.run_node = AsyncMock()

    ctx.run_node.return_value = {
        "research_run_id": "run-dict-456",
        "summary": "Analyst consensus suggests moderate growth for semiconductor stocks.",
        "sources": ["https://example.com/nvda"],
        "confidence": "medium",
        "as_of": "2026-08-01T12:00:00Z",
    }

    with patch("orchestrator.skills.research.AgentRegistryClient.get_skill_content", new_callable=AsyncMock) as mock_get_content:
        mock_get_content.return_value = "# Research Skill\nPerform market analysis."

        result = await managed_research_agent_node._func(
            ctx,
            {"research_question": "Analyze NVDA consensus"},
        )

        assert isinstance(result, ResearchBrief)
        assert result.research_run_id == "run-dict-456"
        assert result.confidence == ConfidenceLevel.MEDIUM
        assert "semiconductor stocks" in result.summary


@pytest.mark.asyncio
async def test_managed_research_agent_node_adk_workflow_stream():
    """Verifies that research skill executes through ADK runner generator stream."""
    ctx = MagicMock()
    ctx.run_node = AsyncMock()

    ctx.run_node.return_value = {
        "research_run_id": "run-adk-789",
        "summary": "Cloud infrastructure spending accelerated.",
        "sources": [],
        "confidence": "high",
        "as_of": "2026-08-01T12:00:00Z",
    }

    with patch("orchestrator.skills.research.AgentRegistryClient.get_skill_content", new_callable=AsyncMock) as mock_get_content:
        mock_get_content.return_value = "# Research Skill\nPerform market analysis."

        gen = managed_research_agent_node.run(
            ctx=ctx,
            node_input={"research_question": "Check cloud spending"},
        )
        result = None
        async for item in gen:
            result = item.output if isinstance(item, Event) else item

        assert result is not None
        assert result["research_run_id"] == "run-adk-789"
        assert result["confidence"] == ConfidenceLevel.HIGH


@pytest.mark.asyncio
async def test_managed_research_agent_node_missing_question_raises():
    """Verifies B2 & M3: Missing, non-dict, or empty research_question raises ValueError."""
    ctx = MagicMock()

    with pytest.raises(ValueError, match="research_question is required"):
        await managed_research_agent_node._func(ctx, {})

    with pytest.raises(ValueError, match="research_question is required"):
        await managed_research_agent_node._func(ctx, {"research_question": "   "})

    with pytest.raises(ValueError, match="research_question is required"):
        await managed_research_agent_node._func(ctx, "plain string input without dict")


@pytest.mark.asyncio
async def test_managed_research_agent_node_registry_failure_propagates():
    """Verifies B1: Agent Registry retrieval failure raises rather than silently degrading."""
    ctx = MagicMock()

    with patch("orchestrator.skills.research.AgentRegistryClient.get_skill_content", new_callable=AsyncMock) as mock_get_content:
        mock_get_content.side_effect = ConnectionError("Agent Registry endpoint unreachable")

        with pytest.raises(RuntimeError, match="Failed to resolve research skill content from registry"):
            await managed_research_agent_node._func(
                ctx,
                {"research_question": "Check AAPL market drivers"},
            )


@pytest.mark.asyncio
async def test_managed_research_agent_node_malformed_result_fallback():
    """Verifies B4: Malformed dict or non-contract result falls back to valid low-confidence ResearchBrief."""
    ctx = MagicMock()
    ctx.run_node = AsyncMock()

    # Returns malformed dict with missing required confidence field
    ctx.run_node.return_value = {
        "summary": "Some raw unstructured text output",
        "invalid_field": 12345,
    }

    with patch("orchestrator.skills.research.AgentRegistryClient.get_skill_content", new_callable=AsyncMock) as mock_get_content:
        mock_get_content.return_value = "# Research Skill\nPerform market analysis."

        result = await managed_research_agent_node._func(
            ctx,
            {"research_question": "Evaluate micro-cap stock"},
        )

        assert isinstance(result, ResearchBrief)
        assert result.research_run_id is not None
        assert result.confidence == ConfidenceLevel.LOW
        assert result.as_of is not None
