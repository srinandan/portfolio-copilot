"""Managed Agents integration layer for Google Cloud Gemini Enterprise."""

from .dispatcher import (
    OUTPUT_SCHEMA_BY_SKILL,
    dispatch_managed_skill,
    get_skill_tools,
    resolve_skill_instructions,
)
from .worker import build_worker_managed_agent, get_worker_agent_id

__all__ = [
    "build_worker_managed_agent",
    "get_worker_agent_id",
    "dispatch_managed_skill",
    "resolve_skill_instructions",
    "get_skill_tools",
    "OUTPUT_SCHEMA_BY_SKILL",
]
