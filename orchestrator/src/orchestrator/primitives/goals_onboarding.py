"""Deterministic formulas for risk tolerance and default allocation bands."""

from ..contracts.ips import RiskTolerance, TargetAllocation


def calculate_risk_tolerance(time_horizon_years: int, drawdown_reaction: str) -> RiskTolerance:
    """Deterministically calculates risk tolerance based on time horizon and drawdown reaction.

    Reaction must be one of: 'sell', 'hold', 'buy_more'
    """
    if drawdown_reaction == "sell":
        return RiskTolerance.CONSERVATIVE

    if time_horizon_years >= 15:
        return RiskTolerance.AGGRESSIVE
    elif time_horizon_years >= 7:
        return RiskTolerance.MODERATE
    else:
        return RiskTolerance.MODERATE


def get_default_allocation_bands(risk_tolerance: RiskTolerance) -> list[TargetAllocation]:
    """Proposes default bands per risk tier as a starting point."""
    if risk_tolerance == RiskTolerance.CONSERVATIVE:
        return [
            TargetAllocation(asset_class="equity", target_percent=30, min_percent=20, max_percent=40),
            TargetAllocation(asset_class="bonds", target_percent=60, min_percent=50, max_percent=70),
            TargetAllocation(asset_class="cash", target_percent=10, min_percent=5, max_percent=15),
        ]
    elif risk_tolerance == RiskTolerance.MODERATE:
        return [
            TargetAllocation(asset_class="equity", target_percent=60, min_percent=50, max_percent=70),
            TargetAllocation(asset_class="bonds", target_percent=30, min_percent=20, max_percent=40),
            TargetAllocation(asset_class="cash", target_percent=10, min_percent=5, max_percent=15),
        ]
    elif risk_tolerance == RiskTolerance.AGGRESSIVE:
        return [
            TargetAllocation(asset_class="equity", target_percent=85, min_percent=75, max_percent=95),
            TargetAllocation(asset_class="bonds", target_percent=10, min_percent=0, max_percent=20),
            TargetAllocation(asset_class="cash", target_percent=5, min_percent=0, max_percent=10),
        ]
    raise ValueError(f"Unknown risk tolerance: {risk_tolerance}")
