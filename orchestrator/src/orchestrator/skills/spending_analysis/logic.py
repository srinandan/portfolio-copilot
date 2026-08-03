"""Re-export spending analysis primitives for backwards compatibility."""

from ...primitives.spending_analysis import (
    calculate_reserve_months,
    calculate_savings_rate,
    is_anomalous,
)

__all__ = [
    "calculate_reserve_months",
    "calculate_savings_rate",
    "is_anomalous",
]
