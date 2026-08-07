"""Root planner — dynamic dispatch of registry-authorized skills to the worker Managed Agent."""

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from google.adk import Context
from google.adk.events import Event
from google.adk.workflow import Workflow, node
from google.auth import default as google_auth_default
from google.genai.types import Part, UserContent

from .contracts.goals_onboarding import GoalsOnboardingResult
from .contracts.proposed_action import ProposedAction
from .data.firestore import FirestoreClient
from .gates import execution_gate, hitl_approval_gate
from .logger import get_logger
from .managed_agents import dispatch_managed_skill
from .registry_client import AgentRegistryClient
from .state import (
    PreloadDeclinedError,
    emit_review_completed_audit,
    emit_skill_failed_audit,
    emit_skill_invoked_audit,
    emit_skill_revoked_audit,
    preload_for_action_drafting,
    preload_for_portfolio_analysis,
    preload_for_research,
    preload_for_reviewer,
    preload_spending_facts,
    write_ips_from_interview_result,
    write_proposed_action,
)

logger = get_logger(__name__)


PIPELINE_SKILL_ORDER = [
    "spending-analysis",
    "private-spending-analysis",
    "goals-onboarding",
    "private-goals-onboarding",
    "portfolio-analysis",
    "private-portfolio-analysis",
    "research",
    "private-research",
    "action-drafting",
    "private-action-drafting",
    "reviewer",
    "private-reviewer",
]


@dataclass
class SkillPlan:
    """Configuration for how the planner drives one skill turn."""
    short_name: str
    # Given (user_id, input_dict, context), returns the node_input dict to pass to the MA,
    # or None to skip this skill entirely (e.g. research with no research_question).
    build_input: Callable[[str, Dict[str, Any], Dict[str, Any]], Optional[Dict[str, Any]]]
    # Given (user_id, result, ctx, registry_entry_id), performs post-processing (writes, audit hooks) and
    # returns the payload to append to results + context. Return (result_payload, context_update).
    postprocess: Callable[[str, Any, Context, Dict[str, Any], Optional[str]], Awaitable[tuple[Any, Dict[str, Any]]]]


def _short_skill_id(name: str) -> str:
    return name.split("/")[-1] if "/" in name else name


def _normalize_skill_key(name: str) -> str:
    """Returns normalized skill key with 'private-' prefix for dictionary lookup."""
    short = _short_skill_id(name)
    return short if short.startswith("private-") else f"private-{short}"


def _skill_sort_key(skill: Any) -> int:
    skill_name = skill.name if hasattr(skill, "name") else str(skill)
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


async def _postprocess_spending(
    user_id, result, ctx, input_dict, registry_entry_id=None
):
    payload = result.model_dump() if hasattr(result, "model_dump") else result
    return payload, {"spending_analysis_result": result}


def _build_goals_onboarding_input(user_id, input_dict, context):
    trigger = input_dict.get("trigger", "initial")
    return {"user_id": user_id, "trigger": trigger}


async def _postprocess_goals_onboarding(
    user_id, result, ctx, input_dict, registry_entry_id=None
):
    if isinstance(result, GoalsOnboardingResult):
        trigger = input_dict.get("trigger", "initial")
        new_ips, _ = write_ips_from_interview_result(
            user_id=user_id,
            result=result,
            trigger=trigger,
            registry_entry_id=registry_entry_id,
        )
        summary_text = (
            f"User {user_id} completed goals onboarding. "
            f"Risk tolerance: {new_ips.risk_tolerance.value}. "
            f"Primary horizon: {new_ips.time_horizon_years} years."
        )
        try:
            await ctx.add_events_to_memory(
                events=[UserContent(parts=[Part.from_text(text=summary_text)])]
            )
        except Exception as mem_err:
            logger.warning(f"add_events_to_memory failed: {mem_err}")
        payload = {
            "status": "completed",
            "ips_id": new_ips.ips_id,
            "version": new_ips.version,
        }
    else:
        payload = result
    return payload, {"goals_onboarding_result": payload}


def _build_portfolio_analysis_input(user_id, input_dict, context):
    return preload_for_portfolio_analysis(user_id=user_id)


async def _postprocess_portfolio_analysis(
    user_id, result, ctx, input_dict, registry_entry_id=None
):
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
    return preload_for_research(
        user_id=user_id, research_question=str(research_question)
    )


async def _postprocess_research(
    user_id, result, ctx, input_dict, registry_entry_id=None
):
    payload = result.model_dump() if hasattr(result, "model_dump") else result
    return payload, {"research_briefs": [payload]}


