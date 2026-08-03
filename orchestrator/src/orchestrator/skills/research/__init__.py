import os
import uuid
from datetime import datetime, timezone
from typing import Any

from google.adk import Context
from google.adk.agents import ManagedAgent
from google.adk.tools import google_search
from google.adk.workflow import node
from pydantic import ValidationError

from orchestrator.contracts import ConfidenceLevel, ResearchBrief
from orchestrator.registry_client import AgentRegistryClient

from ...logger import get_logger

logger = get_logger(__name__)


@node(name="managed_research_agent_node", rerun_on_resume=True)
async def managed_research_agent_node(ctx: Context, node_input: Any) -> ResearchBrief:
    """Executes the research skill using ADK's ManagedAgent.

    Constructs the tool list (google_search only) and resolves instructions
    dynamically from the Agent Registry on every invocation (ADR-0007, ADR-0009).
    """
    # 1. Validate inputs (B2, M3)
    if not isinstance(node_input, dict) or not node_input.get("research_question"):
        raise ValueError("research_question is required")

    research_question = str(node_input["research_question"]).strip()
    if not research_question:
        raise ValueError("research_question is required")

    project_id = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "dummy-project"
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")

    # 2. Resolve instructions dynamically from the Agent Registry (B1, B3)
    # TODO (D1): Add client-level in-memory cache keyed by (skill_id, defaultRevision) to avoid repeat fetches.
    async with AgentRegistryClient(project_id=project_id, location=location) as registry_client:
        try:
            instructions = await registry_client.get_skill_content("research")
        except Exception as e:
            logger.error(f"Failed to fetch research skill content from Agent Registry: {e}")
            raise RuntimeError(f"Failed to resolve research skill content from registry: {e}") from e

    agent_id = os.environ.get("MANAGED_AGENT_ID") or "antigravity-preview-05-2026"

    # 3. Instantiate ManagedAgent dynamically per planning cycle
    research_agent = ManagedAgent(
        name="research",
        description=instructions,
        agent_id=agent_id,
        environment={"type": "remote"},
        tools=[google_search],
        output_schema=ResearchBrief,
        rerun_on_resume=True,
    )

    logger.info(f"Invoking managed research agent with question: {research_question}")
    result = await ctx.run_node(research_agent, node_input=research_question)

    now = datetime.now(timezone.utc)

    # 4. Handle and validate return type (B4, M4)
    if isinstance(result, ResearchBrief):
        if not result.research_run_id:
            result.research_run_id = str(uuid.uuid4())
        if not result.as_of:
            result.as_of = now
        return result

    if isinstance(result, dict):
        candidate = dict(result)
        if not candidate.get("research_run_id"):
            candidate["research_run_id"] = str(uuid.uuid4())
        if not candidate.get("as_of"):
            candidate["as_of"] = now
        try:
            return ResearchBrief.model_validate(candidate)
        except (ValidationError, TypeError, ValueError) as val_err:
            logger.warning(f"Result dict could not be validated as ResearchBrief: {val_err}. Falling back to low-confidence brief.")

    # Absolute fallback to ensure we return a valid ResearchBrief even on malformed or string output
    return ResearchBrief(
        research_run_id=str(uuid.uuid4()),
        summary=str(result),
        sources=[],
        confidence=ConfidenceLevel.LOW,
        as_of=now,
    )
