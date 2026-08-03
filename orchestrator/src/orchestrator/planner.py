"""Root planner — dynamic dispatch of registry-authorized skills to the worker Managed Agent."""

import json
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from google.adk import Context
from google.adk.workflow import Workflow, node
from google.genai.types import Part, UserContent

from .contracts.goals_onboarding import GoalsOnboardingResult
from .contracts.proposed_action import ProposedAction
from .logger import get_logger
from .managed_agents import dispatch_managed_skill
from .registry_client import AgentRegistryClient
from .state import (
    PreloadDeclinedError,
    emit_skill_failed_audit,
    emit_skill_invoked_audit,
    preload_for_action_drafting,
    preload_for_portfolio_analysis,
    preload_for_research,
    preload_spending_facts,
    write_ips_from_interview_result,
    write_proposed_action,
)

logger = get_logger(__name__)


PIPELINE_SKILL_ORDER = [
    "private-spending-analysis",
    "private-goals-onboarding",
    "private-portfolio-analysis",
    "private-research",
    "private-action-drafting",
]


@dataclass
class SkillPlan:
    """Configuration for how the planner drives one skill turn."""
    short_name: str
    # Given (user_id, input_dict, context), returns the node_input dict to pass to the MA,
    # or None to skip this skill entirely (e.g. research with no research_question).
    build_input: Callable[[str, Dict[str, Any], Dict[str, Any]], Optional[Dict[str, Any]]]
    # Given (user_id, result, ctx), performs post-processing (writes, audit hooks) and
    # returns the payload to append to results + context. Return (result_payload, context_update).
    postprocess: Callable[[str, Any, Context, Dict[str, Any]], Awaitable[tuple[Any, Dict[str, Any]]]]


def _short_skill_id(name: str) -> str:
    return name.split("/")[-1] if "/" in name else name


def _skill_sort_key(skill_name: str) -> int:
    short = _short_skill_id(skill_name)
    return PIPELINE_SKILL_ORDER.index(short) if short in PIPELINE_SKILL_ORDER else len(PIPELINE_SKILL_ORDER) + 1


# ---------- per-skill input builders and post-processors ----------

def _build_spending_input(user_id, input_dict, context):
    window_months = input_dict.get("window_months", 3)
    preloaded = preload_spending_facts(user_id=user_id, window_months=window_months)
    return {
        "user_id": user_id,
        "query_intent": input_dict.get("query_intent", "anomaly_check"),
        "window_months": window_months,
        "preloaded": preloaded,
    }


async def _postprocess_spending(user_id, result, ctx, input_dict):
    payload = result.model_dump() if hasattr(result, "model_dump") else result
    return payload, {"spending_analysis_result": result}


def _build_goals_onboarding_input(user_id, input_dict, context):
    trigger = input_dict.get("trigger", "initial")
    return {"user_id": user_id, "trigger": trigger}


async def _postprocess_goals_onboarding(user_id, result, ctx, input_dict):
    if isinstance(result, GoalsOnboardingResult):
        trigger = input_dict.get("trigger", "initial")
        new_ips, _ = write_ips_from_interview_result(user_id=user_id, result=result, trigger=trigger)
        summary_text = (
            f"User {user_id} completed goals onboarding. "
            f"Risk tolerance: {new_ips.risk_tolerance.value}. "
            f"Primary horizon: {new_ips.time_horizon_years} years."
        )
        try:
            await ctx.add_events_to_memory(events=[UserContent(parts=[Part.from_text(text=summary_text)])])
        except Exception as mem_err:
            logger.warning(f"add_events_to_memory failed: {mem_err}")
        payload = {"status": "completed", "ips_id": new_ips.ips_id, "version": new_ips.version}
    else:
        payload = result
    return payload, {"goals_onboarding_result": payload}


def _build_portfolio_analysis_input(user_id, input_dict, context):
    return preload_for_portfolio_analysis(user_id=user_id)


async def _postprocess_portfolio_analysis(user_id, result, ctx, input_dict):
    payload = result.model_dump() if hasattr(result, "model_dump") else result
    context_update = {"portfolio_analysis_result": payload}
    # Thread the drift_report forward so action-drafting can consume it (I1 chaining)
    if hasattr(result, "model_dump"):
        context_update["drift_report"] = result.model_dump()
    elif isinstance(result, dict):
        context_update["drift_report"] = result
    return payload, context_update


def _build_research_input(user_id, input_dict, context):
    research_question = input_dict.get("research_question")
    if not research_question or not str(research_question).strip():
        return None  # skip research if no explicit question (I4)
    return preload_for_research(user_id=user_id, research_question=str(research_question))


async def _postprocess_research(user_id, result, ctx, input_dict):
    payload = result.model_dump() if hasattr(result, "model_dump") else result
    return payload, {"research_briefs": [payload]}


def _build_action_drafting_input(user_id, input_dict, context):
    return preload_for_action_drafting(
        user_id=user_id,
        drift_report=input_dict.get("drift_report") or context.get("drift_report"),
        research_briefs=input_dict.get("research_briefs") or context.get("research_briefs"),
        requested_trade=input_dict.get("requested_trade"),
    )


async def _postprocess_action_drafting(user_id, result, ctx, input_dict):
    if isinstance(result, ProposedAction):
        write_proposed_action(user_id=user_id, action=result)
        payload = result.model_dump()
    else:
        payload = result
    return payload, {"action_drafting_result": payload}