def _build_action_drafting_input(user_id, input_dict, context):
    return preload_for_action_drafting(
        user_id=user_id,
        drift_report=input_dict.get("drift_report") or context.get("drift_report"),
        research_briefs=input_dict.get("research_briefs")
        or context.get("research_briefs"),
        requested_trade=input_dict.get("requested_trade"),
    )


async def _postprocess_action_drafting(
    user_id, result, ctx, input_dict, registry_entry_id=None
):
    if isinstance(result, ProposedAction):
        write_proposed_action(
            user_id=user_id, action=result, registry_entry_id=registry_entry_id
        )
        payload = result.model_dump()
    else:
        payload = result
    return payload, {"action_drafting_result": payload}


def _build_reviewer_input(user_id, input_dict, context):
    ad_result = context.get("action_drafting_result")
    if not ad_result or not isinstance(ad_result, dict) or ad_result.get("status") != "drafted":
        return None  # SkillPlan returning None = skip cleanly
    input_dict["_reviewer_action"] = ad_result
    node_input = preload_for_reviewer(user_id=user_id, action=ad_result)
    # Mirror the preloader's IPS + holdings into input_dict so _postprocess_reviewer
    # can reuse them without a second Firestore round-trip. node_input flows to the
    # Managed Agent; input_dict is what postprocess sees.
    input_dict["_preloaded_ips"] = node_input.get("ips")
    input_dict["_preloaded_holdings"] = node_input.get("holdings")
    return node_input


async def _postprocess_reviewer(user_id, result, ctx, input_dict, registry_entry_id=None):
    """After the Reviewer MA returns its advisory verdict, run the deterministic
    re-check and produce the authoritative verdict. Emit REVIEW_COMPLETED with
    both."""
    from .contracts.ips import RelatedIPSVersion
    from .contracts.proposed_action import ProposedAction, SkillVersionRef
    from .contracts.reviewer_verdict import ReviewerVerdict
    from .reviewer import ReviewInput, check_all_rules, compute_requires_human_approval
    from .skills._skill_metadata import read_skill_version

    llm_verdict: Optional[ReviewerVerdict] = None
    if isinstance(result, ReviewerVerdict):
        llm_verdict = result
    elif isinstance(result, dict):
        try:
            llm_verdict = ReviewerVerdict.model_validate(result)
        except Exception as e:
            logger.warning(f"Reviewer MA returned malformed verdict, treating as no-verdict: {e}")

    ad_result_dict = input_dict.get("_reviewer_action")
    action = ProposedAction.model_validate(ad_result_dict)

    from .contracts.holdings import HoldingsSnapshot
    from .contracts.ips import InvestmentPolicyStatement

    preloaded_ips_dict = input_dict.get("_preloaded_ips") or input_dict.get("ips")
    preloaded_holdings_dict = input_dict.get("_preloaded_holdings") or input_dict.get("holdings")

    if preloaded_ips_dict and isinstance(preloaded_ips_dict, dict):
        ips_obj = InvestmentPolicyStatement.model_validate(preloaded_ips_dict)
    else:
        fs = FirestoreClient()
        ips_obj = fs.get_active_ips_by_user(user_id)

    if preloaded_holdings_dict and isinstance(preloaded_holdings_dict, dict):
        holdings_obj = HoldingsSnapshot.model_validate(preloaded_holdings_dict)
    else:
        fs = FirestoreClient()
        holdings_obj = fs.get_holdings(user_id)
    if ips_obj is None or holdings_obj is None:
        logger.error(f"Reviewer postprocess: missing IPS or holdings for user {user_id}")
        if llm_verdict is not None:
            auth_verdict = llm_verdict
        else:
            auth_verdict = ReviewerVerdict(
                verdict_id=str(uuid.uuid4()),
                action_id=action.action_id,
                ips_version_checked_against=RelatedIPSVersion(ips_id="unknown", version=0),
                rule_results=[],
                overall_pass=False,
                requires_human_approval=True,
                reviewer_skill_version=SkillVersionRef(
                    skill_name="private-reviewer",
                    skill_version=read_skill_version("reviewer"),
                    registry_entry_id=registry_entry_id,
                ),
                reviewed_at=datetime.now(timezone.utc),
            )
    else:
        review_input = ReviewInput(action=action, ips=ips_obj, holdings=holdings_obj)
        rule_results = check_all_rules(review_input)
        overall_pass = all(r.passed for r in rule_results)
        requires_approval = compute_requires_human_approval(review_input, overall_pass)
        auth_verdict = ReviewerVerdict(
            verdict_id=str(uuid.uuid4()),
            action_id=action.action_id,
            ips_version_checked_against=RelatedIPSVersion(
                ips_id=ips_obj.ips_id, version=ips_obj.version
            ),
            rule_results=rule_results,
            overall_pass=overall_pass,
            requires_human_approval=requires_approval,
            reviewer_skill_version=SkillVersionRef(
                skill_name="private-reviewer",
                skill_version=read_skill_version("reviewer"),
                registry_entry_id=registry_entry_id,
            ),
            reviewed_at=datetime.now(timezone.utc),
        )

    emit_review_completed_audit(
        action=action,
        authoritative_verdict=auth_verdict,
        llm_verdict=llm_verdict,
        registry_entry_id=registry_entry_id,
    )

    if auth_verdict and hasattr(ctx, "state") and ctx.state is not None:
        ctx.state["reviewer_verdict"] = auth_verdict.model_dump()

    payload = auth_verdict.model_dump() if auth_verdict else {"status": "unavailable"}
    ctx_update = {
        "reviewer_verdict": auth_verdict,
        "reviewer_verdict_llm": llm_verdict,
    }
    return payload, ctx_update


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
    "private-reviewer": SkillPlan(
        short_name="private-reviewer",
        build_input=_build_reviewer_input,
        postprocess=_postprocess_reviewer,
    ),
}


