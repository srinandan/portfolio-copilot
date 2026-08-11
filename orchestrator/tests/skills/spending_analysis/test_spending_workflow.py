from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.workflow import Workflow
from google.genai.types import Part, UserContent

from orchestrator.contracts.holdings import HoldingsSnapshot
from orchestrator.planner import root_planner
from orchestrator.registry_client import Skill
from orchestrator.state.spending import preload_spending_facts


def test_preload_spending_facts_default_3_months():
    mock_bq = MagicMock()
    mock_bq.get_spending_snapshot.return_value = (
        {"total_income": 10000.0, "total_outflow": 6000.0},
        [
            {"normalized_category": "dining", "current_month_spend": 800.0, "trailing_3mo_avg": 400.0},
            {"normalized_category": "groceries", "current_month_spend": 500.0, "trailing_3mo_avg": 500.0},
        ],
    )

    mock_fs = MagicMock()
    mock_fs.get_holdings.return_value = HoldingsSnapshot(
        user_id="user_123",
        as_of="2026-08-01T00:00:00Z",
        cash_usd=12000.0,
        positions=[],
    )

    facts = preload_spending_facts("user_123", window_months=3, bq_client=mock_bq, firestore_client=mock_fs)

    assert facts["user_id"] == "user_123"
    assert facts["window_months"] == 3
    assert facts["total_income_usd"] == 10000.0
    assert facts["total_outflow_usd"] == 6000.0
    assert facts["savings_rate"] == 0.4  # (10000 - 6000) / 10000
    assert facts["reserve_months"] == 6.0  # 12000 / (6000 / 3) = 12000 / 2000 = 6
    assert len(facts["anomalies"]) == 1
    assert facts["anomalies"][0]["category"] == "dining"
    assert len(facts["category_breakdown"]) == 2
    mock_bq.get_spending_snapshot.assert_called_once()


def test_preload_spending_facts_dynamic_6_months():
    mock_bq = MagicMock()
    mock_bq.get_spending_snapshot.return_value = (
        {"total_income": 20000.0, "total_outflow": 12000.0},
        [],
    )

    mock_fs = MagicMock()
    mock_fs.get_holdings.return_value = HoldingsSnapshot(
        user_id="user_123",
        as_of="2026-08-01T00:00:00Z",
        cash_usd=10000.0,
        positions=[],
    )

    facts = preload_spending_facts("user_123", window_months=6, bq_client=mock_bq, firestore_client=mock_fs)

    assert facts["window_months"] == 6
    # monthly expenses = 12000 / 6 = 2000; reserve_months = 10000 / 2000 = 5.0
    assert facts["reserve_months"] == 5.0


def test_preload_uses_single_bigquery_call():
    mock_bq = MagicMock()
    mock_bq.get_spending_snapshot.return_value = ({"total_income": 0.0, "total_outflow": 0.0}, [])
    mock_fs = MagicMock()
    mock_fs.get_holdings.return_value = None

    preload_spending_facts("user_123", window_months=3, bq_client=mock_bq, firestore_client=mock_fs)

    assert mock_bq.get_spending_snapshot.call_count == 1


@pytest.mark.asyncio
async def test_spending_postprocess_merges_narrative_onto_preloaded_facts():
    from orchestrator.contracts.spending_analysis import SpendingNarrative
    from orchestrator.planner import _postprocess_spending

    preloaded = {
        "user_id": "user_123",
        "total_income_usd": 12000.0,
        "total_outflow_usd": 7000.0,
        "savings_rate": 0.4167,
        "reserve_months": 4.5,
        "category_breakdown": [{"category": "dining", "amount_usd": 500.0, "percentage": 7.14}],
        "anomalies": [
            {"category": "dining", "current_spend_usd": 500.0, "trailing_avg_usd": 200.0, "description": "surged"}
        ],
    }
    llm_result = SpendingNarrative(
        narrative_summary="Your spending is on track with 41.7% savings rate.",
        anomaly_commentary=["One-time birthday dinner celebration."],
    )

    payload, context_delta = await _postprocess_spending(
        user_id="user_123",
        result=llm_result,
        ctx=MagicMock(),
        input_dict={"preloaded": preloaded},
    )

    report = context_delta["spending_analysis_result"]
    assert report.total_income_usd == 12000.0
    assert report.total_outflow_usd == 7000.0
    assert report.savings_rate == 0.4167
    assert report.reserve_months == 4.5
    assert report.narrative_summary == "Your spending is on track with 41.7% savings rate."
    assert report.anomalies[0].description == "One-time birthday dinner celebration."


