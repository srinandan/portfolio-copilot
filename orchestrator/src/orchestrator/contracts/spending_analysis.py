"""Contract for the Spending Analysis Managed Agent output."""

from typing import List

from pydantic import BaseModel, Field


class CategorySpending(BaseModel):
    """Spending summary for a specific category."""

    category: str = Field(description="Transaction category name.")
    amount_usd: float = Field(description="Total spend in USD for the window.")
    percentage: float = Field(description="Percentage of total outflow.")


class SpendingAnomaly(BaseModel):
    """Detected spending anomaly in a category."""

    category: str = Field(description="Category where anomalous spending was detected.")
    current_spend_usd: float = Field(description="Current period spend in USD.")
    trailing_avg_usd: float = Field(description="Trailing period average spend in USD.")
    description: str = Field(description="Explanation of anomaly.")


class SpendingReport(BaseModel):
    """Comprehensive spending analysis report produced by the Managed Agent."""

    user_id: str = Field(description="User identifier.")
    total_income_usd: float = Field(description="Total income over window in USD.")
    total_outflow_usd: float = Field(description="Total outflow over window in USD.")
    savings_rate: float = Field(description="Calculated savings rate fraction.")
    reserve_months: float = Field(description="Months of emergency cash reserves.")
    category_breakdown: List[CategorySpending] = Field(
        default_factory=list, description="Spending breakdown by category."
    )
    anomalies: List[SpendingAnomaly] = Field(default_factory=list, description="Detected spending anomalies.")
    narrative_summary: str = Field(description="Natural language narrative analysis and recommendations.")


class SpendingNarrative(BaseModel):
    """LLM-authored slice of a SpendingReport.

    The orchestrator's preloader computes every numeric field
    (totals, savings rate, reserve months, per-category totals,
    detected anomalies). The Managed Agent only synthesizes the
    natural-language narrative that ties those facts to the user's
    question. The orchestrator merges the narrative back onto the
    preloaded facts to produce the persisted SpendingReport.
    """

    narrative_summary: str = Field(min_length=1, description="Natural language spending synthesis and insights.")
    anomaly_commentary: List[str] = Field(
        default_factory=list, description="Optional per-anomaly commentary aligning with preloaded anomalies."
    )
