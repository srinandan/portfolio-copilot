import os
import uuid
from datetime import datetime, timezone
from typing import Any

from google.adk import Context
from google.adk.agents import ManagedAgent
from google.adk.tools import google_search
from google.adk.workflow import node

from orchestrator.contracts import ResearchBrief
from orchestrator.registry_client import AgentRegistryClient

from ...logger import get_logger

logger = get_logger(__name__)

@node(name="managed_research_agent_node", rerun_on_resume=True)
async def managed_research_agent_node(ctx: Context, node_input: Any):
    """
    Executes the research skill using ADK's ManagedAgent.
    Constructs the tool list (google_search only) and resolves
    instructions from the Agent Registry on every invocation.
    """
    project_id = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "dummy-project"
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    registry_client = AgentRegistryClient(project_id=project_id, location=location)

    # Resolve instructions dynamically from the Agent Registry
    try:
        instructions = await registry_client.get_skill_content("research")
    except Exception as e:
        logger.error(f"Failed to fetch research skill content: {e}")
        # Fallback instruction if registry unavailable during dev/tests, but log heavily
        instructions = (
            "Gather external market and news context to inform a potential action. "
            "Never fabricate a conclusion. If inconclusive, set confidence to low."
        )

    # Instantiate ManagedAgent dynamically per planning cycle
    research_agent = ManagedAgent(
        name="research",
        description=instructions,
        agent_id="antigravity-preview-05-2026",
        environment={"type": "remote"},
        tools=[google_search],
        output_schema=ResearchBrief,
        rerun_on_resume=True
    )

    # Parse input for the research_question
    research_question = "What are current market conditions?"
    if isinstance(node_input, dict) and "research_question" in node_input:
        research_question = node_input["research_question"]
    elif isinstance(node_input, str):
        research_question = node_input

    logger.info(f"Invoking managed research agent with question: {research_question}")
    result = await ctx.run_node(research_agent, node_input=research_question)

    # Ensure a stable run ID if one isn't produced by the model (though it should map to the Pydantic schema)
    if isinstance(result, ResearchBrief):
        if not result.research_run_id:
             result.research_run_id = str(uuid.uuid4())
        # Set as_of strictly to current time if missing or as a fallback just in case
        if not result.as_of:
             result.as_of = datetime.now(timezone.utc)
        return result

    elif isinstance(result, dict):
        # Fallback if returned as raw dict
        if "research_run_id" not in result or not result["research_run_id"]:
             result["research_run_id"] = str(uuid.uuid4())
        if "as_of" not in result or not result["as_of"]:
             result["as_of"] = datetime.now(timezone.utc)
        return ResearchBrief(**result)

    # Absolute fallback to ensure we ALWAYS return a ResearchBrief even if ManagedAgent somehow returned plain text
    return ResearchBrief(
        research_run_id=str(uuid.uuid4()),
        summary=str(result),
        sources=[],
        confidence="low",
        as_of=datetime.now(timezone.utc)
    )
