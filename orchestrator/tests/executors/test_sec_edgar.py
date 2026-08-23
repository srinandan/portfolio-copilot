"""Unit tests for the SEC EDGAR client and its normalization (offline)."""

import httpx
import pytest

from orchestrator.contracts.fundamentals import FiscalPeriodType, FundamentalsSource
from orchestrator.executors.sec_edgar import (
    SECEdgarClient,
    SECEdgarError,
    normalize_company_facts,
)


def _usd_rows(rows):
    return {"units": {"USD": rows}}


def _share_rows(rows):
    return {"units": {"shares": rows}}


# Canned companyfacts payload: two annual (FY/10-K) years plus noise rows that
# must be filtered out (a quarterly row and a non-annual form).
CANNED_FACTS = {
    "cik": 320193,
    "entityName": "Apple Inc.",
    "facts": {
        "us-gaap": {
            "Revenues": _usd_rows(
                [
                    {"fy": 2024, "fp": "FY", "form": "10-K", "end": "2024-09-28", "val": 391_035_000_000},
                    {"fy": 2023, "fp": "FY", "form": "10-K", "end": "2023-09-30", "val": 383_285_000_000},
                    {"fy": 2024, "fp": "Q3", "form": "10-Q", "end": "2024-06-29", "val": 85_000_000_000},
                    {"fy": 2022, "fp": "FY", "form": "8-K", "end": "2022-09-24", "val": 999},
                ]
            ),
            "NetIncomeLoss": _usd_rows(
                [
                    {"fy": 2024, "fp": "FY", "form": "10-K", "end": "2024-09-28", "val": 93_736_000_000},
                    {"fy": 2023, "fp": "FY", "form": "10-K", "end": "2023-09-30", "val": 96_995_000_000},
                ]
            ),
            "NetCashProvidedByUsedInOperatingActivities": _usd_rows(
                [
                    {"fy": 2024, "fp": "FY", "form": "10-K", "end": "2024-09-28", "val": 118_254_000_000},
                ]
            ),
            "PaymentsToAcquirePropertyPlantAndEquipment": _usd_rows(
                [
                    {"fy": 2024, "fp": "FY", "form": "10-K", "end": "2024-09-28", "val": 9_447_000_000},
                ]
            ),
            "LongTermDebtNoncurrent": _usd_rows(
                [{"fy": 2024, "fp": "FY", "form": "10-K", "end": "2024-09-28", "val": 85_000_000_000}]
            ),
            "LongTermDebtCurrent": _usd_rows(
                [{"fy": 2024, "fp": "FY", "form": "10-K", "end": "2024-09-28", "val": 10_000_000_000}]
            ),
            "WeightedAverageNumberOfDilutedSharesOutstanding": _share_rows(
                [{"fy": 2024, "fp": "FY", "form": "10-K", "end": "2024-09-28", "val": 15_408_095_000}]
            ),
        }
    },
}


def test_normalize_extracts_annual_periods_only():
    snap = normalize_company_facts(CANNED_FACTS, ticker="aapl", cik="0000320193")

    assert snap.ticker == "AAPL"
    assert snap.company_name == "Apple Inc."
    assert snap.source == FundamentalsSource.SEC_EDGAR
    # Only FY 2024 and 2023 survive (Q3 quarterly and 8-K rows are filtered out).
    assert [p.fiscal_year for p in snap.periods] == [2024, 2023]
    assert all(p.period_type == FiscalPeriodType.ANNUAL for p in snap.periods)


def test_normalize_derives_fcf_and_total_debt():
    snap = normalize_company_facts(CANNED_FACTS, ticker="AAPL")
    fy24 = snap.periods[0]

    assert fy24.revenue_usd == 391_035_000_000
    assert fy24.free_cash_flow_usd == pytest.approx(118_254_000_000 - 9_447_000_000)
    # total debt = long-term noncurrent + current portion
    assert fy24.total_debt_usd == pytest.approx(95_000_000_000)


def test_normalize_missing_metric_is_none_not_error():
    snap = normalize_company_facts(CANNED_FACTS, ticker="AAPL")
    fy23 = snap.periods[1]
    # 2023 has revenue/net income but no OCF/capex → FCF is None, not a crash.
    assert fy23.revenue_usd == 383_285_000_000
    assert fy23.free_cash_flow_usd is None
    assert fy23.total_debt_usd is None


def test_tag_fallback_picks_alternate_concept():
    facts = {
        "entityName": "Example Co",
        "facts": {
            "us-gaap": {
                # First candidate absent; a later candidate carries the value.
                "SalesRevenueNet": _usd_rows(
                    [{"fy": 2024, "fp": "FY", "form": "10-K", "end": "2024-12-31", "val": 500}]
                ),
            }
        },
    }
    snap = normalize_company_facts(facts, ticker="EXPL")
    assert snap.periods[0].revenue_usd == 500


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_client_end_to_end_with_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/files/company_tickers.json"):
            return httpx.Response(200, json={"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}})
        if "companyfacts/CIK0000320193.json" in request.url.path:
            return httpx.Response(200, json=CANNED_FACTS)
        return httpx.Response(404, json={})

    sec = SECEdgarClient(user_agent="test-agent contact@example.com", client=_mock_client(handler))
    snap = sec.get_fundamentals("AAPL")

    assert snap.ticker == "AAPL"
    assert snap.cik == "0000320193"
    assert snap.periods[0].fiscal_year == 2024


def test_resolve_cik_unknown_ticker_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}})

    sec = SECEdgarClient(user_agent="t", client=_mock_client(handler))
    with pytest.raises(SECEdgarError, match="No SEC CIK"):
        sec.resolve_cik("ZZZZ")


def test_http_error_wrapped_as_edgar_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={})

    sec = SECEdgarClient(user_agent="t", client=_mock_client(handler))
    with pytest.raises(SECEdgarError):
        sec.resolve_cik("AAPL")
