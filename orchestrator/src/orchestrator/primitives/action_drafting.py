"""Core logic and constraint evaluation for drafting proposed actions."""

from typing import Callable, Union

from ..contracts.holdings import HoldingsSnapshot
from ..contracts.ips import InvestmentPolicyStatement
from ..contracts.proposed_action import OrderType, Side

KNOWN_SECTOR_MAP = {
    "XOM": "Energy",
    "CVX": "Energy",
    "JPM": "Financials",
    "GS": "Financials",
    "AAPL": "Technology",
    "MSFT": "Technology",
    "TSLA": "Consumer Cyclical",
    "NVDA": "Technology",
    "VOO": "Broad Market",
    "SPY": "Broad Market",
    "BND": "Fixed Income",
}


def get_mock_alpaca_quote(ticker: str) -> float:
    """Mock Alpaca market data endpoint returning deterministic prices for testing."""
    if ticker == "AAPL":
        return 150.0
    if ticker == "TSLA":
        return 200.0
    if ticker == "NVDA":
        return 100.0
    return 100.0


def get_mock_sector(ticker: str) -> str:
    """Mock sector lookup mapping known tickers to their sector, or Unknown."""
    return KNOWN_SECTOR_MAP.get(ticker.upper(), "Unknown")


def calculate_draft_action(
    drift_report: Union[dict, None],
    holdings: HoldingsSnapshot,
    ips: InvestmentPolicyStatement,
    quote_fn: Callable[[str], float] = get_mock_alpaca_quote,
    sector_fn: Callable[[str], str] = get_mock_sector,
) -> dict | None:
    """Calculates the drafted action based on the drift report or a directly requested trade.

    Returns a dict with proposed trade details, or None if no action is warranted.
    Raises ValueError if a trade would violate constraints or if insufficient shares exist.
    """
    report_dict = drift_report.model_dump() if hasattr(drift_report, "model_dump") else (drift_report or {})

    rebalance_recommended = report_dict.get("rebalance_recommended", False)
    requested_trade = report_dict.get("requested_trade")

    if not rebalance_recommended and not requested_trade:
        return None

    total_value_usd = holdings.total_value_usd
    if total_value_usd is None:
        total_value_usd = sum(p.market_value_usd for p in holdings.positions) + (holdings.cash_usd or 0.0)

    if total_value_usd <= 0:
        return None

    trade_details = None
    is_direct_request = bool(requested_trade)

    # Handle directly requested trade first
    if is_direct_request:
        ticker = requested_trade["ticker"]
        raw_side = requested_trade["side"]
        side = Side(raw_side.lower() if isinstance(raw_side, str) else raw_side)
        quantity = requested_trade.get("quantity")
        if not quantity:
            quantity = 1.0

        current_price = quote_fn(ticker)
        trade_details = {
            "ticker": ticker,
            "side": side,
            "quantity": float(quantity),
            "order_type": OrderType.MARKET,
            "estimated_price_usd": current_price,
            "estimated_value_usd": float(quantity) * current_price,
            "rationale": f"User requested to {side.value} {quantity} shares of {ticker}",
        }
    else:
        # Handle drift rebalancing
        asset_class_values = {}
        for p in holdings.positions:
            asset_class_values[p.asset_class] = asset_class_values.get(p.asset_class, 0.0) + p.market_value_usd

        over_allocated_ac = None
        trim_amount_usd = 0.0
        target_percent = 0.0

        for alloc in ips.target_allocation:
            ac = alloc.asset_class
            ac_val = asset_class_values.get(ac, 0.0)
            ac_percent = (ac_val / total_value_usd) * 100

            if ac_percent > alloc.max_percent:
                over_allocated_ac = ac
                target_percent = alloc.target_percent
                trim_amount_usd = ac_val - (target_percent / 100 * total_value_usd)
                break

        if over_allocated_ac is None or trim_amount_usd <= 0:
            return None

        # Select largest position in asset class
        ac_positions = [p for p in holdings.positions if p.asset_class == over_allocated_ac]
        if not ac_positions:
            return None

        largest_position = max(ac_positions, key=lambda p: p.market_value_usd)
        ticker = largest_position.ticker
        current_price = quote_fn(ticker)
        quantity_to_sell = trim_amount_usd / current_price

        # B1: If single position does not have enough shares, decline to draft rather than under-trimming silently
        if quantity_to_sell > largest_position.quantity:
            raise ValueError(
                f"no single position in {over_allocated_ac} has enough market value to complete the trim to "
                f"target_percent — trim needed: ${trim_amount_usd:.2f}, largest available ({largest_position.ticker}): "
                f"${largest_position.market_value_usd:.2f}"
            )

        trade_details = {
            "ticker": ticker,
            "side": Side.SELL,
            "quantity": quantity_to_sell,
            "order_type": OrderType.MARKET,
            "estimated_price_usd": current_price,
            "estimated_value_usd": trim_amount_usd,
            "rationale": f"Trimming {ticker} by {round(quantity_to_sell, 2)} shares to bring {over_allocated_ac} back to exactly {target_percent}%",
        }

    if not trade_details:
        return None

    # Apply constraint checks (Defense in Depth)
    ticker = trade_details["ticker"]

    if ticker in ips.constraints.excluded_tickers:
        raise ValueError(f"Drafting failed: {ticker} is in excluded_tickers")

    sector = sector_fn(ticker)
    if ips.constraints.excluded_sectors:
        if sector == "Unknown":
            raise ValueError(
                f"Drafting failed: Cannot classify sector for {ticker} with active excluded_sectors constraint"
            )
        if sector.lower() in [s.lower() for s in ips.constraints.excluded_sectors]:
            raise ValueError(f"Drafting failed: {ticker} is in excluded_sectors ({sector})")

    # B2: Check concentration limit
    current_position = next((p for p in holdings.positions if p.ticker == ticker), None)
    current_value = current_position.market_value_usd if current_position else 0.0

    side = trade_details["side"]
    if side == Side.BUY:
        new_value = current_value + trade_details["estimated_value_usd"]
        new_percent = (new_value / total_value_usd) * 100.0
        if new_percent > ips.constraints.concentration_limit_percent:
            raise ValueError(
                f"Drafting failed: Buying {ticker} would push position to {round(new_percent, 2)}%, "
                f"exceeding concentration limit of {ips.constraints.concentration_limit_percent}%"
            )
    elif is_direct_request and side == Side.SELL:
        # A user-requested sell that still leaves position above the concentration limit
        new_value = max(0.0, current_value - trade_details["estimated_value_usd"])
        new_percent = (new_value / total_value_usd) * 100.0
        if new_percent > ips.constraints.concentration_limit_percent:
            raise ValueError(
                f"Drafting failed: Trade in {ticker} results in position concentration of {round(new_percent, 2)}%, "
                f"exceeding concentration limit of {ips.constraints.concentration_limit_percent}%"
            )

    return trade_details
