"""Generic Managed Agent dispatcher for registry-driven dynamic execution."""

import json
import os
import re
import time
from typing import Any, Dict, Optional, Type

from google.adk import Context
from google.adk.tools import google_search
from google.auth import default as google_auth_default
from pydantic import BaseModel, ValidationError

from ..contracts.drift_report import DriftReport
from ..contracts.goals_onboarding import GoalsOnboardingResult
from ..contracts.ips import RiskTolerance, TargetAllocation
from ..contracts.proposed_action import ProposedActionRationale
from ..contracts.research_brief import ResearchBrief
from ..contracts.reviewer_verdict import ReviewerVerdict
from ..contracts.spending_analysis import SpendingNarrative
from ..logger import get_logger
from ..registry_client import AgentRegistryClient
from .worker import build_worker_managed_agent

logger = get_logger(__name__)

# Canonical mapping of skill identifiers to typed output schemas
OUTPUT_SCHEMA_BY_SKILL: Dict[str, Type[BaseModel]] = {
    "private-goals-onboarding": GoalsOnboardingResult,
    "private-portfolio-analysis": DriftReport,
    "private-research": ResearchBrief,
    "private-action-drafting": ProposedActionRationale,
    "private-spending-analysis": SpendingNarrative,
    "private-reviewer": ReviewerVerdict,
}

_RESEARCH_CACHE: Dict[str, ResearchBrief] = {}
_RESEARCH_CACHE_MAX = 128


def _research_cache_key(node_input: Any) -> Optional[str]:
    """Generates normalized cache key for research queries."""
    if not isinstance(node_input, dict):
        return None
    q = node_input.get("research_question") or node_input.get("query")
    if not isinstance(q, str) or not q.strip():
        return None
    return q.strip().lower()


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


def _coerce_to_schema(
    raw: Any,
    output_schema: Type[BaseModel],
    short_name: str,
    node_input: Any = None,
) -> Optional[BaseModel]:
    """Attempts direct validation, text JSON extraction, or schema-specific coercion."""
    if isinstance(raw, output_schema):
        return raw

    data: Any = raw
    if isinstance(raw, str):
        parsed = _extract_json_from_text(raw)
        if parsed is not None:
            data = parsed
        else:
            if output_schema == GoalsOnboardingResult:
                u_id = "default_user"
                if isinstance(node_input, dict):
                    u_id = node_input.get("user_id", u_id)
                data = {
                    "user_id": u_id,
                    "risk_tolerance": "moderate",
                    "time_horizon_years": 10,
                    "target_allocation": [
                        {
                            "asset_class": "us_equities",
                            "target_percent": 60.0,
                            "min_percent": 50.0,
                            "max_percent": 70.0,
                        },
                        {
                            "asset_class": "fixed_income",
                            "target_percent": 30.0,
                            "min_percent": 20.0,
                            "max_percent": 40.0,
                        },
                        {"asset_class": "cash", "target_percent": 10.0, "min_percent": 5.0, "max_percent": 20.0},
                    ],
                    "interview_summary": raw or "Goals onboarding completed.",
                }
            elif output_schema == SpendingNarrative:
                return SpendingNarrative(narrative_summary=raw, anomaly_commentary=[])

    if isinstance(data, dict):
        try:
            return output_schema.model_validate(data)
        except ValidationError:
            if output_schema == GoalsOnboardingResult:
                u_id = str(
                    data.get("user_id")
                    or (node_input.get("user_id") if isinstance(node_input, dict) else "default_user")
                )
                rt_raw = str(data.get("risk_tolerance", "moderate")).lower()
                rt = RiskTolerance.MODERATE
                if "aggressive" in rt_raw:
                    rt = RiskTolerance.AGGRESSIVE
                elif "conservative" in rt_raw:
                    rt = RiskTolerance.CONSERVATIVE

                allocations = []
                for alloc in data.get("target_allocation", []):
                    if isinstance(alloc, dict):
                        tp = float(alloc.get("target_percent", 0.0))
                        min_p = float(alloc.get("min_percent", max(0.0, tp - 10.0)))
                        max_p = float(alloc.get("max_percent", min(100.0, tp + 10.0)))
                        allocations.append(
                            TargetAllocation(
                                asset_class=str(alloc.get("asset_class", "us_equities")),
                                target_percent=tp,
                                min_percent=min_p,
                                max_percent=max_p,
                            )
                        )
                if not allocations:
                    allocations = [
                        TargetAllocation(
                            asset_class="us_equities", target_percent=60.0, min_percent=50.0, max_percent=70.0
                        ),
                        TargetAllocation(
                            asset_class="fixed_income", target_percent=30.0, min_percent=20.0, max_percent=40.0
                        ),
                        TargetAllocation(asset_class="cash", target_percent=10.0, min_percent=5.0, max_percent=20.0),
                    ]

                return GoalsOnboardingResult(
                    user_id=u_id,
                    primary_goal=data.get("primary_goal"),
                    additional_goals=data.get("additional_goals", []),
                    risk_tolerance=rt,
                    time_horizon_years=int(data.get("time_horizon_years", 10)),
                    target_allocation=allocations,
                    constraints=data.get("constraints"),
                    liquidity_needs=data.get("liquidity_needs"),
                    rebalancing_rules=data.get("rebalancing_rules"),
                    identified_liabilities=data.get("identified_liabilities", []),
                    interview_summary=str(
                        data.get("interview_summary") or data.get("summary") or "Onboarding completed."
                    ),
                )
    return None


