"""Contract for Portfolio Analysis drift report."""

from typing import List

from pydantic import BaseModel, Field


class DriftReportEntry(BaseModel):
    """Represents asset class allocation status and drift metrics against target bands."""
    asset_class: str = Field(description="Name of the asset class (e.g. Equity, Fixed Income, Cash).")
    current_percent: float = Field(description="Current percentage of total portfolio value.")
    target_percent: float = Field(description="Target percentage defined in the IPS.")
    min_percent: float = Field(description="Minimum acceptable percentage tolerance band.")
    max_percent: float = Field(description="Maximum acceptable percentage tolerance band.")
    in_band: bool = Field(description="Whether the current allocation falls within [min_percent, max_percent].")
    drift_amount_percent: float = Field(description="Absolute percentage distance outside the tolerance band (>= 0.0).")


class DriftReport(BaseModel):
    """Comprehensive drift analysis report across all target asset classes."""
    entries: List[DriftReportEntry] = Field(description="Per-asset-class allocation and drift entries.")
    unclassified_value_usd: float = Field(description="Total USD value of holdings not mapped to any IPS target band.")
    rebalance_recommended: bool = Field(description="True if rebalancing threshold is exceeded for an out-of-band class.")
