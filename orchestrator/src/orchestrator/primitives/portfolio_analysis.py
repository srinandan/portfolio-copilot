"""Core calculations for portfolio drift analysis against Investment Policy Statement target allocation."""

from ..contracts.drift_report import DriftReport, DriftReportEntry
from ..contracts.holdings import HoldingsSnapshot
from ..contracts.ips import InvestmentPolicyStatement
from ..logger import get_logger

logger = get_logger(__name__)

CASH_ASSET_CLASS_SYNONYMS = {
    "cash",
    "cash reserves",
    "cash_reserves",
    "cash equivalents",
    "cash_equivalents",
}


def calculate_drift(holdings: HoldingsSnapshot, ips: InvestmentPolicyStatement) -> DriftReport:
    """Calculates portfolio allocation drift against the active Investment Policy Statement.

    Args:
        holdings: Current portfolio positions and cash snapshot.
        ips: Active Investment Policy Statement with target allocation bands and rules.

    Returns:
        DriftReport detailing asset class allocations, drift percentages, and rebalance recommendation.
    """
    cash_amount = holdings.cash_usd or 0.0
    cash_in_positions = sum(
        p.market_value_usd for p in holdings.positions if p.asset_class.strip().lower() in CASH_ASSET_CLASS_SYNONYMS
    )
    # Reconcile cash to prevent double-counting when cash is represented both in positions and cash_usd (I5)
    net_cash_usd = max(0.0, cash_amount - cash_in_positions) if cash_in_positions > 0 else cash_amount

    computed_total = sum(p.market_value_usd for p in holdings.positions) + net_cash_usd

    # Use holdings.total_value_usd if present, but reconcile if it significantly deviates from computed sum (PA1)
    if holdings.total_value_usd is not None:
        if abs(holdings.total_value_usd - computed_total) > 0.001 * max(holdings.total_value_usd, computed_total, 1.0):
            logger.warning(
                f"Holdings total_value_usd ({holdings.total_value_usd}) disagrees with computed positions + cash sum "
                f"({computed_total}). Using computed total value."
            )
            total_value = computed_total
        else:
            total_value = holdings.total_value_usd
    else:
        total_value = computed_total

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

    # Map net cash balance to target allocation bands recognizing standard cash synonyms
    cash_mapped = False
    if net_cash_usd > 0:
        for alloc in ips.target_allocation:
            if alloc.asset_class.strip().lower() in CASH_ASSET_CLASS_SYNONYMS:
                value_by_class[alloc.asset_class] = value_by_class.get(alloc.asset_class, 0.0) + net_cash_usd
                cash_mapped = True
                break

    unclassified_value = 0.0
    if not cash_mapped and net_cash_usd > 0:
        unclassified_value += net_cash_usd

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
