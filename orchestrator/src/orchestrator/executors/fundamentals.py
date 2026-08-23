"""FundamentalsProvider — the seam between valuation code and data sources.

Downstream equity-research primitives depend only on this interface, never on a
specific vendor. Implementations:

- `EdgarFundamentalsProvider` — the real, free primary source (SEC EDGAR).
- `MockFundamentalsProvider` — deterministic offline data for local dev and CI,
  mirroring the `MockW2Parser` pattern so tests never touch the network.

A future free fundamentals-API provider (Finnhub/StockFit) for the "extras"
(analyst estimates, pre-computed ratios) can implement the same Protocol and be
layered behind the same cache without touching consumers.
"""

from datetime import datetime, timezone
from typing import Optional, Protocol, runtime_checkable

from ..contracts.fundamentals import (
    FinancialPeriod,
    FiscalPeriodType,
    FundamentalsSnapshot,
    FundamentalsSource,
)
from ..logger import get_logger
from .sec_edgar import SECEdgarClient

logger = get_logger(__name__)


@runtime_checkable
class FundamentalsProvider(Protocol):
    """Returns normalized fundamentals for a ticker."""

    def get_fundamentals(self, ticker: str) -> FundamentalsSnapshot:  # pragma: no cover - interface
        ...


class EdgarFundamentalsProvider:
    """FundamentalsProvider backed by SEC EDGAR (the free, uncapped primary source)."""

    def __init__(self, client: Optional[SECEdgarClient] = None):
        self._client = client or SECEdgarClient()

    def get_fundamentals(self, ticker: str) -> FundamentalsSnapshot:
        return self._client.get_fundamentals(ticker)


class MockFundamentalsProvider:
    """Deterministic offline provider for local dev and CI.

    Returns a fixed, plausible snapshot for any ticker (the ticker is echoed
    back), so pipelines are exercisable without a data source or network. Pass
    `custom` to force a specific snapshot.
    """

    def __init__(self, custom: Optional[FundamentalsSnapshot] = None):
        self._custom = custom

    def get_fundamentals(self, ticker: str) -> FundamentalsSnapshot:
        if self._custom is not None:
            return self._custom.model_copy(update={"ticker": ticker.upper()})
        return _mock_snapshot(ticker)


def _mock_snapshot(ticker: str) -> FundamentalsSnapshot:
    """A deterministic three-year annual snapshot with internally consistent figures."""
    periods = [
        FinancialPeriod(
            fiscal_year=2024,
            period_type=FiscalPeriodType.ANNUAL,
            period_end="2024-09-28",
            revenue_usd=391_035_000_000.0,
            net_income_usd=93_736_000_000.0,
            operating_income_usd=123_216_000_000.0,
            operating_cash_flow_usd=118_254_000_000.0,
            capital_expenditure_usd=9_447_000_000.0,
            free_cash_flow_usd=108_807_000_000.0,
            total_debt_usd=106_629_000_000.0,
            cash_and_equivalents_usd=29_943_000_000.0,
            total_assets_usd=364_980_000_000.0,
            total_equity_usd=56_950_000_000.0,
            shares_diluted=15_408_095_000.0,
        ),
        FinancialPeriod(
            fiscal_year=2023,
            period_type=FiscalPeriodType.ANNUAL,
            period_end="2023-09-30",
            revenue_usd=383_285_000_000.0,
            net_income_usd=96_995_000_000.0,
            operating_income_usd=114_301_000_000.0,
            operating_cash_flow_usd=110_543_000_000.0,
            capital_expenditure_usd=10_959_000_000.0,
            free_cash_flow_usd=99_584_000_000.0,
            total_debt_usd=111_088_000_000.0,
            cash_and_equivalents_usd=29_965_000_000.0,
            total_assets_usd=352_583_000_000.0,
            total_equity_usd=62_146_000_000.0,
            shares_diluted=15_812_547_000.0,
        ),
        FinancialPeriod(
            fiscal_year=2022,
            period_type=FiscalPeriodType.ANNUAL,
            period_end="2022-09-24",
            revenue_usd=394_328_000_000.0,
            net_income_usd=99_803_000_000.0,
            operating_income_usd=119_437_000_000.0,
            operating_cash_flow_usd=122_151_000_000.0,
            capital_expenditure_usd=10_708_000_000.0,
            free_cash_flow_usd=111_443_000_000.0,
            total_debt_usd=120_069_000_000.0,
            cash_and_equivalents_usd=23_646_000_000.0,
            total_assets_usd=352_755_000_000.0,
            total_equity_usd=50_672_000_000.0,
            shares_diluted=16_325_819_000.0,
        ),
    ]
    return FundamentalsSnapshot(
        ticker=ticker.upper(),
        company_name="Mock Corporation",
        cik="0000000000",
        currency="USD",
        periods=periods,
        latest_price_usd=225.0,
        shares_outstanding=15_115_823_000.0,
        source=FundamentalsSource.MOCK,
        as_of=datetime.now(timezone.utc),
    )
