from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.workflow import Workflow
from google.genai.types import Part, UserContent

from orchestrator.contracts.holdings import HoldingsSnapshot
from orchestrator.contracts.spending_analysis import CategorySpending, SpendingAnomaly, SpendingReport
from orchestrator.planner import root_planner
from orchestrator.registry_client import Skill
from orchestrator.state.spending import preload_spending_facts


def test_preload_spending_facts_default_3_months():
    mock_bq = MagicMock()
    mock_bq.get_trailing_income_and_outflow.return_value = {
        "total_income": 10000.0,
        "total_outflow": 6000.0,
    }
    mock_bq.get_monthly_spending_totals.return_value = [
        {"normalized_category": "dining", "current_month_spend": 800.0, "trailing_3mo_avg": 400.0},
        {"normalized_category": "groceries", "current_month_spend": 500.0, "trailing_3mo_avg": 500.0},
    ]

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


def test_preload_spending_facts_dynamic_6_months():
    mock_bq = MagicMock()
    mock_bq.get_trailing_income_and_outflow.return_value = {
        "total_income": 20000.0,
        "total_outflow": 12000.0,
    }
    mock_bq.get_monthly_spending_totals.return_value = []

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

    expected_report = SpendingReport(
        user_id="user_123",
        total_income_usd=10000.0,
        total_outflow_usd=6000.0,
        savings_rate=0.4,
        reserve_months=6.0,
        category_breakdown=[CategorySpending(category="dining", amount_usd=800.0, percentage=13.33)],
        anomalies=[
            SpendingAnomaly(
                category="dining",
                current_spend_usd=800.0,
                trailing_avg_usd=400.0,
                description="Dining doubled this month.",
            )
        ],
        narrative_summary="Dining showed significant surge; overall savings rate remains solid at 40%.",
    )

    with (
        patch(
            "orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock
        ) as mock_list,
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
        mock_dispatch.return_value = expected_report

        response_stream = runner.run_async(
            user_id="user_123",
            session_id="session_spending_1",
            new_message=UserContent(parts=[Part.from_text(text='{"user_id": "user_123", "query_intent": "anomaly_check", "window_months": 6}')]),
        )

        events = [e async for e in response_stream]
        assert len(events) > 0

        mock_preload.assert_called_once_with(user_id="user_123", window_months=6)
        assert mock_dispatch.call_args[0][0] == "private-spending-analysis"
        assert mock_dispatch.call_args[1]["node_input"]["user_id"] == "user_123"
        assert mock_dispatch.call_args[1]["node_input"]["query_intent"] == "anomaly_check"
        assert mock_dispatch.call_args[1]["node_input"]["window_months"] == 6
        assert "preloaded" in mock_dispatch.call_args[1]["node_input"]
