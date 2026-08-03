"""Deterministic math and constraint primitives for Portfolio Copilot."""

from .spending_analysis import calculate_reserve_months, calculate_savings_rate, is_anomalous

__all__ = [
    "calculate_reserve_months",
    "calculate_savings_rate",
    "is_anomalous",
]
