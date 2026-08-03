"""Re-export goals onboarding primitives for backwards compatibility."""

from ...primitives.goals_onboarding import (
    calculate_risk_tolerance,
    get_default_allocation_bands,
)

__all__ = [
    "calculate_risk_tolerance",
    "get_default_allocation_bands",
]
