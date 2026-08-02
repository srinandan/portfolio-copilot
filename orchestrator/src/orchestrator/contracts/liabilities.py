from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class LiabilityType(str, Enum):
    CREDIT_CARD = "credit_card"
    MORTGAGE = "mortgage"
    AUTO_LOAN = "auto_loan"
    STUDENT_LOAN = "student_loan"
    HELOC = "heloc"
    OTHER = "other"


class Liability(BaseModel):
    liability_id: str
    type: LiabilityType
    description: Optional[str] = None
    balance_usd: float = Field(ge=0)
    interest_rate_percent: Optional[float] = Field(default=None, ge=0)
    minimum_payment_usd: float = Field(ge=0)


class LiabilitiesSnapshot(BaseModel):
    user_id: str
    as_of: datetime
    liabilities: List[Liability]
    total_liabilities_usd: Optional[float] = Field(default=None, ge=0)
