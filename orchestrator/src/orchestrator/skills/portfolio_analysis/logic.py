"""Core calculations for portfolio drift analysis against Investment Policy Statement target allocation."""

from typing import List

from pydantic import BaseModel, Field

from ...contracts.holdings import HoldingsSnapshot
from ...contracts.ips import InvestmentPolicyStatement

CASH_ASSET_CLASS_SYNONYMS = {
    "cash",
    "cash reserves",
    "cash_reserves",
    "cash equivalents",
    "cash_equivalents",
}


class DriftReportEntry(BaseModel):
    """Represents asset class allocation status and drift metrics against target bands."""
    asset_class: str = Field(description="Name of the asset class (e.g. Equity, Fixed Income, Cash).")
    current_percent: float = Field(description="Current percentage of total portfolio value.")
    target_percent: float = Field(description="Target percentage defined in the IPS.")
    min_percent: float = Field(description="Minimum acceptable percentage tolerance band.")
    max_percent: float = Field(description="Maximum acceptable percentage tolerance band.")
    in_band: bool = Field(description="Whether the current allocation falls within [min_percent, max_percent].")
    drift_amount_percent: float = Field(description="Absolute percentage distance outside the tolerance band (>= 0.0).")


class DriftReport(BaseModel):
    """Comprehensive drift analysis report across all target asset classes."""
    entries: List[DriftReportEntry] = Field(description="Per-asset-class allocation and drift entries.")
    unclassified_value_usd: float = Field(description="Total USD value of holdings not mapped to any IPS target band.")
    rebalance_recommended: bool = Field(description="True if rebalancing threshold is exceeded for an out-of-band class.")


def calculate_drift(holdings: HoldingsSnapshot, ips: InvestmentPolicyStatement) -> DriftReport:
    """Calculates portfolio allocation drift against the active Investment Policy Statement.

    Args:
        holdings: Current portfolio positions and cash snapshot.
        ips: Active Investment Policy Statement with target allocation bands and rules.

    Returns:
        DriftReport detailing asset class allocations, drift percentages, and rebalance recommendation.
    """
    # Use holdings.total_value_usd if present, otherwise calculate it
    if holdings.total_value_usd is not None:
        total_value = holdings.total_value_usd
    else:
        total_value = sum(p.market_value_usd for p in holdings.positions) + (holdings.cash_usd or 0.0)

    # If total value is 0, we can't calculate percentages
    if total_value == 0:
        entries = []
        for alloc in ips.target_allocation:
            in_band = alloc.min_percent <= 0.0 <= alloc.max_percent
            drift_amount = 0.0
            if not in_band:
                if 0.0 < alloc.min_percent:
                    drift_amount = max(0.0, alloc.min_percent - 0.0)
                else:
                    drift_amount = max(0.0, 0.0 - alloc.max_percent)

            entries.append(DriftReportEntry(
                asset_class=alloc.asset_class,
                current_percent=0.0,
                target_percent=alloc.target_percent,
                min_percent=alloc.min_percent,
                max_percent=alloc.max_percent,
                in_band=in_band,
                drift_amount_percent=drift_amount,
            ))
        return DriftReport(entries=entries, unclassified_value_usd=0.0, rebalance_recommended=False)

    # Accumulate market value by asset class
    value_by_class: dict[str, float] = {}
    for p in holdings.positions:
        value_by_class[p.asset_class] = value_by_class.get(p.asset_class, 0.0) + p.market_value_usd

    # Map cash balance to target allocation bands recognizing standard cash synonyms
    cash_mapped = False
    cash_amount = holdings.cash_usd or 0.0

    if cash_amount > 0:
        for alloc in ips.target_allocation:
            if alloc.asset_class.strip().lower() in CASH_ASSET_CLASS_SYNONYMS:
                value_by_class[alloc.asset_class] = value_by_class.get(alloc.asset_class, 0.0) + cash_amount
                cash_mapped = True
                break

    unclassified_value = 0.0
    if not cash_mapped and cash_amount > 0:
        unclassified_value += cash_amount

    bands = {alloc.asset_class: alloc for alloc in ips.target_allocation}

    entries = []
    rebalance_recommended = False

    drift_threshold = None
    if ips.rebalancing_rules and ips.rebalancing_rules.drift_threshold_percent is not None:
        drift_threshold = ips.rebalancing_rules.drift_threshold_percent

    for alloc in ips.target_allocation:
        val = value_by_class.get(alloc.asset_class, 0.0)
        current_percent = (val / total_value) * 100.0

        in_band = alloc.min_percent <= current_percent <= alloc.max_percent
        drift_amount = 0.0
        if not in_band:
            if current_percent < alloc.min_percent:
                drift_amount = max(0.0, alloc.min_percent - current_percent)
            else:
                drift_amount = max(0.0, current_percent - alloc.max_percent)

        if drift_threshold is not None and drift_amount >= drift_threshold:
            rebalance_recommended = True

        entries.append(DriftReportEntry(
            asset_class=alloc.asset_class,
            current_percent=current_percent,
            target_percent=alloc.target_percent,
            min_percent=alloc.min_percent,
            max_percent=alloc.max_percent,
            in_band=in_band,
            drift_amount_percent=drift_amount,
        ))

    # Any positions in value_by_class not matching an IPS band are unclassified
    for ac, val in value_by_class.items():
        if ac not in bands:
            unclassified_value += val

    return DriftReport(
        entries=entries,
        unclassified_value_usd=unclassified_value,
        rebalance_recommended=rebalance_recommended,
    )