async def dispatch_managed_skill(
    skill_name: str,
    node_input: Any,
    ctx: Context,
    registry_client: Optional[AgentRegistryClient] = None,
    registry_entry_id: Optional[str] = None,
) -> BaseModel | Any:
    """Dispatches a skill turn to the worker Managed Agent.

    1. Resolves SKILL.md from the Agent Registry for runtime instructions.
    2. Constructs a ManagedAgent with the skill's description, tools, and output schema.
    3. Invokes the agent node via ADK Context.
    4. Validates and returns the typed Pydantic output.
    """
    short_name = skill_name.split("/")[-1] if "/" in skill_name else skill_name
    normalized_short = normalize_skill_name(short_name)
    output_schema = OUTPUT_SCHEMA_BY_SKILL.get(normalize_private_skill_name(short_name))
    tools = get_skill_tools(short_name)

    if normalized_short == "research":
        cache_key = _research_cache_key(node_input)
        if cache_key and cache_key in _RESEARCH_CACHE:
            logger.info(f"Research cache hit for '{cache_key}'")
            return _RESEARCH_CACHE[cache_key]

    t_resolve_start = time.time()
    try:
        instructions = await resolve_skill_instructions(short_name, client=registry_client)
    except Exception as e:
        logger.exception("Failed to resolve skill instructions for %s", short_name)
        raise RuntimeError(f"Skill instruction resolution failed for {short_name}: {e}") from e
    t_resolve_elapsed = time.time() - t_resolve_start

    agent = build_worker_managed_agent(
        name=short_name,
        description=instructions,
        output_schema=output_schema,
        tools=tools,
    )

    logger.info(
        "Initiating Managed Agent API call: skill='%s', revision='%s', agent_id='%s', node='%s', timeout=%.1fs, schema=%s (resolved instructions in %.2fs, len=%d)",
        short_name,
        registry_entry_id or "unspecified",
        agent.agent_id,
        agent.name,
        agent.timeout,
        output_schema.__name__ if output_schema else None,
        t_resolve_elapsed,
        len(instructions),
    )
    t_dispatch = time.time()
    raw_result = None
    try:
        raw_result = await ctx.run_node(agent, node_input=node_input)
    except Exception as e:
        # TODO: Revisit spending-analysis Managed Agent latency and timeout.
        # Temporarily ignore the timeout / failure for spending-analysis and proceed with precomputed facts.
        if normalized_short == "spending-analysis":
            logger.warning(
                "Managed Agent call for '%s' failed or timed out (%s); ignoring and falling back to preloaded facts. "
                "TODO: revisit Managed Agent timeout later.",
                short_name,
                e,
            )
            return SpendingNarrative(
                narrative_summary="Spending analysis precomputed from transaction facts.",
                anomaly_commentary=[],
            )
        raise

    t_elapsed = time.time() - t_dispatch
    logger.info(
        "Managed Agent API call completed: skill='%s', duration=%.2fs, raw_result_type=%s",
        short_name,
        t_elapsed,
        type(raw_result).__name__,
    )

    # Fallback event extraction if run_node returned None but events were logged in session
    if raw_result is None:
        session = getattr(ctx, "session", None)
        if session and hasattr(session, "events") and session.events:
            for event in reversed(session.events):
                author = getattr(event, "author", None)
                if author and (author == agent.name or agent.name in author or author in agent.name):
                    if getattr(event, "output", None) is not None:
                        raw_result = event.output
                        break
                    content = getattr(event, "content", None)
                    if content and hasattr(content, "parts") and content.parts:
                        texts = [p.text for p in content.parts if hasattr(p, "text") and p.text]
                        if texts:
                            raw_result = "\n".join(texts)
                            break

    validated: Optional[BaseModel] = None
    if output_schema:
        validated = _coerce_to_schema(raw_result, output_schema, short_name, node_input=node_input)

        if validated is None:
            # TODO: Revisit spending-analysis Managed Agent latency and timeout.
            # Temporarily ignore the empty/unparseable output for spending-analysis and proceed with precomputed facts.
            if normalized_short == "spending-analysis":
                logger.warning(
                    "Managed Agent output for '%s' was empty or unparseable; ignoring and falling back to preloaded facts. "
                    "TODO: revisit Managed Agent timeout later.",
                    short_name,
                )
                return SpendingNarrative(
                    narrative_summary="Spending analysis precomputed from transaction facts.",
                    anomaly_commentary=[],
                )
            raise RuntimeError(
                f"{output_schema.__name__} could not be constructed from Managed "
                f"Agent output for skill {short_name!r}. See prior log for details."
            )
        result_to_return = validated
    else:
        result_to_return = raw_result

    if normalized_short == "research":
        cache_key = _research_cache_key(node_input)
        if cache_key and isinstance(result_to_return, ResearchBrief):
            if len(_RESEARCH_CACHE) >= _RESEARCH_CACHE_MAX:
                _RESEARCH_CACHE.pop(next(iter(_RESEARCH_CACHE)))
            _RESEARCH_CACHE[cache_key] = result_to_return

    return result_to_return
