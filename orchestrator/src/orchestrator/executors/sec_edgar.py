"""SEC EDGAR client — the primary, free, uncapped fundamentals source.

Reads as-reported XBRL financial facts from `data.sec.gov` (no API key, no cost)
and normalizes them into a provider-agnostic `FundamentalsSnapshot`. SEC's fair-
access policy asks for a descriptive `User-Agent` with contact info and a request
rate at or below ~10/s; set `SEC_EDGAR_USER_AGENT` to a real contact string in
deployment. Caching (see data/fundamentals_cache.py) keeps request volume low.

Only ANNUAL periods (10-K / 20-F, `fp == "FY"`) are extracted in this first cut,
which is what the DCF/comps primitives need; quarterly support can be layered on
later using the same helpers.
"""

import os
from datetime import datetime, timezone
from typing import Optional

import httpx

from ..contracts.fundamentals import (
    FinancialPeriod,
    FiscalPeriodType,
    FundamentalsSnapshot,
    FundamentalsSource,
)
from ..logger import get_logger

logger = get_logger(__name__)

SEC_DATA_BASE_URL = "https://data.sec.gov"
SEC_WWW_BASE_URL = "https://www.sec.gov"
COMPANY_TICKERS_PATH = "/files/company_tickers.json"

# Placeholder used when SEC_EDGAR_USER_AGENT is unset. SEC asks for a real
# contact; requests still succeed with this, but deployments should override it.
_DEFAULT_USER_AGENT = "portfolio-copilot (set SEC_EDGAR_USER_AGENT to a real contact)"

# Candidate us-gaap concept tags per metric, tried in order; the first tag that
# has a value for a given fiscal year wins. Filers tag the same economic concept
# under different names across eras, so multiple candidates are the norm.
_USD = "USD"
_SHARES = "shares"

_REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
]
_NET_INCOME_TAGS = ["NetIncomeLoss"]
_OPERATING_INCOME_TAGS = ["OperatingIncomeLoss"]
_OPERATING_CASH_FLOW_TAGS = [
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
]
_CAPEX_TAGS = [
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireProductiveAssets",
]
_LONG_TERM_DEBT_TAGS = ["LongTermDebtNoncurrent", "LongTermDebt"]
_SHORT_TERM_DEBT_TAGS = ["LongTermDebtCurrent", "DebtCurrent"]
_CASH_TAGS = ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsAndShortTermInvestments"]
_TOTAL_ASSETS_TAGS = ["Assets"]
_TOTAL_EQUITY_TAGS = ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]
_SHARES_DILUTED_TAGS = ["WeightedAverageNumberOfDilutedSharesOutstanding"]

# 10-K (and amendments) / 20-F are the annual forms.
_ANNUAL_FORMS = ("10-K", "20-F")


class SECEdgarError(RuntimeError):
    """Wraps every failure mode of an EDGAR call so callers need only one except."""


def _is_annual_form(form: str) -> bool:
    return any(form.startswith(prefix) for prefix in _ANNUAL_FORMS)


def _unit_facts(facts_json: dict, tag: str, unit: str) -> list[dict]:
    """Returns the list of fact rows for a us-gaap `tag` under `unit`, or []."""
    try:
        return facts_json["facts"]["us-gaap"][tag]["units"][unit]
    except (KeyError, TypeError):
        return []


def _merge_annual(facts_json: dict, unit: str, tags: list[str]) -> dict[int, tuple[float, Optional[str]]]:
    """Maps fiscal_year -> (value, period_end) for annual filings.

    Iterates candidate `tags` in order; a fiscal year already filled by an
    earlier tag is not overwritten. For duplicate rows within a year (e.g. an
    original 10-K and a later 10-K/A), the row with the latest `end` wins.
    """
    out: dict[int, tuple[float, Optional[str]]] = {}
    for tag in tags:
        for row in _unit_facts(facts_json, tag, unit):
            if row.get("fp") != "FY" or not _is_annual_form(str(row.get("form", ""))):
                continue
            fy = row.get("fy")
            val = row.get("val")
            if fy is None or val is None:
                continue
            end = row.get("end")
            existing = out.get(fy)
            if existing is None:
                out[fy] = (float(val), end)
            elif end is not None and (existing[1] is None or end > existing[1]):
                # A later-ending row for the same FY (restatement/amendment) wins.
                out[fy] = (float(val), end)
    return out


