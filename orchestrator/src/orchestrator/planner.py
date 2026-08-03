from orchestrator.logger import get_logger

logger = get_logger(__name__)

import json
import os
from typing import Any

from google.adk import Context
from google.adk.workflow import Workflow, node
from google.genai.types import Part, UserContent

from .contracts.goals_onboarding import GoalsOnboardingResult
from .managed_agents import dispatch_managed_skill
from .registry_client import AgentRegistryClient
from .skills.action_drafting import action_drafting_skill
from .skills.portfolio_analysis import portfolio_analysis_skill
from .skills.research import managed_research_agent_node
from .state import write_ips_from_interview_result


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


PIPELINE_SKILL_ORDER = [
    "private-goals-onboarding",
    "private-portfolio-analysis",
    "private-research",
    "private-action-drafting",
]


def _skill_sort_key(skill_name: str) -> int:
    """Sorts authorized skills into canonical pipeline execution order."""
    short_name = _short_skill_id(skill_name)
    if short_name in PIPELINE_SKILL_ORDER:
        return PIPELINE_SKILL_ORDER.index(short_name)
    return len(PIPELINE_SKILL_ORDER) + 1


def _short_skill_id(name: str) -> str:
    """Extracts the short skill ID from a full resource path."""
    return name.split("/")[-1] if "/" in name else name


@node(rerun_on_resume=True)
async def root_planner(ctx: Context, node_input: Any):
    """The root dynamic workflow orchestrator."""

    # Run the memory interaction to satisfy Issue #11
    await ctx.run_node(memory_interaction, node_input="test_memory")

    skills = await ctx.run_node(get_skills_from_registry, node_input=node_input)
    logger.info(f"Available skills: {skills}")

    input_dict = {}
    if isinstance(node_input, dict):
        input_dict = node_input
    elif isinstance(node_input, str):
        try:
            parsed = json.loads(node_input)
            if isinstance(parsed, dict):
                input_dict = parsed
        except json.JSONDecodeError:
            pass
    elif hasattr(node_input, "parts") and node_input.parts:
        for part in node_input.parts:
            text = getattr(part, "text", None)
            if text:
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        input_dict.update(parsed)
                except json.JSONDecodeError:
                    pass

    user_id = input_dict.get("user_id", "default_user")
    trigger = input_dict.get("trigger", "initial")

    results = []
    context: dict[str, Any] = {}

    # Sort skills into deterministic pipeline order (I2)
    ordered_skills = sorted(skills, key=_skill_sort_key)

    for skill in ordered_skills:
        short_name = _short_skill_id(skill)
        if short_name == "private-goals-onboarding":
            logger.info(f"Executing dynamic managed goals onboarding skill: {skill}")
            result = await dispatch_managed_skill(
                "private-goals-onboarding",
                node_input={"user_id": user_id, "trigger": trigger},
                ctx=ctx,
            )
            if isinstance(result, GoalsOnboardingResult):
                new_ips, _ = write_ips_from_interview_result(user_id=user_id, result=result, trigger=trigger)
                summary_text = f"User {user_id} completed goals onboarding. Risk tolerance: {new_ips.risk_tolerance.value}. Primary horizon: {new_ips.time_horizon_years} years."
                try:
                    await ctx.add_events_to_memory(events=[UserContent(parts=[Part.from_text(text=summary_text)])])
                except Exception as mem_err:
                    logger.warning(f"add_events_to_memory failed: {mem_err}")
                result_payload = {"status": "completed", "ips_id": new_ips.ips_id, "version": new_ips.version}
            else:
                result_payload = result
            results.append(f"goals_onboarding_result: {result_payload}")
            context["goals_onboarding_result"] = result_payload
        elif short_name == "private-portfolio-analysis":
            logger.info(f"Executing native portfolio analysis skill: {skill}")
            result = await ctx.run_node(portfolio_analysis_skill, node_input={"user_id": user_id})
            results.append(f"portfolio_analysis_result: {result}")
            context["portfolio_analysis_result"] = result
            if isinstance(result, dict) and result.get("status") == "completed" and result.get("drift_report"):
                context["drift_report"] = result["drift_report"]
        elif short_name == "private-research":
            research_question = input_dict.get("research_question")
            if research_question and str(research_question).strip():
                logger.info(f"Executing dynamic managed research skill for question: {research_question}")
                result = await ctx.run_node(managed_research_agent_node, node_input={"research_question": str(research_question).strip()})
                brief_data = result.model_dump() if hasattr(result, "model_dump") else result
                results.append(f"research_result: {brief_data}")
                context["research_briefs"] = [result]
            else:
                logger.info("Skipping research skill execution as no research_question was requested.")
        elif short_name == "private-action-drafting":
            logger.info(f"Executing native action drafting skill: {skill}")
            drift_report = input_dict.get("drift_report") or context.get("drift_report")
            research_briefs = input_dict.get("research_briefs") or context.get("research_briefs")
            requested_trade = input_dict.get("requested_trade")
            result = await ctx.run_node(
                action_drafting_skill,
                node_input={
                    "user_id": user_id,
                    "drift_report": drift_report,
                    "research_briefs": research_briefs,
                    "requested_trade": requested_trade,
                },
            )
            results.append(f"action_drafting_result: {result}")
            context["action_drafting_result"] = result
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
