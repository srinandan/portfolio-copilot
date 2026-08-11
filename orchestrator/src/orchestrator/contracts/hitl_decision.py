"""Typed contract for the Human-in-the-Loop approval gate output."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .proposed_action import ProposedAction


class HITLOutcome(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"  # future — for a session-timeout policy, unused today


class HITLDecision(BaseModel):
    """Result the HITL gate hands back to the orchestrator after the human resumes."""

    outcome: HITLOutcome = Field(description="Final human decision after any edit rounds.")
    action: ProposedAction = Field(description="Final ProposedAction after any edit-round modifications applied.")
    reason: Optional[str] = Field(
        default=None, description="Free-text reason (required on REJECTED, optional elsewhere)."
    )
    edit_rounds: int = Field(default=0, description="Number of edit rounds the user cycled through.")
    approved_at: datetime = Field(description="Timestamp the outcome was recorded.")
    approving_user_id: Optional[str] = Field(
        default=None, description="User id from the RequestInput response — required on APPROVED."
    )