def _sum_optional(*values: Optional[float]) -> Optional[float]:
    """Sums the non-None values; returns None only if every input is None."""
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def normalize_company_facts(
    facts_json: dict,
    ticker: str,
    cik: Optional[str] = None,
    *,
    latest_price_usd: Optional[float] = None,
    shares_outstanding: Optional[float] = None,
) -> FundamentalsSnapshot:
    """Pure normalization of an EDGAR `companyfacts` payload → FundamentalsSnapshot.

    Kept free of I/O so it can be unit-tested directly against a canned payload.
    """
    revenue = _merge_annual(facts_json, _USD, _REVENUE_TAGS)
    net_income = _merge_annual(facts_json, _USD, _NET_INCOME_TAGS)
    op_income = _merge_annual(facts_json, _USD, _OPERATING_INCOME_TAGS)
    ocf = _merge_annual(facts_json, _USD, _OPERATING_CASH_FLOW_TAGS)
    capex = _merge_annual(facts_json, _USD, _CAPEX_TAGS)
    lt_debt = _merge_annual(facts_json, _USD, _LONG_TERM_DEBT_TAGS)
    st_debt = _merge_annual(facts_json, _USD, _SHORT_TERM_DEBT_TAGS)
    cash = _merge_annual(facts_json, _USD, _CASH_TAGS)
    assets = _merge_annual(facts_json, _USD, _TOTAL_ASSETS_TAGS)
    equity = _merge_annual(facts_json, _USD, _TOTAL_EQUITY_TAGS)
    shares_diluted = _merge_annual(facts_json, _SHARES, _SHARES_DILUTED_TAGS)

    fiscal_years = set()
    for series in (revenue, net_income, op_income, ocf, capex, lt_debt, st_debt, cash, assets, equity, shares_diluted):
        fiscal_years.update(series.keys())

    def val(series: dict[int, tuple[float, Optional[str]]], fy: int) -> Optional[float]:
        row = series.get(fy)
        return row[0] if row else None

    def end_for(fy: int) -> Optional[str]:
        # Prefer the revenue row's period_end, then any series that has one.
        for series in (revenue, net_income, ocf, assets):
            row = series.get(fy)
            if row and row[1]:
                return row[1]
        return None

    periods: list[FinancialPeriod] = []
    for fy in sorted(fiscal_years, reverse=True):
        ocf_v = val(ocf, fy)
        capex_v = val(capex, fy)
        fcf_v = (ocf_v - capex_v) if (ocf_v is not None and capex_v is not None) else None
        total_debt_v = _sum_optional(val(lt_debt, fy), val(st_debt, fy))
        periods.append(
            FinancialPeriod(
                fiscal_year=fy,
                period_type=FiscalPeriodType.ANNUAL,
                period_end=end_for(fy),
                revenue_usd=val(revenue, fy),
                net_income_usd=val(net_income, fy),
                operating_income_usd=val(op_income, fy),
                operating_cash_flow_usd=ocf_v,
                capital_expenditure_usd=capex_v,
                free_cash_flow_usd=fcf_v,
                total_debt_usd=total_debt_v,
                cash_and_equivalents_usd=val(cash, fy),
                total_assets_usd=val(assets, fy),
                total_equity_usd=val(equity, fy),
                shares_diluted=val(shares_diluted, fy),
            )
        )

    return FundamentalsSnapshot(
        ticker=ticker.upper(),
        company_name=facts_json.get("entityName"),
        cik=cik,
        currency=_USD,
        periods=periods,
        latest_price_usd=latest_price_usd,
        shares_outstanding=shares_outstanding,
        source=FundamentalsSource.SEC_EDGAR,
        as_of=datetime.now(timezone.utc),
    )


