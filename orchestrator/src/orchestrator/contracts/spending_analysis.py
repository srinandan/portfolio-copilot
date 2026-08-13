from typing import List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class CategorySpending(BaseModel):
    """Spending summary for a specific category."""

    category: str = Field(description="Transaction category name.")
    amount_usd: float = Field(description="Total spend in USD for the window.")
    percent_of_total: float = Field(
        default=0.0,
        validation_alias=AliasChoices("percent_of_total", "percentage"),
        serialization_alias="percent_of_total",
        description="Percentage of total outflow.",
    )
    monthly_average_usd: Optional[float] = Field(
        default=None, description="Optional trailing monthly average spend in USD."
    )

    model_config = ConfigDict(populate_by_name=True)

    @property
    def percentage(self) -> float:
        return self.percent_of_total


class SpendingAnomaly(BaseModel):
    """Detected spending anomaly in a category."""

    category: str = Field(description="Category where anomalous spending was detected.")
    amount_usd: float = Field(
        default=0.0,
        validation_alias=AliasChoices("amount_usd", "current_spend_usd"),
        serialization_alias="amount_usd",
        description="Current period spend in USD.",
    )
    trailing_average_usd: float = Field(
        default=0.0,
        validation_alias=AliasChoices("trailing_average_usd", "trailing_avg_usd"),
        serialization_alias="trailing_average_usd",
        description="Trailing period average spend in USD.",
    )
    description: str = Field(description="Explanation of anomaly.")
    date: str = Field(default="", description="Date of the anomaly or reference period.")

    model_config = ConfigDict(populate_by_name=True)

    @property
    def current_spend_usd(self) -> float:
        return self.amount_usd

    @property
    def trailing_avg_usd(self) -> float:
        return self.trailing_average_usd


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

    model_config = ConfigDict(populate_by_name=True)


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
