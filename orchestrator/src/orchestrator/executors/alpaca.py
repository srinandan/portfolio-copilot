"""Alpaca paper-trading executor.

Wraps the alpaca-py SDK. Owned by trusted orchestrator code per ADR-0005
(execution never delegated). Uses Alpaca's paper-trading endpoint exclusively —
never touches the live endpoint, regardless of environment.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

from ..contracts.proposed_action import OrderType, ProposedAction, Side
from ..logger import get_logger

logger = get_logger(__name__)


class AlpacaExecutionError(RuntimeError):
    """Wraps every failure mode from the Alpaca call site so callers only need one except."""


@dataclass
class ExecutionResult:
    """What the executor hands back to the gate after a successful submit."""
    broker_order_id: str
    submitted_at: datetime
    client_order_id: str  # = ProposedAction.action_id
    raw_status: str       # Alpaca's own status string ("new", "accepted", etc.)


def _load_alpaca_credentials() -> tuple[str, str]:
    """Reads ALPACA_API_KEY_ID and ALPACA_API_SECRET from env or Secret Manager.

    Populated at startup by secret_loader.py (see scripts/setup_secrets.sh).

    Raises:
        AlpacaExecutionError: if either credential is missing or empty.
    """
    from ..managed_agents.secret_loader import (
        SecretLoadError,
        resolve_alpaca_credentials,
    )

    try:
        return resolve_alpaca_credentials(require=True)
    except SecretLoadError as e:
        raise AlpacaExecutionError(
            "Alpaca credentials not configured: set ALPACA_API_KEY_ID and "
            "ALPACA_API_SECRET (populated from Secret Manager at deploy time)."
        ) from e


def _to_alpaca_side(side: Side) -> OrderSide:
    return OrderSide.BUY if side == Side.BUY else OrderSide.SELL


def _build_order_request(action: ProposedAction):
    """Translates a ProposedAction into an alpaca-py order request.

    Uses `client_order_id = action.action_id` for idempotency — resubmitting
    the same action_id returns the same broker order rather than creating a
    duplicate.
    """
    side = _to_alpaca_side(action.side)
    common = {
        "symbol": action.ticker,
        "qty": action.quantity,
        "side": side,
        "time_in_force": TimeInForce.DAY,
        "client_order_id": action.action_id,
    }
    if action.order_type == OrderType.LIMIT:
        if action.limit_price_usd is None:
            raise AlpacaExecutionError(
                f"ProposedAction {action.action_id} is a limit order but has no limit_price_usd"
            )
        return LimitOrderRequest(**common, limit_price=action.limit_price_usd)
    return MarketOrderRequest(**common)


class AlpacaExecutor:
    """Thin wrapper around alpaca-py's TradingClient. Paper-trading only."""

    def __init__(self, client: Optional[TradingClient] = None):
        """Args:
            client: Optional pre-built TradingClient (for tests). If None, one
                is constructed from ALPACA_API_KEY_ID / ALPACA_API_SECRET env vars
                on first use.
        """
        self._client = client
        self._client_built = client is not None

    def _get_client(self) -> TradingClient:
        if self._client is None:
            key_id, secret = _load_alpaca_credentials()
            self._client = TradingClient(api_key=key_id, secret_key=secret, paper=True)
            self._client_built = True
        return self._client

    def submit_order(self, action: ProposedAction) -> ExecutionResult:
        """Submits a ProposedAction to Alpaca's paper-trading endpoint.

        Raises:
            AlpacaExecutionError: on any Alpaca API error, credential misconfig,
                or malformed action. All exceptions from the SDK are wrapped
                so callers can `except AlpacaExecutionError:` once.
        """
        try:
            client = self._get_client()
            request = _build_order_request(action)
        except AlpacaExecutionError:
            raise
        except Exception as e:
            raise AlpacaExecutionError(f"Failed to build order request for {action.action_id}: {e}") from e

        try:
            logger.info(
                f"Submitting Alpaca order: {action.side.value} {action.quantity} {action.ticker} "
                f"(client_order_id={action.action_id})"
            )
            order = client.submit_order(order_data=request)
        except APIError as e:
            raise AlpacaExecutionError(f"Alpaca API rejected order {action.action_id}: {e}") from e
        except Exception as e:
            raise AlpacaExecutionError(f"Alpaca submit_order failed for {action.action_id}: {e}") from e

        broker_order_id = str(getattr(order, "id", "")) or str(order)
        raw_status = str(getattr(order, "status", "unknown"))
        logger.info(
            f"Alpaca accepted order {action.action_id} -> broker_order_id={broker_order_id} status={raw_status}"
        )
        return ExecutionResult(
            broker_order_id=broker_order_id,
            submitted_at=datetime.now(timezone.utc),
            client_order_id=action.action_id,
            raw_status=raw_status,
        )
