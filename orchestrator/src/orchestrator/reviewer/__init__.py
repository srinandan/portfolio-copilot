"""Reviewer/Critic deterministic rule enforcement.

The Managed Agent produces an advisory verdict. This module re-runs the same
rules in trusted code — its output is the authoritative verdict the HITL and
execution gates enforce. See ADR-0014 (defense in depth), SKILL.md.
"""

from .rules import (
    RULES,
    ReviewInput,
    check_all_rules,
    compute_requires_human_approval,
)

__all__ = ["RULES", "ReviewInput", "check_all_rules", "compute_requires_human_approval"]