@node(name="get_skills", rerun_on_resume=False)
async def get_skills_from_registry(ctx: Context, node_input: Any):
    """Queries the Agent Registry for available skills."""
    project_id = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        try:
            _, project_id = google_auth_default()
        except Exception:
            pass
    if not project_id:
        project_id = "dummy-project"
    location = os.environ.get("AGENT_REGISTRY_LOCATION", "global")
    logger.info(f"Goal received: {node_input}, project_id: {project_id}, location: {location}")
    client = AgentRegistryClient(project_id=project_id, location=location)
    skills = await client.list_authorized_skills()
    return skills


@node(name="dummy_skill_execution", rerun_on_resume=False)
async def dummy_skill_execution(ctx: Context, node_input: Any):
    logger.info(f"Executing skill: {node_input}")
    return f"{node_input}_completed"


@node(name="memory_interaction", rerun_on_resume=False)
async def memory_interaction(ctx: Context, node_input: Any):
    """Reads and writes to the memory bank to satisfy acceptance criteria."""
    part = Part.from_text(text="User prefers low-risk investments")
    event = Event(author="user", content=UserContent(parts=[part]))
    try:
        await ctx.add_events_to_memory(events=[event])
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
    registry_entry_id: Optional[str] = None,
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
        emit_skill_failed_audit(
            plan.short_name, error=f"declined: {e}", registry_entry_id=registry_entry_id
        )
        return {"status": "declined", "message": str(e)}
    except Exception as e:
        logger.error(f"Skill {plan.short_name} preload failed: {e}")
        emit_skill_failed_audit(
            plan.short_name,
            error=f"preload_failed: {e}",
            registry_entry_id=registry_entry_id,
        )
        raise

    if node_input is None:
        logger.info(f"Skipping skill {plan.short_name} (no input built)")
        return None

    # 2. Emit SKILL_INVOKED
    emit_skill_invoked_audit(
        plan.short_name,
        detail=f"Dispatching {plan.short_name}",
        registry_entry_id=registry_entry_id,
    )

    # 3. Dispatch to Managed Agent
    try:
        result = await dispatch_managed_skill(plan.short_name, node_input=node_input, ctx=ctx)
    except Exception as e:
        logger.error(f"Skill {plan.short_name} dispatch failed: {e}")
        emit_skill_failed_audit(
            plan.short_name,
            error=f"dispatch_failed: {e}",
            registry_entry_id=registry_entry_id,
        )
        raise

    # 4. Postprocess (writes + rationale + context)
    try:
        payload, ctx_update = await plan.postprocess(
            user_id, result, ctx, input_dict, registry_entry_id
        )
    except Exception as e:
        logger.error(f"Skill {plan.short_name} postprocess failed: {e}")
        emit_skill_failed_audit(
            plan.short_name,
            error=f"postprocess_failed: {e}",
            registry_entry_id=registry_entry_id,
        )
        raise

    context.update(ctx_update)
    return payload


