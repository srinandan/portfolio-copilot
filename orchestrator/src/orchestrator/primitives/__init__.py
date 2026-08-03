"""Deterministic math and financial calculations for Portfolio Copilot."""

from .action_drafting import (
    KNOWN_SECTOR_MAP,
    calculate_draft_action,
    get_mock_alpaca_quote,
    get_mock_sector,
)
from .goals_onboarding import calculate_risk_tolerance, get_default_allocation_bands
from .portfolio_analysis import (
    CASH_ASSET_CLASS_SYNONYMS,
    DriftReport,
    DriftReportEntry,
    calculate_drift,
)
from .spending_analysis import (
    calculate_reserve_months,
    calculate_savings_rate,
    is_anomalous,
)

__all__ = [
    "calculate_drift",
    "DriftReport",
    "DriftReportEntry",
    "CASH_ASSET_CLASS_SYNONYMS",
    "calculate_draft_action",
    "get_mock_alpaca_quote",
    "get_mock_sector",
    "KNOWN_SECTOR_MAP",
    "is_anomalous",
    "calculate_savings_rate",
    "calculate_reserve_months",
    "calculate_risk_tolerance",
    "get_default_allocation_bands",
]
