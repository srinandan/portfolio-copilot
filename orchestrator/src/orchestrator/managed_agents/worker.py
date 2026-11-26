import os
import re
from datetime import timedelta
from typing import Any, List, Optional, Type

from google.adk.agents import ManagedAgent
from pydantic import BaseModel

from orchestrator.managed_agents.secret_loader import (
    DEFAULT_MANAGED_AGENT_ID,
    resolve_managed_agent_id,
)

DEFAULT_TIMEOUT_SEC = float(os.environ.get("MANAGED_AGENT_TIMEOUT_SECONDS", "480"))
DEFAULT_TURN_TIMEOUT = timedelta(seconds=DEFAULT_TIMEOUT_SEC)
PER_SKILL_TIMEOUT: dict[str, timedelta] = {
    "research": timedelta(seconds=float(os.environ.get("RESEARCH_TIMEOUT_SECONDS", "300"))),
    "action-drafting": timedelta(seconds=float(os.environ.get("ACTION_DRAFTING_TIMEOUT_SECONDS", "180"))),
    "spending-analysis": timedelta(seconds=float(os.environ.get("SPENDING_ANALYSIS_TIMEOUT_SECONDS", "60"))),
    "private-spending-analysis": timedelta(seconds=float(os.environ.get("SPENDING_ANALYSIS_TIMEOUT_SECONDS", "60"))),
}

__all__ = [
    "DEFAULT_MANAGED_AGENT_ID",
    "DEFAULT_TURN_TIMEOUT",
    "PER_SKILL_TIMEOUT",
    "build_worker_managed_agent",
    "get_worker_agent_id",
    "patch_adk_function_result_delta",
    "sanitize_node_name",
]


def patch_adk_function_result_delta() -> None:
    """Patches ADK's streaming FunctionResultDelta handler for google-genai >= 2.23.

    google-genai >= 2.23 removed ``call_id`` from ``FunctionResultDelta`` while
    google-adk (through 2.15.0) still reads ``delta.call_id`` unconditionally in
    ``google.adk.models.interactions_utils._handle_function_result``. Whenever a
    remote Managed Agent invokes an internal sandbox tool during streaming, that
    raises ``AttributeError`` and aborts the turn.

    Remove this workaround once upstream google-adk guards ``delta.call_id``.
    """
    from google.adk.models import interactions_utils
    from google.genai import types

    orig_handler = getattr(interactions_utils, "_handle_function_result", None)
    if orig_handler is None or getattr(orig_handler, "_is_safe_patched", False):
        return

    def safe_handle_function_result(
        delta: Any, state: Any, interaction_id: Optional[str], *args: Any, **kwargs: Any
    ) -> Any:
        try:
            return orig_handler(delta, state, interaction_id, *args, **kwargs)
        except AttributeError as exc:
            if "call_id" not in str(exc):
                raise
            part = types.Part(
                function_response=types.FunctionResponse(
                    id="",
                    name=delta.name,
                    response=interactions_utils._function_result_to_response(delta.result),
                )
            )
            state.parts.append(part)
            return interactions_utils._partial_part_response(part, interaction_id)

    safe_handle_function_result._is_safe_patched = True  # type: ignore[attr-defined]
    interactions_utils._handle_function_result = safe_handle_function_result


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
    patch_adk_function_result_delta()
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