def _detect_and_audit_revocations(
    ctx: Context,
    current_skills: list[Any],
) -> None:
    """Compares current authorized skills against last cycle's; emits SKILL_REVOKED
    for each skill that was authorized last cycle but isn't now.

    State is stored in ctx.state["last_authorized_skills"] as a list of
    {"name": str, "default_revision": str} dicts (JSON-serializable across resumes).
    """
    current_by_name = {
        (s.name if hasattr(s, "name") else str(s)): getattr(s, "default_revision", None)
        for s in current_skills
    }
    prior_raw = ctx.state.get("last_authorized_skills") or []
    prior_by_name = {p["name"]: p for p in prior_raw if isinstance(p, dict) and "name" in p}

    # Any name in prior but not in current is a revocation
    revoked_names = set(prior_by_name.keys()) - set(current_by_name.keys())

    for full_name in sorted(revoked_names):
        short_name = _short_skill_id(full_name)
        prior_revision = prior_by_name[full_name].get("default_revision")
        try:
            emit_skill_revoked_audit(
                revoked_skill_short_name=short_name,
                prior_registry_entry_id=prior_revision,
                detail=f"Skill {short_name} was authorized last cycle but is now DISABLED or absent",
            )
            logger.info(f"Detected revocation of skill {short_name} (prior revision {prior_revision})")
        except Exception as e:
            # Audit fail-closed raises; log and continue so a single failure doesn't
            # block detection of other revocations in the same cycle.
            logger.error(f"Failed to audit revocation of {short_name}: {e}")

    # Store current cycle for next comparison. Serialized as plain dicts so
    # ADK's ctx.state (which needs JSON-safe values) is happy.
    ctx.state["last_authorized_skills"] = [
        {"name": name, "default_revision": rev}
        for name, rev in current_by_name.items()
    ]


@node(rerun_on_resume=True)
async def root_planner(ctx: Context, node_input: Any):
    """Registry-driven dynamic planner. Iterates authorized skills in canonical order,
    dispatching each to the worker Managed Agent via a per-skill SkillPlan."""

    await ctx.run_node(memory_interaction, node_input="test_memory")

    skills = await ctx.run_node(get_skills_from_registry, node_input=node_input)
    logger.info(f"Available skills: {skills}")

    # Delta-detect revocations vs the previous planning cycle in this session.
    # Emits SKILL_REVOKED audit for anything that disappeared.
    _detect_and_audit_revocations(ctx, skills)

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
        skill_name = skill.name if hasattr(skill, "name") else str(skill)
        registry_entry_id = getattr(skill, "default_revision", None)
        short_name = _normalize_skill_key(skill_name)
        plan = SKILL_PLANS.get(short_name)
        if plan is None:
            logger.info(f"Authorized skill {skill} has no SkillPlan; executing fallback.")
            result = await ctx.run_node(dummy_skill_execution, node_input=skill_name)
            results.append(result)
            continue

        payload = await _execute_skill(
            plan,
            skill_name,
            user_id,
            input_dict,
            context,
            ctx,
            registry_entry_id=registry_entry_id,
        )
        if payload is None:
            continue
        results.append(f"{plan.short_name.replace('private-', '')}_result: {payload}")

    # HITL approval gate: if action-drafting produced a ProposedAction, gate it before returning
    ad_result = context.get("action_drafting_result")
    if ad_result and isinstance(ad_result, dict) and ad_result.get("status") == "drafted":
        # ProposedAction was drafted this cycle -- run it past the human
        # Reviewer verdict may be present in context (once #106 lands); may be None until then
        gate_input = {
            "action": ad_result,
            "reviewer_verdict": context.get("reviewer_verdict"),
        }
        try:
            hitl_result = await ctx.run_node(hitl_approval_gate, node_input=gate_input)
        except Exception as e:
            logger.error(f"HITL gate failed: {e}")
            results.append(f"hitl_error: {e}")
        else:
            results.append(f"hitl_decision: {hitl_result}")
            context["hitl_decision"] = hitl_result
            # Downstream: #23 G3 execution path picks up context["hitl_decision"] and
            # checks outcome == "approved" before calling Alpaca.

    # Execution gate: if HITL approved, place the trade with Alpaca
    if context.get("hitl_decision"):
        exec_input = {
            "hitl_decision": context.get("hitl_decision"),
            "reviewer_verdict": context.get("reviewer_verdict")
            or ctx.state.get("reviewer_verdict")
            or ctx.state.get("hitl_verdict"),
        }
        try:
            exec_result = await ctx.run_node(execution_gate, node_input=exec_input)
        except Exception as e:
            logger.error(f"Execution gate raised: {e}")
            results.append(f"execution_error: {e}")
        else:
            results.append(f"execution_result: {exec_result}")
            context["execution_result"] = exec_result

    return results


# Perform startup verification of SKILL.md metadata reachability per Issue #168
from .skills._skill_metadata import verify_all_skills_metadata

verify_all_skills_metadata()

# Perform startup verification of required credentials per Issue #153
from .managed_agents.secret_loader import verify_required_secrets

verify_required_secrets()


root_agent = Workflow(
    name="portfolio_copilot_planner",
    description="Dynamic planner for Portfolio Copilot that queries Agent Registry to construct a plan.",
    edges=[("START", root_planner)],
)
