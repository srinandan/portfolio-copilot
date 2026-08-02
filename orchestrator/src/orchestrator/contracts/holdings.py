from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AccountType(str, Enum):
    TAXABLE = "taxable"
    RETIREMENT = "retirement"


class Position(BaseModel):
    ticker: str
    quantity: float = Field(ge=0)
    asset_class: str
    market_value_usd: float = Field(ge=0)
    account_type: AccountType | None = None


class HoldingsSnapshot(BaseModel):
    user_id: str
    as_of: datetime
    positions: list[Position]
    cash_usd: float | None = Field(default=None, ge=0)
    total_value_usd: float | None = Field(default=None, ge=0)
