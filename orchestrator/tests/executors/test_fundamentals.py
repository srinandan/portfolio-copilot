"""Unit tests for FundamentalsProvider implementations."""

from orchestrator.contracts.fundamentals import FiscalPeriodType, FundamentalsSource
from orchestrator.executors.fundamentals import (
    EdgarFundamentalsProvider,
    FundamentalsProvider,
    MockFundamentalsProvider,
)


def test_mock_provider_is_deterministic_and_echoes_ticker():
    provider = MockFundamentalsProvider()
    snap = provider.get_fundamentals("aapl")

    assert snap.ticker == "AAPL"
    assert snap.source == FundamentalsSource.MOCK
    assert len(snap.periods) == 3
    latest = snap.latest_annual()
    assert latest is not None
    assert latest.fiscal_year == 2024
    assert latest.period_type == FiscalPeriodType.ANNUAL
    # Financial content is deterministic across calls (only the as_of timestamp differs).
    assert provider.get_fundamentals("AAPL").model_dump(exclude={"as_of"}) == snap.model_dump(exclude={"as_of"})


def test_mock_provider_custom_snapshot_override():
    base = MockFundamentalsProvider().get_fundamentals("AAPL")
    provider = MockFundamentalsProvider(custom=base)
    out = provider.get_fundamentals("msft")
    assert out.ticker == "MSFT"  # ticker overridden
    assert out.periods == base.periods


def test_edgar_provider_delegates_to_client():
    sentinel = MockFundamentalsProvider().get_fundamentals("NVDA")

    class FakeClient:
        def __init__(self):
            self.called_with = None

        def get_fundamentals(self, ticker, **kwargs):
            self.called_with = ticker
            return sentinel

    fake = FakeClient()
    provider = EdgarFundamentalsProvider(client=fake)
    out = provider.get_fundamentals("NVDA")

    assert out is sentinel
    assert fake.called_with == "NVDA"


def test_mock_provider_satisfies_runtime_protocol():
    assert isinstance(MockFundamentalsProvider(), FundamentalsProvider)
    assert isinstance(EdgarFundamentalsProvider(client=object()), FundamentalsProvider)
