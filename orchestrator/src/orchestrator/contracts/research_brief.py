from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ResearchBrief(BaseModel):
    research_run_id: str
    summary: str
    sources: list[str]
    confidence: ConfidenceLevel
    as_of: datetime
