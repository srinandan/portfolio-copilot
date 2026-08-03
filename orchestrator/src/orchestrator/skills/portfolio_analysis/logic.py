"""Re-export portfolio analysis primitives for backwards compatibility."""

from ...primitives.portfolio_analysis import (
    CASH_ASSET_CLASS_SYNONYMS,
    DriftReport,
    DriftReportEntry,
    calculate_drift,
)

__all__ = [
    "CASH_ASSET_CLASS_SYNONYMS",
    "DriftReport",
    "DriftReportEntry",
    "calculate_drift",
]
