"""Pydantic model and enum contracts for ResearchBrief returned by research skill."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    """Confidence rating for market research findings based on source availability and consensus."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ResearchBrief(BaseModel):
    """Structured research brief summarizing external market context, sentiment, and sources."""
    research_run_id: str = Field(description="Unique, stable identifier for this research execution.")
    summary: str = Field(description="Objective synthesis of market context, performance drivers, and analyst consensus.")
    sources: list[str] = Field(default_factory=list, description="List of cited public URLs and reference sources.")
    confidence: ConfidenceLevel = Field(description="Confidence rating (high, medium, low) indicating source certainty.")
    as_of: datetime = Field(description="UTC timestamp when the research context was retrieved.")
