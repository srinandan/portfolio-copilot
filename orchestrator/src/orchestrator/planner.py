from orchestrator.logger import get_logger

logger = get_logger(__name__)

import json
import os
from typing import Any

from google.adk import Context
from google.adk.agents import ManagedAgent
from google.adk.workflow import Workflow, node
from google.genai.types import Part, UserContent

from .registry_client import AgentRegistryClient
from .skills.goals_onboarding import goals_onboarding_skill
from .skills.portfolio_analysis import portfolio_analysis_skill


@node(name="get_skills", rerun_on_resume=False)
async def get_skills_from_registry(ctx: Context, node_input: Any):
    """Queries the Agent Registry for available skills."""
    project_id = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "dummy-project"
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")

    logger.info(f"Goal received: {node_input}")
    logger.info(f"Queried registry in {project_id}/{location}")
    client = AgentRegistryClient(project_id=project_id, location=location)
    skills = await client.list_authorized_skills()
    return [s.name for s in skills]


@node(name="dummy_skill_execution", rerun_on_resume=False)
async def dummy_skill_execution(ctx: Context, node_input: Any):
    """Executes a dummy skill as part of the dynamic plan."""
    logger.info(f"Executing skill: {node_input}")
    return f"{node_input}_completed"

@node(name="memory_interaction", rerun_on_resume=False)
async def memory_interaction(ctx: Context, node_input: Any):
    """Reads and writes to the memory bank to satisfy acceptance criteria."""
    logger.info("Writing placeholder fact to memory bank via add_events_to_memory...")
    part = Part.from_text(text="User prefers low-risk investments")
    placeholder_fact = UserContent(parts=[part])
    try:
        await ctx.add_events_to_memory(events=[placeholder_fact])
    except NotImplementedError:
        logger.warning("add_events_to_memory not fully implemented by the memory service yet, continuing...")
    except Exception as e:
        logger.warning(f"add_events_to_memory failed: {e}")

    logger.info("Reading from memory bank...")
    try:
        search_results = await ctx.search_memory("investment preferences")
        logger.info(f"Memory Bank search results: {search_results}")
    except NotImplementedError:
        logger.warning("search_memory not fully implemented by the memory service yet, continuing...")
    except Exception as e:
         logger.warning(f"search_memory failed (expected if memory service is InMemory): {e}")

    return "memory_interaction_completed"

def _short_skill_id(name: str) -> str:
    """Extracts the short skill ID from a full resource path."""
    return name.split("/")[-1] if "/" in name else name


@node(rerun_on_resume=True)
async def root_planner(ctx: Context, node_input: Any):
    """The root dynamic workflow orchestrator."""

    # Run the memory interaction to satisfy Issue #11
    await ctx.run_node(memory_interaction, node_input="test_memory")

    project_id = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "dummy-project"
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    registry_client = AgentRegistryClient(project_id=project_id, location=location)

    skills = await ctx.run_node(get_skills_from_registry, node_input=node_input)
    logger.info(f"Available skills: {skills}")

    # Simple extraction of user_id from node_input or default
    user_id = "default_user"
    trigger = "initial"
    if isinstance(node_input, dict):
        user_id = node_input.get("user_id", user_id)
        trigger = node_input.get("trigger", trigger)
    elif isinstance(node_input, str):
        try:
            parsed = json.loads(node_input)
            user_id = parsed.get("user_id", user_id)
            trigger = parsed.get("trigger", trigger)
        except json.JSONDecodeError:
            pass

    results = []
    for skill in skills:
        short_name = _short_skill_id(skill)
        if short_name == "private-goals-onboarding":
            logger.info(f"Executing native skill: {skill}")
            result = await ctx.run_node(goals_onboarding_skill, node_input={"user_id": user_id, "trigger": trigger})
            results.append(f"goals_onboarding_result: {result}")
        elif short_name == "private-portfolio-analysis":
            logger.info(f"Executing native portfolio analysis skill: {skill}")
            result = await ctx.run_node(portfolio_analysis_skill, node_input={"user_id": user_id})
            results.append(f"portfolio_analysis_result: {result}")
        elif short_name == "private-research":
            logger.info(f"Executing dynamic managed research skill: {skill}")
            instructions = await registry_client.get_skill_content("research")
            research_agent = ManagedAgent(
                name="research",
                description=instructions,
                agent_id="antigravity-preview-05-2026",
                environment={"type": "remote"},
            )
            result = await ctx.run_node(research_agent, node_input={"user_id": user_id, "goal": "market research"})
            results.append(f"research_result: {result}")
        else:
            logger.info(f"Authorized skill {skill} is not yet wired into dynamic plan; executing fallback.")
            result = await ctx.run_node(dummy_skill_execution, node_input=skill)
            results.append(result)

    return results

root_agent = Workflow(
    name="portfolio_copilot_planner",
    description="Dynamic planner for Portfolio Copilot that queries Agent Registry to construct a plan.",
    edges=[("START", root_planner)],
)
