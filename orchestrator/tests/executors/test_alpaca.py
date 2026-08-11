from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from alpaca.common.exceptions import APIError
from alpaca.trading.enums import OrderSide
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

from orchestrator.contracts.ips import RelatedIPSVersion
from orchestrator.contracts.proposed_action import (
    ActionStatus,
    ActionType,
    OrderType,
    ProposedAction,
    Side,
    SkillVersionRef,
)
from orchestrator.executors.alpaca import (
    AlpacaExecutionError,
    AlpacaExecutor,
    _load_alpaca_credentials,
)


@pytest.fixture
def sample_proposed_action():
    return ProposedAction(
        action_id="act-alpaca-123",
        session_id="sess-alpaca-1",
        type=ActionType.TRADE,
        ticker="AAPL",
        side=Side.BUY,
        quantity=5.0,
        order_type=OrderType.MARKET,
        estimated_price_usd=150.0,
        estimated_value_usd=750.0,
        rationale="Rebalancing into equity per IPS target.",
        supporting_research_refs=[],
        ips_version_referenced=RelatedIPSVersion(ips_id="ips-1", version=1),
        proposed_by_skill_version=SkillVersionRef(skill_name="private-action-drafting", skill_version="0.2.0"),
        status=ActionStatus.DRAFTED,
        created_at=datetime.now(timezone.utc),
    )


def test_submit_order_success_market(sample_proposed_action):
    mock_client = MagicMock()
    mock_order = MagicMock(id="alpaca_ord_1", status="accepted")
    mock_client.submit_order.return_value = mock_order

    executor = AlpacaExecutor(client=mock_client)
    result = executor.submit_order(sample_proposed_action)

    assert result.broker_order_id == "alpaca_ord_1"
    assert result.client_order_id == "act-alpaca-123"
    assert result.raw_status == "accepted"

    mock_client.submit_order.assert_called_once()
    req = mock_client.submit_order.call_args[1]["order_data"]
    assert isinstance(req, MarketOrderRequest)
    assert req.symbol == "AAPL"
    assert req.qty == 5.0
    assert req.side == OrderSide.BUY
    assert req.client_order_id == "act-alpaca-123"


def test_submit_order_success_limit(sample_proposed_action):
    action = sample_proposed_action.model_copy(
        update={"order_type": OrderType.LIMIT, "limit_price_usd": 150.0, "side": Side.SELL}
    )
    mock_client = MagicMock()
    mock_order = MagicMock(id="alpaca_ord_limit_2", status="new")
    mock_client.submit_order.return_value = mock_order

    executor = AlpacaExecutor(client=mock_client)
    result = executor.submit_order(action)

    assert result.broker_order_id == "alpaca_ord_limit_2"
    assert result.raw_status == "new"

    mock_client.submit_order.assert_called_once()
    req = mock_client.submit_order.call_args[1]["order_data"]
    assert isinstance(req, LimitOrderRequest)
    assert req.symbol == "AAPL"
    assert req.side == OrderSide.SELL
    assert req.limit_price == 150.0
    assert req.client_order_id == "act-alpaca-123"


def test_submit_order_limit_without_price_raises(sample_proposed_action):
    action = sample_proposed_action.model_copy(update={"order_type": OrderType.LIMIT, "limit_price_usd": None})
    executor = AlpacaExecutor(client=MagicMock())

    with pytest.raises(AlpacaExecutionError, match="limit_price_usd"):
        executor.submit_order(action)


def test_submit_order_wraps_api_error(sample_proposed_action):
    mock_client = MagicMock()
    original_err = APIError("insufficient funds")
    mock_client.submit_order.side_effect = original_err

    executor = AlpacaExecutor(client=mock_client)

    with pytest.raises(AlpacaExecutionError, match="Alpaca API rejected order") as exc_info:
        executor.submit_order(sample_proposed_action)

    assert exc_info.value.__cause__ is original_err


def test_submit_order_idempotency_via_client_order_id(sample_proposed_action):
    mock_client = MagicMock()
    mock_order = MagicMock(id="alpaca_ord_idempotent", status="accepted")
    mock_client.submit_order.return_value = mock_order

    executor = AlpacaExecutor(client=mock_client)
    res1 = executor.submit_order(sample_proposed_action)
    res2 = executor.submit_order(sample_proposed_action)

    assert res1.broker_order_id == res2.broker_order_id == "alpaca_ord_idempotent"
    assert mock_client.submit_order.call_count == 2

    req1 = mock_client.submit_order.call_args_list[0][1]["order_data"]
    req2 = mock_client.submit_order.call_args_list[1][1]["order_data"]
    assert req1.client_order_id == req2.client_order_id == "act-alpaca-123"


def test_load_credentials_missing_env_raises(monkeypatch, sample_proposed_action):
    monkeypatch.delenv("ALPACA_API_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_API_SECRET", raising=False)

    executor = AlpacaExecutor(client=None)
    with pytest.raises(AlpacaExecutionError, match="Alpaca credentials not configured"):
        executor.submit_order(sample_proposed_action)

    with pytest.raises(AlpacaExecutionError, match="Alpaca credentials not configured"):
        _load_alpaca_credentials()
