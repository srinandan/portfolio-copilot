"""Equity price quotes via Alpaca's free market-data API.

Alpaca (already used for paper-trade execution) also serves free market data, so
it is the price source for valuation. `get_quote` returns the latest trade price
for a ticker, falling back to a deterministic mock when credentials are absent
(local dev / CI) or a live call fails — so the analysis pipeline is always
runnable offline.

Credentials are read from `ALPACA_API_KEY_ID` / `ALPACA_API_SECRET`, populated
into the environment at startup by `managed_agents/secret_loader.py` (same source
the trade executor uses). Only env is read here — no Secret Manager round-trip —
so the offline/mock path is fast and side-effect free.
"""

import os

from ..logger import get_logger

logger = get_logger(__name__)

# Deterministic offline prices, consistent with the legacy get_mock_alpaca_quote
# used by action-drafting, so mocked runs agree across the codebase.
_MOCK_PRICES = {"AAPL": 150.0, "TSLA": 200.0, "NVDA": 100.0}
_MOCK_DEFAULT_PRICE = 100.0


class MarketDataError(RuntimeError):
    """Raised when a live quote cannot be obtained and fallback is disabled."""


def get_mock_quote(ticker: str) -> float:
    """Deterministic offline price for a ticker."""
    return _MOCK_PRICES.get(ticker.upper(), _MOCK_DEFAULT_PRICE)


def _build_client():
    """Builds a live Alpaca market-data client, or raises if credentials are absent."""
    key = os.environ.get("ALPACA_API_KEY_ID")
    secret = os.environ.get("ALPACA_API_SECRET")
    if not key or not secret:
        raise MarketDataError("Alpaca credentials not set (ALPACA_API_KEY_ID / ALPACA_API_SECRET)")
    from alpaca.data.historical import StockHistoricalDataClient  # lazy import keeps offline paths light

    return StockHistoricalDataClient(key, secret)


def get_quote(ticker: str, *, client: object = None, allow_mock_fallback: bool = True) -> float:
    """Returns the latest trade price for `ticker`.

    Args:
        client: optional pre-built Alpaca data client (injected in tests); when
            None, one is built from environment credentials.
        allow_mock_fallback: when True (default), any failure or missing
            credentials yields a deterministic mock price instead of raising —
            keeping the pipeline runnable offline. Set False to require a live
            quote.

    Raises:
        MarketDataError: only when a live quote fails and fallback is disabled.
    """
    symbol = ticker.upper()
    try:
        c = client or _build_client()
        from alpaca.data.requests import StockLatestTradeRequest

        resp = c.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbol))
        price = float(resp[symbol].price)
        if price <= 0:
            raise MarketDataError(f"Alpaca returned a non-positive price ({price}) for {symbol}")
        return price
    except Exception as e:
        if allow_mock_fallback:
            logger.warning("Live quote for %s unavailable (%s); using mock price.", symbol, e)
            return get_mock_quote(symbol)
        raise MarketDataError(f"Failed to fetch live quote for {symbol}: {e}") from e
