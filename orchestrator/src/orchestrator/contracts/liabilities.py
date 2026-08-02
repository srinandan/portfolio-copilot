from datetime import datetime
from enum import Enum

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
    description: str | None = None
    balance_usd: float = Field(ge=0)
    interest_rate_percent: float | None = Field(default=None, ge=0)
    minimum_payment_usd: float = Field(ge=0)


class LiabilitiesSnapshot(BaseModel):
    user_id: str
    as_of: datetime
    liabilities: list[Liability]
    total_liabilities_usd: float | None = Field(default=None, ge=0)