class SECEdgarClient:
    """Fetches and normalizes SEC EDGAR fundamentals over HTTPS."""

    def __init__(
        self,
        user_agent: Optional[str] = None,
        client: Optional[httpx.Client] = None,
        *,
        data_base_url: str = SEC_DATA_BASE_URL,
        www_base_url: str = SEC_WWW_BASE_URL,
        timeout: float = 20.0,
    ):
        self.user_agent = user_agent or os.environ.get("SEC_EDGAR_USER_AGENT") or _DEFAULT_USER_AGENT
        if self.user_agent == _DEFAULT_USER_AGENT:
            logger.warning("SEC_EDGAR_USER_AGENT is unset; using a placeholder User-Agent for SEC EDGAR requests.")
        self.data_base_url = data_base_url.rstrip("/")
        self.www_base_url = www_base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)
        self._ticker_map: Optional[dict[str, tuple[str, str]]] = None

    def _get(self, url: str) -> dict:
        """GETs `url` with the required headers and returns parsed JSON."""
        try:
            resp = self._client.get(url, headers={"User-Agent": self.user_agent, "Accept": "application/json"})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise SECEdgarError(f"SEC EDGAR returned {e.response.status_code} for {url}") from e
        except httpx.HTTPError as e:
            raise SECEdgarError(f"SEC EDGAR request failed for {url}: {e}") from e
        except ValueError as e:  # JSON decode
            raise SECEdgarError(f"SEC EDGAR returned non-JSON for {url}: {e}") from e

    def _load_ticker_map(self) -> dict[str, tuple[str, str]]:
        """Loads and caches the ticker -> (cik10, title) map from SEC's index."""
        if self._ticker_map is not None:
            return self._ticker_map
        raw = self._get(f"{self.www_base_url}{COMPANY_TICKERS_PATH}")
        mapping: dict[str, tuple[str, str]] = {}
        # The file is a JSON object keyed by arbitrary index -> {cik_str, ticker, title}.
        for entry in raw.values():
            try:
                ticker = str(entry["ticker"]).upper()
                cik10 = str(int(entry["cik_str"])).zfill(10)
                mapping[ticker] = (cik10, entry.get("title", ""))
            except (KeyError, TypeError, ValueError):
                continue
        self._ticker_map = mapping
        return mapping

    def resolve_cik(self, ticker: str) -> tuple[str, str]:
        """Resolves a ticker to (zero-padded CIK, company title). Raises if unknown."""
        mapping = self._load_ticker_map()
        hit = mapping.get(ticker.upper())
        if hit is None:
            raise SECEdgarError(f"No SEC CIK found for ticker {ticker!r}")
        return hit

    def get_company_facts(self, cik10: str) -> dict:
        """Fetches the raw `companyfacts` payload for a zero-padded CIK."""
        return self._get(f"{self.data_base_url}/api/xbrl/companyfacts/CIK{cik10}.json")

    def get_fundamentals(
        self,
        ticker: str,
        *,
        latest_price_usd: Optional[float] = None,
        shares_outstanding: Optional[float] = None,
    ) -> FundamentalsSnapshot:
        """End-to-end: ticker -> CIK -> companyfacts -> normalized FundamentalsSnapshot."""
        cik10, _title = self.resolve_cik(ticker)
        facts = self.get_company_facts(cik10)
        return normalize_company_facts(
            facts,
            ticker=ticker,
            cik=cik10,
            latest_price_usd=latest_price_usd,
            shares_outstanding=shares_outstanding,
        )

    def close(self) -> None:
        """Closes the underlying HTTP client."""
        self._client.close()
