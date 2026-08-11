import re
from datetime import timedelta
from typing import Any, List, Optional, Type

from google.adk.agents import ManagedAgent
from pydantic import BaseModel

from orchestrator.managed_agents.secret_loader import (
    DEFAULT_MANAGED_AGENT_ID,
    resolve_managed_agent_id,
)

DEFAULT_TURN_TIMEOUT = timedelta(minutes=3)
PER_SKILL_TIMEOUT: dict[str, timedelta] = {
    "research": timedelta(minutes=2),  # search-loop guardrail
    "action-drafting": timedelta(minutes=1),  # narrow schema
}

__all__ = [
    "DEFAULT_MANAGED_AGENT_ID",
    "DEFAULT_TURN_TIMEOUT",
    "PER_SKILL_TIMEOUT",
    "build_worker_managed_agent",
    "get_worker_agent_id",
    "sanitize_node_name",
]


def get_worker_agent_id() -> str:
    """Resolves the provisioned worker Managed Agent resource ID."""
    return resolve_managed_agent_id()


def sanitize_node_name(name: str) -> str:
    """Ensures node name is a valid Python identifier required by ADK."""
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if sanitized and sanitized[0].isdigit():
        sanitized = f"agent_{sanitized}"
    return sanitized or "managed_worker"


def build_worker_managed_agent(
    name: str,
    description: str,
    output_schema: Optional[Type[BaseModel]] = None,
    tools: Optional[List[Any]] = None,
    agent_id: Optional[str] = None,
) -> ManagedAgent:
    """Constructs a ManagedAgent instance configured for a specific skill turn.

    Args:
        name: Name of the node / skill.
        description: Full SKILL.md instructions resolved from the Agent Registry.
        output_schema: Expected Pydantic model for structured output validation.
        tools: Optional list of server-side built-in tools (e.g. google_search).
        agent_id: Optional explicit Managed Agent ID (defaults to MANAGED_AGENT_ID env).

    Returns:
        Configured ADK ManagedAgent node.
    """
    resolved_id = agent_id or get_worker_agent_id()
    safe_name = sanitize_node_name(name)
    short = name.replace("private-", "")
    timeout = PER_SKILL_TIMEOUT.get(short, DEFAULT_TURN_TIMEOUT)
    timeout_sec = timeout.total_seconds() if isinstance(timeout, timedelta) else float(timeout)

    return ManagedAgent(
        name=safe_name,
        description=description,
        agent_id=resolved_id,
        environment={"type": "remote"},
        tools=tools or [],
        output_schema=output_schema,
        rerun_on_resume=True,
        timeout=timeout_sec,
    )
