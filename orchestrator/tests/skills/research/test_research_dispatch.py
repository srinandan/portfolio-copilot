from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.contracts.research_brief import ConfidenceLevel, ResearchBrief
from orchestrator.planner import SKILL_PLANS, _execute_skill


@pytest.fixture
def sample_research_brief():
    return ResearchBrief(
        research_run_id="run_123",
        summary="Tech sector outlook is positive.",
        sources=["https://example.com/report"],
        confidence=ConfidenceLevel.HIGH,
        as_of=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
@patch("orchestrator.planner.emit_skill_invoked_audit")
@patch("orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock)
async def test_research_dispatch_happy_path(mock_dispatch, mock_emit_invoked, sample_research_brief):
    mock_dispatch.return_value = sample_research_brief

    context = {}
    ctx = MagicMock()
    plan = SKILL_PLANS["private-research"]

    payload = await _execute_skill(
        plan,
        "private-research",
        "user_123",
        {"research_question": "What is MSFT sentiment?"},
        context,
        ctx,
    )

    assert payload == sample_research_brief.model_dump()
    assert "research_briefs" in context
    assert len(context["research_briefs"]) == 1
    assert context["research_briefs"][0] == sample_research_brief.model_dump()
    mock_emit_invoked.assert_called_once()


@pytest.mark.asyncio
@patch("orchestrator.planner.emit_skill_invoked_audit")
@patch("orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock)
async def test_research_dispatch_skips_without_question(mock_dispatch, mock_emit_invoked):
    context = {}
    ctx = MagicMock()
    plan = SKILL_PLANS["private-research"]

    payload = await _execute_skill(
        plan,
        "private-research",
        "user_123",
        {},
        context,
        ctx,
    )

    assert payload is None
    mock_dispatch.assert_not_called()
    mock_emit_invoked.assert_not_called()


@pytest.mark.asyncio
@patch("orchestrator.planner.emit_skill_invoked_audit")
@patch("orchestrator.planner.emit_skill_failed_audit")
@patch("orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock)
async def test_research_dispatch_ma_failure_raises(mock_dispatch, mock_emit_failed, mock_emit_invoked):
    mock_dispatch.side_effect = RuntimeError("MA search service failed")

    context = {}
    ctx = MagicMock()
    plan = SKILL_PLANS["private-research"]

    with pytest.raises(RuntimeError, match="MA search service failed"):
        await _execute_skill(
            plan,
            "private-research",
            "user_123",
            {"research_question": "What is MSFT sentiment?"},
            context,
            ctx,
        )

    mock_emit_failed.assert_called_once()
    assert "dispatch_failed" in mock_emit_failed.call_args[1]["error"]
    mock_emit_invoked.assert_called_once()
