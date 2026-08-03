from unittest.mock import MagicMock, patch

import pytest

from orchestrator.skills.portfolio_analysis import portfolio_analysis_skill


@pytest.mark.asyncio
async def test_portfolio_analysis_skill_missing_user_id():
    ctx = MagicMock()
    node_input = {}

    with pytest.raises(ValueError, match="user_id is required"):
        gen = portfolio_analysis_skill.run(ctx=ctx, node_input=node_input)
        async for _ in gen:
            pass

@pytest.mark.asyncio
@patch("orchestrator.skills.portfolio_analysis.FirestoreClient")
async def test_portfolio_analysis_skill_no_ips(mock_firestore_class):
    mock_db = mock_firestore_class.return_value
    mock_db.get_active_ips_by_user.return_value = None

    ctx = MagicMock()
    node_input = {"user_id": "test_user"}

    gen = portfolio_analysis_skill.run(ctx=ctx, node_input=node_input)
    result = None
    async for item in gen:
        result = item.output

    assert result["status"] == "declined"
    assert "No active Investment Policy Statement" in result["message"]

@pytest.mark.asyncio
@patch("orchestrator.skills.portfolio_analysis.FirestoreClient")
@patch("orchestrator.skills.portfolio_analysis.calculate_drift")
async def test_portfolio_analysis_skill_success(mock_calculate_drift, mock_firestore_class):
    mock_db = mock_firestore_class.return_value
    mock_db.get_active_ips_by_user.return_value = {"mock": "ips"}
    mock_db.get_holdings.return_value = {"mock": "holdings"}

    # calculate_drift is synchronous in logic.py, so just use MagicMock
    mock_report = MagicMock()
    mock_report.model_dump.return_value = {"mock": "drift_report_data"}
    mock_calculate_drift.return_value = mock_report

    ctx = MagicMock()
    node_input = {"user_id": "test_user"}

    gen = portfolio_analysis_skill.run(ctx=ctx, node_input=node_input)
    result = None
    async for item in gen:
        result = item.output

    assert result["status"] == "completed"
    assert result["drift_report"] == {"mock": "drift_report_data"}
