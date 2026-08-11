"""Generic Managed Agent dispatcher for registry-driven dynamic execution."""

import json
import os
import re
from typing import Any, Dict, Optional, Type

from google.adk import Context
from google.adk.tools import google_search
from google.auth import default as google_auth_default
from pydantic import BaseModel, ValidationError

from ..contracts.drift_report import DriftReport
from ..contracts.goals_onboarding import GoalsOnboardingResult
from ..contracts.proposed_action import ProposedAction
from ..contracts.research_brief import ResearchBrief
from ..contracts.reviewer_verdict import ReviewerVerdict
from ..contracts.spending_analysis import SpendingReport
from ..logger import get_logger
from ..registry_client import AgentRegistryClient
from .worker import build_worker_managed_agent

logger = get_logger(__name__)

# Canonical mapping of skill identifiers to typed output schemas
OUTPUT_SCHEMA_BY_SKILL: Dict[str, Type[BaseModel]] = {
    "private-goals-onboarding": GoalsOnboardingResult,
    "private-portfolio-analysis": DriftReport,
    "private-research": ResearchBrief,
    "private-action-drafting": ProposedAction,
    "private-spending-analysis": SpendingReport,
    "private-reviewer": ReviewerVerdict,
}


def get_skill_tools(skill_name: str) -> list:
    """Returns the authorized toolset for a given skill turn."""
    normalized = normalize_skill_name(skill_name)
    if normalized == "research":
        return [google_search]
    return []


def normalize_skill_name(skill_name: str) -> str:
    """Extracts short skill ID from full resource name without prefix."""
    base = skill_name.split("/")[-1] if "/" in skill_name else skill_name
    return base.replace("private-", "")


def normalize_private_skill_name(skill_name: str) -> str:
    """Extracts short skill ID with 'private-' prefix for schema lookup."""
    base = skill_name.split("/")[-1] if "/" in skill_name else skill_name
    return base if base.startswith("private-") else f"private-{base}"


async def resolve_skill_instructions(skill_name: str, client: Optional[AgentRegistryClient] = None) -> str:
    """Resolves SKILL.md content from Agent Registry."""
    project_id = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        try:
            _, project_id = google_auth_default()
        except Exception:
            pass
    if not project_id:
        project_id = "dummy-project"
    location = os.environ.get("AGENT_REGISTRY_LOCATION", "global")
    norm_name = normalize_skill_name(skill_name)

    if client:
        return await client.get_skill_content(norm_name)

    async with AgentRegistryClient(project_id=project_id, location=location) as reg_client:
        return await reg_client.get_skill_content(norm_name)


def _extract_json_from_text(text: str) -> Optional[dict]:
    """Helper to extract JSON dict from raw LLM text or markdown code blocks."""
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return None


async def dispatch_managed_skill(
    skill_name: str,
    node_input: Any,
    ctx: Context,
    registry_client: Optional[AgentRegistryClient] = None,
) -> BaseModel | Any:
    """Dispatches a skill turn to the worker Managed Agent.

    1. Resolves SKILL.md from the Agent Registry for runtime instructions.
    2. Constructs a ManagedAgent with the skill's description, tools, and output schema.
    3. Invokes the agent node via ADK Context.
    4. Validates and returns the typed Pydantic output.
    """
    short_name = skill_name.split("/")[-1] if "/" in skill_name else skill_name
    output_schema = OUTPUT_SCHEMA_BY_SKILL.get(normalize_private_skill_name(short_name))
    tools = get_skill_tools(short_name)

    try:
        instructions = await resolve_skill_instructions(short_name, client=registry_client)
    except Exception as e:
        logger.exception("Failed to resolve skill instructions for %s", short_name)
        raise RuntimeError(f"Skill instruction resolution failed for {short_name}: {e}") from e

    agent = build_worker_managed_agent(
        name=short_name,
        description=instructions,
        output_schema=output_schema,
        tools=tools,
    )

    logger.info(f"Dispatching skill '{short_name}' to worker Managed Agent (schema={output_schema.__name__ if output_schema else None})")
    raw_result = await ctx.run_node(agent, node_input=node_input)

    if output_schema:
        if isinstance(raw_result, output_schema):
            return raw_result
        if isinstance(raw_result, dict):
            try:
                return output_schema.model_validate(raw_result)
            except ValidationError:
                logger.exception(
                    "Could not validate result as %s (raw_result keys=%s)",
                    output_schema.__name__,
                    list(raw_result.keys()),
                )
        elif isinstance(raw_result, str):
            parsed = _extract_json_from_text(raw_result)
            if parsed:
                try:
                    return output_schema.model_validate(parsed)
                except ValidationError:
                    pass

        # Fallback for structured schemas using preloaded facts + model narrative
        if output_schema is SpendingReport:
            preloaded = node_input.get("preloaded", {}) if isinstance(node_input, dict) else {}
            narrative = ""
            if ctx.session and ctx.session.events:
                safe_author = agent.name
                for ev in reversed(ctx.session.events):
                    if ev.author == safe_author and ev.content and ev.content.parts:
                        for part in reversed(ev.content.parts):
                            text = getattr(part, "text", "")
                            if text:
                                narrative = text
                                break
                    if narrative:
                        break
            return SpendingReport(
                user_id=node_input.get("user_id", "default_user") if isinstance(node_input, dict) else "default_user",
                total_income_usd=float(preloaded.get("total_income_usd", 0.0)),
                total_outflow_usd=float(preloaded.get("total_outflow_usd", 0.0)),
                savings_rate=float(preloaded.get("savings_rate", 0.0)),
                reserve_months=float(preloaded.get("reserve_months", 0.0)),
                category_breakdown=[],
                anomalies=[],
                narrative_summary=narrative or "Spending analysis completed based on transaction facts.",
            )

    return raw_result
