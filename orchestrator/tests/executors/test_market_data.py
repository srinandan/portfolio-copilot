"""Unit tests for the Alpaca market-data quote source (offline)."""

import pytest

from orchestrator.executors.market_data import (
    MarketDataError,
    get_mock_quote,
    get_quote,
)


class _FakeTrade:
    def __init__(self, price):
        self.price = price


class _FakeClient:
    """Stands in for alpaca-py's StockHistoricalDataClient."""

    def __init__(self, price=None, raises=False):
        self._price = price
        self._raises = raises

    def get_stock_latest_trade(self, request):
        if self._raises:
            raise RuntimeError("boom")
        # alpaca-py returns a symbol-keyed mapping of Trade objects.
        return {request.symbol_or_symbols: _FakeTrade(self._price)}


def test_get_mock_quote_known_and_unknown():
    assert get_mock_quote("aapl") == 150.0
    assert get_mock_quote("TSLA") == 200.0
    assert get_mock_quote("ZZZZ") == 100.0


def test_get_quote_uses_injected_client_price():
    price = get_quote("AAPL", client=_FakeClient(price=222.5))
    assert price == 222.5


def test_get_quote_falls_back_to_mock_on_client_error():
    price = get_quote("AAPL", client=_FakeClient(raises=True), allow_mock_fallback=True)
    assert price == 150.0  # mock AAPL


def test_get_quote_raises_when_fallback_disabled():
    with pytest.raises(MarketDataError):
        get_quote("AAPL", client=_FakeClient(raises=True), allow_mock_fallback=False)


def test_get_quote_no_credentials_falls_back(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_API_SECRET", raising=False)
    # No client passed → _build_client raises (no creds) → mock fallback.
    assert get_quote("NVDA") == 100.0


def test_get_quote_no_credentials_no_fallback_raises(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_API_SECRET", raising=False)
    with pytest.raises(MarketDataError):
        get_quote("NVDA", allow_mock_fallback=False)
