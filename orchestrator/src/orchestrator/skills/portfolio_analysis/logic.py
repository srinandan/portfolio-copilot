from typing import List

from pydantic import BaseModel

from ...contracts.holdings import HoldingsSnapshot
from ...contracts.ips import InvestmentPolicyStatement


class DriftReportEntry(BaseModel):
    asset_class: str
    current_percent: float
    target_percent: float
    min_percent: float
    max_percent: float
    in_band: bool
    drift_amount_percent: float

class DriftReport(BaseModel):
    entries: List[DriftReportEntry]
    unclassified_value_usd: float
    rebalance_recommended: bool

def calculate_drift(holdings: HoldingsSnapshot, ips: InvestmentPolicyStatement) -> DriftReport:
    # Use holdings.total_value_usd if present, otherwise calculate it
    if holdings.total_value_usd is not None:
        total_value = holdings.total_value_usd
    else:
        total_value = sum(p.market_value_usd for p in holdings.positions) + (holdings.cash_usd or 0.0)

    # If total value is 0, we can't calculate percentages
    if total_value == 0:
        entries = []
        for alloc in ips.target_allocation:
            entries.append(DriftReportEntry(
                asset_class=alloc.asset_class,
                current_percent=0.0,
                target_percent=alloc.target_percent,
                min_percent=alloc.min_percent,
                max_percent=alloc.max_percent,
                in_band=(alloc.min_percent <= 0.0 <= alloc.max_percent),
                drift_amount_percent=0.0 if (alloc.min_percent <= 0.0 <= alloc.max_percent) else (
                    alloc.min_percent - 0.0 if 0.0 < alloc.min_percent else 0.0 - alloc.max_percent
                )
            ))
        return DriftReport(entries=entries, unclassified_value_usd=0.0, rebalance_recommended=False)

    # Accumulate market value by asset class
    value_by_class = {}
    for p in holdings.positions:
        value_by_class[p.asset_class] = value_by_class.get(p.asset_class, 0.0) + p.market_value_usd

    cash_mapped = False
    for alloc in ips.target_allocation:
        if alloc.asset_class.lower() == "cash" and (holdings.cash_usd or 0) > 0:
            value_by_class[alloc.asset_class] = value_by_class.get(alloc.asset_class, 0.0) + holdings.cash_usd
            cash_mapped = True
            break

    unclassified_value = 0.0
    if not cash_mapped and (holdings.cash_usd or 0) > 0:
        unclassified_value += holdings.cash_usd

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
                drift_amount = alloc.min_percent - current_percent
            else:
                drift_amount = current_percent - alloc.max_percent

        if drift_threshold is not None and drift_amount >= drift_threshold:
            rebalance_recommended = True

        entries.append(DriftReportEntry(
            asset_class=alloc.asset_class,
            current_percent=current_percent,
            target_percent=alloc.target_percent,
            min_percent=alloc.min_percent,
            max_percent=alloc.max_percent,
            in_band=in_band,
            drift_amount_percent=drift_amount
        ))

    for ac, val in value_by_class.items():
        if ac not in bands:
            # We already mapped cash if "cash" was in target_allocation.
            # If "cash" is not in target_allocation but we added it to value_by_class? We only added it if it was mapped.
            # So anything here not in bands is genuinely unclassified.
            unclassified_value += val

    return DriftReport(
        entries=entries,
        unclassified_value_usd=unclassified_value,
        rebalance_recommended=rebalance_recommended
    )
