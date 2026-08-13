"""Contract for User Profile demographic and personal details."""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FamilyMember(BaseModel):
    """Represents a family member or dependent."""

    name: str = Field(description="Name of family member.")
    relationship: str = Field(description="Relationship to user (e.g. spouse, child, parent).")
    age: int = Field(default=0, ge=0, le=150, description="Age in years.")

    model_config = ConfigDict(populate_by_name=True)


class UserProfile(BaseModel):
    """User personal, demographic, and financial background details."""

    user_id: str = Field(description="Unique identifier for the user (default: demo_user).")
    full_name: Optional[str] = Field(default=None, description="User's full name.")
    email: Optional[str] = Field(default=None, description="User's email address.")
    date_of_birth: Optional[str] = Field(default=None, description="Date of birth in YYYY-MM-DD format.")
    age: Optional[int] = Field(default=None, ge=0, le=150, description="Current age in years.")
    marital_status: Optional[str] = Field(default=None, description="Marital status.")
    dependents_count: Optional[int] = Field(default=0, ge=0, description="Number of financial dependents.")
    family_members: List[FamilyMember] = Field(default_factory=list, description="List of family members and dependents.")
    employment_status: Optional[str] = Field(default=None, description="Current employment status.")
    occupation: Optional[str] = Field(default=None, description="Job title or profession.")
    annual_income_usd: Optional[float] = Field(default=None, ge=0.0, description="Gross annual income in USD.")
    target_retirement_age: Optional[int] = Field(default=None, ge=0, le=120, description="Target retirement age.")
    monthly_housing_payment_usd: Optional[float] = Field(default=None, ge=0.0, description="Monthly rent or mortgage payment in USD.")
    risk_tolerance_notes: Optional[str] = Field(default=None, description="User notes regarding risk tolerance and volatility comfort.")
    financial_goals_notes: Optional[str] = Field(default=None, description="User notes regarding financial objectives and milestones.")
    updated_at: Optional[str] = Field(default=None, description="ISO 8601 timestamp of last profile update.")

    model_config = ConfigDict(populate_by_name=True)
