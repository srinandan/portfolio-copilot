from ...contracts.holdings import HoldingsSnapshot
from ...contracts.ips import InvestmentPolicyStatement
from ...contracts.proposed_action import OrderType, Side


def get_mock_alpaca_quote(ticker: str) -> float:
    """Mock Alpaca market data endpoint."""
    # Deterministic price for testing
    if ticker == "AAPL":
        return 150.0
    if ticker == "TSLA":
        return 200.0
    return 100.0


def get_mock_sector(ticker: str) -> str:
    """Mock sector lookup since it's not in the holdings schema."""
    if ticker in ["XOM", "CVX"]:
        return "Energy"
    if ticker in ["JPM", "GS"]:
        return "Financials"
    return "Technology"


def calculate_draft_action(
    drift_report: dict,
    holdings: HoldingsSnapshot,
    ips: InvestmentPolicyStatement,
) -> dict | None:
    """
    Calculates the drafted action based on the drift report or a directly requested trade.
    Returns a dict with proposed trade details, or None if no action is warranted.
    Raises ValueError if a trade would violate constraints.
    """
    if not drift_report.get("rebalance_recommended", False) and not drift_report.get("requested_trade"):
        return None

    total_value_usd = holdings.total_value_usd
    if total_value_usd is None:
        total_value_usd = sum(p.market_value_usd for p in holdings.positions) + (holdings.cash_usd or 0.0)

    if total_value_usd == 0:
        return None

    trade_details = None

    # Handle directly requested trade first
    if drift_report.get("requested_trade"):
        req = drift_report["requested_trade"]
        ticker = req["ticker"]
        side = req["side"]
        quantity = req.get("quantity")
        if not quantity:
            # If no quantity given, default to 1 for drafting
            quantity = 1.0

        current_price = get_mock_alpaca_quote(ticker)
        trade_details = {
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "order_type": OrderType.MARKET,
            "estimated_price_usd": current_price,
            "estimated_value_usd": quantity * current_price,
            "rationale": f"User requested to {side} {quantity} shares of {ticker}",
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
        current_price = get_mock_alpaca_quote(ticker)
        quantity_to_sell = trim_amount_usd / current_price

        # Don't sell more than we have
        if quantity_to_sell > largest_position.quantity:
            quantity_to_sell = largest_position.quantity
            trim_amount_usd = quantity_to_sell * current_price

        trade_details = {
            "ticker": ticker,
            "side": Side.SELL.value,
            "quantity": quantity_to_sell,
            "order_type": OrderType.MARKET.value,
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

    sector = get_mock_sector(ticker)
    if sector in ips.constraints.excluded_sectors:
        raise ValueError(f"Drafting failed: {ticker} is in excluded_sectors ({sector})")

    # Check concentration limit
    current_position = next((p for p in holdings.positions if p.ticker == ticker), None)
    current_value = current_position.market_value_usd if current_position else 0.0

    if trade_details["side"] == Side.BUY.value or trade_details["side"] == Side.BUY:
        new_value = current_value + trade_details["estimated_value_usd"]
        new_percent = (new_value / total_value_usd) * 100
        if new_percent > ips.constraints.concentration_limit_percent:
            raise ValueError(
                f"Drafting failed: Buying {ticker} would push position to {round(new_percent, 2)}%, "
                f"exceeding concentration limit of {ips.constraints.concentration_limit_percent}%"
            )

    return trade_details
