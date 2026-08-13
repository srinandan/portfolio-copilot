"""Contract for Portfolio Analysis drift report."""

from typing import List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class DriftReportEntry(BaseModel):
    """Represents asset class allocation status and drift metrics against target bands."""

    asset_class: str = Field(description="Name of the asset class (e.g. Equity, Fixed Income, Cash).")
    current_percent: float = Field(description="Current percentage of total portfolio value.")
    target_percent: float = Field(description="Target percentage defined in the IPS.")
    min_percent: float = Field(description="Minimum acceptable percentage tolerance band.")
    max_percent: float = Field(description="Maximum acceptable percentage tolerance band.")
    in_band: bool = Field(description="Whether the current allocation falls within [min_percent, max_percent].")
    drift_amount_percent: float = Field(description="Absolute percentage distance outside the tolerance band (>= 0.0).")

    model_config = ConfigDict(populate_by_name=True)


class DriftReport(BaseModel):
    """Comprehensive drift analysis report across all target asset classes."""

    user_id: Optional[str] = Field(default=None, description="User identifier.")
    as_of: str = Field(default="", description="When this drift snapshot was computed.")
    bands: List[DriftReportEntry] = Field(
        default_factory=list,
        validation_alias=AliasChoices("bands", "entries"),
        serialization_alias="bands",
        description="Per-asset-class allocation and drift entries.",
    )
    unclassified_value_usd: float = Field(
        default=0.0, description="Total USD value of holdings not mapped to any IPS target band."
    )
    rebalance_recommended: bool = Field(
        default=False, description="True if rebalancing threshold is exceeded for an out-of-band class."
    )
    has_active_ips: bool = Field(default=True, description="Whether user has an active IPS.")

    model_config = ConfigDict(populate_by_name=True)

    @property
    def entries(self) -> List[DriftReportEntry]:
        return self.bands
