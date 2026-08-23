"""Pydantic contracts for normalized company fundamentals.

`FundamentalsSnapshot` is the provider-agnostic shape that every fundamentals
source (SEC EDGAR primary, a free fundamentals API for extras, or the offline
mock) normalizes into. It is the input the future `equity-research` valuation
primitives (DCF, comps) read — so downstream code never depends on a specific
data vendor's field names.

All monetary values are in the snapshot's `currency` (USD for US filers). Every
figure is optional because coverage varies by filer and period; consumers must
tolerate `None` rather than assume a field is present.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FundamentalsSource(str, Enum):
    """Where a FundamentalsSnapshot's data came from."""

    SEC_EDGAR = "sec_edgar"
    FUNDAMENTALS_API = "fundamentals_api"
    MOCK = "mock"


class FiscalPeriodType(str, Enum):
    """Granularity of a reported financial period."""

    ANNUAL = "annual"
    QUARTERLY = "quarterly"


class FinancialPeriod(BaseModel):
    """Key line items for a single reported fiscal period.

    Sourced from as-reported XBRL facts (e.g. SEC EDGAR `companyconcept`), so
    a field is `None` when the filer did not tag that concept for the period.
    `free_cash_flow` is derived (operating cash flow minus capital expenditure)
    when both inputs are present.
    """

    fiscal_year: int = Field(description="Fiscal year the period belongs to, e.g. 2024.")
    period_type: FiscalPeriodType = Field(description="Annual or quarterly period.")
    period_end: Optional[str] = Field(
        default=None, description="Period end date as an ISO-8601 date string (YYYY-MM-DD)."
    )

    revenue_usd: Optional[float] = Field(default=None, description="Total revenue / net sales.")
    net_income_usd: Optional[float] = Field(default=None, description="Net income attributable to the company.")
    operating_income_usd: Optional[float] = Field(default=None, description="Operating income (EBIT proxy).")
    operating_cash_flow_usd: Optional[float] = Field(
        default=None, description="Net cash provided by operating activities."
    )
    capital_expenditure_usd: Optional[float] = Field(
        default=None, description="Capital expenditure (payments for PP&E), reported as a positive magnitude."
    )
    free_cash_flow_usd: Optional[float] = Field(
        default=None, description="Derived: operating_cash_flow_usd - capital_expenditure_usd, when both are present."
    )
    total_debt_usd: Optional[float] = Field(default=None, description="Total short- plus long-term debt.")
    cash_and_equivalents_usd: Optional[float] = Field(
        default=None, description="Cash and cash equivalents (plus short-term investments when tagged)."
    )
    total_assets_usd: Optional[float] = Field(default=None, description="Total assets.")
    total_equity_usd: Optional[float] = Field(default=None, description="Total stockholders' equity.")
    shares_diluted: Optional[float] = Field(
        default=None, description="Weighted-average diluted shares outstanding for the period."
    )


class FundamentalsSnapshot(BaseModel):
    """Normalized, cacheable fundamentals for a single equity.

    Produced by a `FundamentalsProvider` and consumed by valuation primitives.
    `periods` is ordered most-recent-first. This object is safe to persist/cache
    (it contains only public financial data — no user data).
    """

    ticker: str = Field(description="Uppercase ticker symbol, e.g. 'AAPL'.")
    company_name: Optional[str] = Field(default=None, description="Registrant / company name.")
    cik: Optional[str] = Field(default=None, description="SEC Central Index Key (zero-padded to 10 digits) when known.")
    currency: str = Field(default="USD", description="Reporting currency for the monetary figures.")

    periods: list[FinancialPeriod] = Field(
        default_factory=list, description="Reported fiscal periods, most recent first."
    )

    latest_price_usd: Optional[float] = Field(
        default=None, description="Most recent (real-time or delayed) share price, when a price source is wired in."
    )
    shares_outstanding: Optional[float] = Field(
        default=None, description="Most recent common shares outstanding (for market-cap / per-share math)."
    )

    source: FundamentalsSource = Field(description="Origin of this snapshot's data.")
    as_of: datetime = Field(description="UTC timestamp when this snapshot was assembled.")

    def latest_annual(self) -> Optional[FinancialPeriod]:
        """Returns the most recent annual period, or None if there are no annual periods."""
        for period in self.periods:
            if period.period_type == FiscalPeriodType.ANNUAL:
                return period
        return None