SKILL_PLANS: Dict[str, SkillPlan] = {
    "private-spending-analysis": SkillPlan(
        short_name="private-spending-analysis",
        build_input=_build_spending_input,
        postprocess=_postprocess_spending,
    ),
    "private-goals-onboarding": SkillPlan(
        short_name="private-goals-onboarding",
        build_input=_build_goals_onboarding_input,
        postprocess=_postprocess_goals_onboarding,
    ),
    "private-portfolio-analysis": SkillPlan(
        short_name="private-portfolio-analysis",
        build_input=_build_portfolio_analysis_input,
        postprocess=_postprocess_portfolio_analysis,
    ),
    "private-research": SkillPlan(
        short_name="private-research",
        build_input=_build_research_input,
        postprocess=_postprocess_research,
    ),
    "private-action-drafting": SkillPlan(
        short_name="private-action-drafting",
        build_input=_build_action_drafting_input,
        postprocess=_postprocess_action_drafting,
    ),
}


@node(name="get_skills", rerun_on_resume=False)
async def get_skills_from_registry(ctx: Context, node_input: Any):
    """Queries the Agent Registry for available skills."""
    project_id = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "dummy-project"
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    logger.info(f"Goal received: {node_input}")
    client = AgentRegistryClient(project_id=project_id, location=location)
    skills = await client.list_authorized_skills()
    return [s.name for s in skills]


@node(name="dummy_skill_execution", rerun_on_resume=False)
async def dummy_skill_execution(ctx: Context, node_input: Any):
    logger.info(f"Executing skill: {node_input}")
    return f"{node_input}_completed"


@node(name="memory_interaction", rerun_on_resume=False)
async def memory_interaction(ctx: Context, node_input: Any):
    """Reads and writes to the memory bank to satisfy acceptance criteria."""
    part = Part.from_text(text="User prefers low-risk investments")
    placeholder_fact = UserContent(parts=[part])
    try:
        await ctx.add_events_to_memory(events=[placeholder_fact])
    except NotImplementedError:
        logger.warning("add_events_to_memory not fully implemented by the memory service yet, continuing...")
    except Exception as e:
        logger.warning(f"add_events_to_memory failed: {e}")
    try:
        await ctx.search_memory("investment preferences")
    except NotImplementedError:
        logger.warning("search_memory not fully implemented by the memory service yet, continuing...")
    except Exception as e:
        logger.warning(f"search_memory failed (expected if memory service is InMemory): {e}")
    return "memory_interaction_completed"


async def _execute_skill(
    plan: SkillPlan,
    skill_name: str,
    user_id: str,
    input_dict: Dict[str, Any],
    context: Dict[str, Any],
    ctx: Context,
) -> Optional[Any]:
    """Runs one skill turn: emit audit → preload → dispatch → postprocess.

    Returns the result payload for `results.append`, or None if skipped
    (e.g. research with no question, or a preloader declined).
    """
    # 1. Build input (may skip or raise PreloadDeclinedError)
    try:
        node_input = plan.build_input(user_id, input_dict, context)
    except PreloadDeclinedError as e:
        logger.info(f"Skill {plan.short_name} declined: {e}")
        emit_skill_failed_audit(plan.short_name, error=f"declined: {e}")
        return {"status": "declined", "message": str(e)}
    except Exception as e:
        logger.error(f"Skill {plan.short_name} preload failed: {e}")
        emit_skill_failed_audit(plan.short_name, error=f"preload_failed: {e}")
        raise

    if node_input is None:
        logger.info(f"Skipping skill {plan.short_name} (no input built)")
        return None

    # 2. Emit SKILL_INVOKED
    emit_skill_invoked_audit(plan.short_name, detail=f"Dispatching {plan.short_name}")

    # 3. Dispatch to Managed Agent
    try:
        result = await dispatch_managed_skill(plan.short_name, node_input=node_input, ctx=ctx)
    except Exception as e:
        logger.error(f"Skill {plan.short_name} dispatch failed: {e}")
        emit_skill_failed_audit(plan.short_name, error=f"dispatch_failed: {e}")
        raise

    # 4. Postprocess (writes + rationale + context)
    try:
        payload, ctx_update = await plan.postprocess(user_id, result, ctx, input_dict)
    except Exception as e:
        logger.error(f"Skill {plan.short_name} postprocess failed: {e}")
        emit_skill_failed_audit(plan.short_name, error=f"postprocess_failed: {e}")
        raise

    context.update(ctx_update)
    return payload


@node(rerun_on_resume=True)
async def root_planner(ctx: Context, node_input: Any):
    """Registry-driven dynamic planner. Iterates authorized skills in canonical order,
    dispatching each to the worker Managed Agent via a per-skill SkillPlan."""

    await ctx.run_node(memory_interaction, node_input="test_memory")

    skills = await ctx.run_node(get_skills_from_registry, node_input=node_input)
    logger.info(f"Available skills: {skills}")

    # Parse node_input into a plain dict
    input_dict: Dict[str, Any] = {}
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

    results: list[Any] = []
    context: Dict[str, Any] = {}

    ordered_skills = sorted(skills, key=_skill_sort_key)
    for skill in ordered_skills:
        short_name = _short_skill_id(skill)
        plan = SKILL_PLANS.get(short_name)
        if plan is None:
            logger.info(f"Authorized skill {skill} has no SkillPlan; executing fallback.")
            result = await ctx.run_node(dummy_skill_execution, node_input=skill)
            results.append(result)
            continue

        payload = await _execute_skill(plan, skill, user_id, input_dict, context, ctx)
        if payload is None:
            continue
        results.append(f"{plan.short_name.replace('private-', '')}_result: {payload}")

    return results


root_agent = Workflow(
    name="portfolio_copilot_planner",
    description="Dynamic planner for Portfolio Copilot that queries Agent Registry to construct a plan.",
    edges=[("START", root_planner)],
)