@pytest.mark.asyncio
async def test_spending_postprocess_ignores_llm_numeric_hallucination():
    from orchestrator.planner import _postprocess_spending

    preloaded = {
        "user_id": "user_123",
        "total_income_usd": 5000.0,
        "total_outflow_usd": 3000.0,
        "savings_rate": 0.4,
        "reserve_months": 3.0,
        "category_breakdown": [],
        "anomalies": [],
    }
    # Dict output attempting to override numeric fields
    llm_dict = {
        "total_income_usd": 99999.0,
        "savings_rate": 0.99,
        "narrative_summary": "Attempted override of numbers.",
    }

    payload, context_delta = await _postprocess_spending(
        user_id="user_123",
        result=llm_dict,
        ctx=MagicMock(),
        input_dict={"preloaded": preloaded},
    )

    report = context_delta["spending_analysis_result"]
    assert report.total_income_usd == 5000.0
    assert report.savings_rate == 0.4
    assert report.narrative_summary == "Attempted override of numbers."


@pytest.mark.asyncio
async def test_planner_dispatches_spending_analysis_managed_agent():
    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()
    runner = Runner(
        app_name="test_app",
        agent=agent,
        session_service=session_service,
        memory_service=memory_service,
        auto_create_session=True,
    )

    from orchestrator.contracts.spending_analysis import SpendingNarrative

    expected_narrative = SpendingNarrative(
        narrative_summary="Dining showed significant surge; overall savings rate remains solid at 40%.",
        anomaly_commentary=[],
    )

    with (
        patch("orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock) as mock_list,
        patch("orchestrator.planner.preload_spending_facts") as mock_preload,
        patch("orchestrator.planner.emit_skill_invoked_audit"),
        patch("orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock) as mock_dispatch,
    ):
        mock_list.return_value = [
            Skill(
                name="projects/test-proj/locations/global/skills/private-spending-analysis",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="rev1",
            ),
        ]
        mock_preload.return_value = {
            "user_id": "user_123",
            "total_income_usd": 10000.0,
            "total_outflow_usd": 6000.0,
            "savings_rate": 0.4,
            "reserve_months": 6.0,
            "category_breakdown": [],
            "anomalies": [],
        }
        mock_dispatch.return_value = expected_narrative

        response_stream = runner.run_async(
            user_id="user_123",
            session_id="session_spending_1",
            new_message=UserContent(
                parts=[
                    Part.from_text(text='{"user_id": "user_123", "query_intent": "anomaly_check", "window_months": 6}')
                ]
            ),
        )

        events = [e async for e in response_stream]
        assert len(events) > 0

        mock_preload.assert_called_once_with(user_id="user_123", window_months=6)
        assert mock_dispatch.call_args[0][0] == "private-spending-analysis"
        assert mock_dispatch.call_args[1]["node_input"]["user_id"] == "user_123"
        assert mock_dispatch.call_args[1]["node_input"]["query_intent"] == "anomaly_check"
        assert mock_dispatch.call_args[1]["node_input"]["window_months"] == 6
        assert "preloaded" in mock_dispatch.call_args[1]["node_input"]


@pytest.mark.asyncio
async def test_spending_analysis_dispatch_failure_surfaces_error():
    """A spending-analysis dispatch failure must no longer be silently swallowed.

    The old fail-silently fallback (added when the worker routinely timed out at
    60-80s) masked real failures. Now that the #266/#267 fix removed the timeout
    root cause, spending-analysis fails like every other skill: it emits a
    SKILL_INVOCATION_FAILED audit and propagates the error instead of returning a
    fabricated "precomputed" narrative.
    """
    from orchestrator.planner import SKILL_PLANS, _execute_skill

    plan = SKILL_PLANS["private-spending-analysis"]
    ctx = MagicMock()
    input_dict = {"user_id": "user_123", "query_intent": "anomaly_check", "window_months": 3}

    with (
        patch("orchestrator.planner.preload_spending_facts") as mock_preload,
        patch("orchestrator.planner.emit_skill_invoked_audit"),
        patch("orchestrator.planner.emit_skill_failed_audit") as mock_failed,
        patch("orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock) as mock_dispatch,
    ):
        mock_preload.return_value = {
            "user_id": "user_123",
            "total_income_usd": 10000.0,
            "total_outflow_usd": 6000.0,
            "savings_rate": 0.4,
            "reserve_months": 6.0,
            "category_breakdown": [],
            "anomalies": [],
        }
        mock_dispatch.side_effect = TimeoutError("Node 'private_spending_analysis' timed out after 60.0 seconds.")

        with pytest.raises(TimeoutError):
            await _execute_skill(
                plan,
                "projects/test-proj/locations/global/skills/private-spending-analysis",
                "user_123",
                input_dict,
                {},
                ctx,
                registry_entry_id="rev1",
            )

        mock_dispatch.assert_awaited_once()
        # The failure is recorded (surfaced), not hidden.
        mock_failed.assert_called_once()
        assert "dispatch_failed" in mock_failed.call_args[1]["error"]
