import asyncio
import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from google.adk import Context
from google.adk.workflow import Workflow, node
from google.auth import default as google_auth_default
from google.genai.types import Part, UserContent

from .contracts.goals_onboarding import GoalsOnboardingResult
from .contracts.ips import RelatedIPSVersion
from .contracts.proposed_action import (
    ActionStatus,
    ActionType,
    ProposedAction,
    SkillVersionRef,
)
from .contracts.spending_analysis import SpendingReport
from .data.firestore import FirestoreClient
from .gates import execution_gate, hitl_approval_gate
from .logger import get_logger
from .managed_agents import dispatch_managed_skill
from .planning import (
    DEFAULT_POLICY,
    DEFAULT_RETRIEVER,
    applied_rules,
    classify_intent,
    resolve_and_schedule,
    select_leaves,
)
from .progress import STAGE_LABELS, report_progress, report_skill_progress, stage_label
from .registry_client import AgentRegistryClient
from .skills.manifest import SkillManifest
from .state import (
    PreloadDeclinedError,
    emit_plan_constructed_audit,
    emit_review_completed_audit,
    emit_skill_failed_audit,
    emit_skill_invoked_audit,
    emit_skill_revoked_audit,
    preload_for_action_drafting,
    preload_for_equity_research,
    preload_for_portfolio_analysis,
    preload_for_research,
    preload_for_reviewer,
    preload_for_suitability,
    preload_spending_facts,
    write_drift_report,
    write_ips_from_interview_result,
    write_proposed_action,
    write_spending_report,
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
    "equity-research",
    "private-equity-research",
    "suitability",
    "private-suitability",
]

# Canonical clean-name order (no `private-` prefix). Used to tie-break skills
# within a scheduler layer and to emit results in a stable order, preserving the
# historical output ordering when the manifest-driven schedule replaces the
# hardcoded phases (ADR-0022 Phase 3a).
CANONICAL_SKILL_ORDER = [
    "spending-analysis",
    "goals-onboarding",
    "portfolio-analysis",
    "research",
    "action-drafting",
    "reviewer",
    "equity-research",
    "suitability",
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


def _clean_skill_name(name: str) -> str:
    """Returns the clean skill id (no path, no 'private-' prefix) — the manifest id."""
    short = _short_skill_id(name)
    return short[len("private-") :] if short.startswith("private-") else short


def _extract_prompt(node_input: Any) -> str:
    """Best-effort extraction of the user's natural-language prompt for intent
    classification (ADR-0022 Phase 3b). Never raises; returns "" when no text is
    available (in which case intent is simply 'unknown' — the safe default)."""
    if isinstance(node_input, str):
        return node_input
    if isinstance(node_input, dict):
        for key in ("message", "query", "prompt", "goal", "text"):
            val = node_input.get(key)
            if isinstance(val, str) and val.strip():
                return val
        return ""
    parts = getattr(node_input, "parts", None)
    if parts:
        return " ".join(t for t in (getattr(p, "text", None) for p in parts) if isinstance(t, str))
    return ""


def _has_active_ips(user_id: str) -> bool:
    """True if the user has an active IPS. Resilient — a Firestore hiccup returns
    False (recall-biased: onboarding is then kept, and self-skips if unneeded)."""
    try:
        return FirestoreClient().get_active_ips_by_user(user_id) is not None
    except Exception:
        logger.warning("Could not determine active IPS for %s; assuming none", user_id, exc_info=True)
        return False


def _build_decision_context(user_id: str, prompt: str) -> Dict[str, Any]:
    """Assembles the planner's decision context: deterministic state facts
    (`has_active_ips`) plus prompt-derived intent (`requested_trade`, `intent`)."""
    context: Dict[str, Any] = dict(classify_intent(prompt).as_context())
    context["has_active_ips"] = _has_active_ips(user_id)
    return context


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


async def _postprocess_spending(user_id, result, ctx, input_dict, registry_entry_id=None):
    preloaded = input_dict.get("preloaded", {}) or {}
    narrative = ""
    if isinstance(result, dict):
        narrative = result.get("narrative_summary") or result.get("summary") or ""
    elif hasattr(result, "narrative_summary"):
        narrative = getattr(result, "narrative_summary") or ""
    elif isinstance(result, str):
        narrative = result

    commentary = []
    if isinstance(result, dict):
        commentary = result.get("anomaly_commentary", []) or []
    elif hasattr(result, "anomaly_commentary"):
        commentary = getattr(result, "anomaly_commentary", []) or []

    anomalies_out = list(preloaded.get("anomalies", []))
    for i, comment in enumerate(commentary):
        if i < len(anomalies_out) and isinstance(anomalies_out[i], dict) and comment:
            anomalies_out[i] = {**anomalies_out[i], "description": comment}

    report = SpendingReport(
        user_id=preloaded.get("user_id", user_id),
        total_income_usd=float(preloaded.get("total_income_usd", 0.0)),
        total_outflow_usd=float(preloaded.get("total_outflow_usd", 0.0)),
        savings_rate=float(preloaded.get("savings_rate", 0.0)),
        reserve_months=float(preloaded.get("reserve_months", 0.0)),
        category_breakdown=preloaded.get("category_breakdown", []),
        anomalies=anomalies_out,
        narrative_summary=narrative or "Spending analysis completed based on transaction facts.",
    )
    try:
        write_spending_report(user_id=report.user_id, report=report)
    except Exception as e:
        logger.warning("Failed to persist SpendingReport for user %s: %s", user_id, e)
    payload = report.model_dump()
    return payload, {"spending_analysis_result": report}


def _build_goals_onboarding_input(user_id, input_dict, context):
    trigger = input_dict.get("trigger")
    if not trigger:
        try:
            fs = FirestoreClient()
            active_ips = fs.get_active_ips_by_user(user_id)
            if active_ips is not None:
                return None
        except Exception:
            pass
    return {"user_id": user_id, "trigger": trigger or "initial"}


async def _postprocess_goals_onboarding(user_id, result, ctx, input_dict, registry_entry_id=None):
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
            from google.adk.events import Event

            memory_event = Event(
                author="portfolio_copilot_planner",
                content=UserContent(parts=[Part.from_text(text=summary_text)]),
            )
            await ctx.add_events_to_memory(events=[memory_event])
        except Exception:
            logger.exception("add_events_to_memory failed")
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


async def _postprocess_portfolio_analysis(user_id, result, ctx, input_dict, registry_entry_id=None):
    payload = result.model_dump() if hasattr(result, "model_dump") else result
    try:
        write_drift_report(user_id=user_id, report=result)
    except Exception as e:
        logger.warning("Failed to persist DriftReport for user %s: %s", user_id, e)
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


async def _postprocess_research(user_id, result, ctx, input_dict, registry_entry_id=None):
    payload = result.model_dump() if hasattr(result, "model_dump") else result
    return payload, {"research_briefs": [payload]}


def _build_action_drafting_input(user_id, input_dict, context):
    node_input = preload_for_action_drafting(
        user_id=user_id,
        drift_report=input_dict.get("drift_report") or context.get("drift_report"),
        research_briefs=input_dict.get("research_briefs") or context.get("research_briefs"),
        requested_trade=input_dict.get("requested_trade"),
    )
    # Mirror the preloader's active IPS into input_dict so _postprocess_action_drafting
    # can stamp the ProposedAction's ips_version_referenced with the *real* active
    # IPS id/version. Without this, postprocess falls back to "ips_unknown", which
    # makes the reviewer's ips_version_current rule fail and wrongly flags an
    # otherwise-compliant trade as non-compliant. Mirrors the reviewer's build_input.
    if isinstance(node_input, dict) and node_input.get("ips") is not None:
        input_dict["ips"] = node_input.get("ips")
    return node_input


async def _postprocess_action_drafting(user_id, result, ctx, input_dict, registry_entry_id=None):
    if isinstance(result, ProposedAction):
        write_proposed_action(user_id=user_id, action=result, registry_entry_id=registry_entry_id)
        payload = result.model_dump()
        return payload, {"action_drafting_result": payload}

    pre = input_dict.get("precomputed_trade")
    if pre is None:
        # Preloader declined to produce a candidate (no drift + no
        # requested trade). Nothing to persist; return the LLM's
        # rationale as-is so the planner can surface it.
        payload = result.model_dump() if hasattr(result, "model_dump") else result
        return payload, {"action_drafting_result": payload}

    # `result` is a ProposedActionRationale. Build the full ProposedAction
    # from the deterministic precomputed trade + the LLM-authored fields.
    rationale = getattr(result, "rationale", None) or (result.get("rationale") if isinstance(result, dict) else "")
    refs = getattr(result, "supporting_research_refs", None) or (
        result.get("supporting_research_refs", []) if isinstance(result, dict) else []
    )
    ips_dict = input_dict.get("ips", {}) if isinstance(input_dict.get("ips"), dict) else {}
    ips_id = ips_dict.get("ips_id") or getattr(input_dict.get("ips"), "ips_id", "ips_unknown")
    ips_ver = ips_dict.get("version") or getattr(input_dict.get("ips"), "version", 1)

    sess = getattr(ctx, "session", None)
    sess_id = getattr(sess, "id", None)
    session_id_str = sess_id if isinstance(sess_id, str) else "sess_default"

    merged = {
        **pre,
        "action_id": pre.get("action_id") or str(uuid.uuid4()),
        "session_id": pre.get("session_id") or session_id_str,
        "type": pre.get("type") or ActionType.TRADE,
        "status": pre.get("status") or ActionStatus.DRAFTED,
        "created_at": pre.get("created_at") or datetime.now(timezone.utc),
        "ips_version_referenced": pre.get("ips_version_referenced")
        or RelatedIPSVersion(
            ips_id=str(ips_id),
            version=int(ips_ver),
        ),
        "proposed_by_skill_version": pre.get("proposed_by_skill_version")
        or SkillVersionRef(
            skill_name="private-action-drafting",
            skill_version="0.1.0",
            registry_entry_id=registry_entry_id,
        ),
        "rationale": rationale,
        "supporting_research_refs": refs,
    }
    action = ProposedAction.model_validate(merged)

    write_proposed_action(user_id=user_id, action=action, registry_entry_id=registry_entry_id)
    payload = action.model_dump()
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
        except Exception:
            logger.exception("Reviewer MA returned malformed verdict, treating as no-verdict")

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
            ips_version_checked_against=RelatedIPSVersion(ips_id=ips_obj.ips_id, version=ips_obj.version),
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


# ---------- equity-research + suitability (advisory path, issue #344) ----------

_CASHTAG_RE = re.compile(r"\$([A-Za-z]{1,5})\b")
_UPPER_TICKER_RE = re.compile(r"\b([A-Z]{2,5})\b")
# Uppercase tokens that look like tickers but are common finance acronyms.
_TICKER_STOPWORDS = frozenset(
    {"IPS", "DCF", "ETF", "CEO", "CFO", "USD", "AI", "FAQ", "PDF", "API", "US", "IRA", "SEC", "IPO", "ROE", "EPS"}
)


def _extract_ticker(prompt: str, input_dict: Dict[str, Any]) -> Optional[str]:
    """Best-effort ticker extraction for the equity-research path.

    Prefers an explicit ``ticker`` field, then a ``$CASHTAG``, then a lone
    uppercase 2-5 letter token that is not a common finance acronym. Returns
    None when nothing ticker-like is present (the skill then self-skips); a
    wrong guess is caught downstream when fundamentals can't be retrieved.
    """
    explicit = input_dict.get("ticker")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip().upper()
    text = prompt or ""
    m = _CASHTAG_RE.search(text)
    if m:
        return m.group(1).upper()
    for m in _UPPER_TICKER_RE.finditer(text):
        tok = m.group(1).upper()
        if tok not in _TICKER_STOPWORDS:
            return tok
    return None


def _build_equity_research_input(user_id, input_dict, context):
    prompt = _extract_prompt(input_dict) or _extract_prompt(context)
    ticker = _extract_ticker(prompt, input_dict)
    if not ticker:
        return None  # no identifiable ticker — skip cleanly
    node_input = preload_for_equity_research(user_id=user_id, ticker=ticker)
    # Stash the deterministic assessment so postprocess can treat it as authoritative.
    input_dict["_equity_assessment"] = node_input.get("assessment")
    return node_input


async def _postprocess_equity_research(user_id, result, ctx, input_dict, registry_entry_id=None):
    assessment = input_dict.get("_equity_assessment")
    if assessment is None:
        assessment = result.model_dump() if hasattr(result, "model_dump") else result
    payload = dict(assessment) if isinstance(assessment, dict) else assessment
    # Attach the MA's optional narrative without polluting the threaded contract.
    summary = result.get("summary") or result.get("narrative_summary") if isinstance(result, dict) else None
    if summary and isinstance(payload, dict):
        payload = {**payload, "narrative_summary": summary}
    return payload, {"equity_assessment": assessment, "equity_research_result": payload}


def _build_suitability_input(user_id, input_dict, context):
    assessment = context.get("equity_assessment") or input_dict.get("_equity_assessment")
    if not assessment:
        return None  # nothing to assess — skip (equity-research produced nothing)
    node_input = preload_for_suitability(
        user_id=user_id,
        assessment=assessment,
        drift_report=context.get("drift_report") or input_dict.get("drift_report"),
    )
    input_dict["_equity_recommendation"] = node_input.get("recommendation")
    return node_input


async def _postprocess_suitability(user_id, result, ctx, input_dict, registry_entry_id=None):
    recommendation = input_dict.get("_equity_recommendation")
    if recommendation is None:
        recommendation = result.model_dump() if hasattr(result, "model_dump") else result
    payload = dict(recommendation) if isinstance(recommendation, dict) else recommendation
    summary = result.get("summary") or result.get("rationale") if isinstance(result, dict) else None
    if summary and isinstance(payload, dict) and not payload.get("rationale"):
        payload = {**payload, "rationale": summary}
    return payload, {"equity_recommendation": recommendation, "suitability_result": payload}


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
    "private-equity-research": SkillPlan(
        short_name="private-equity-research",
        build_input=_build_equity_research_input,
        postprocess=_postprocess_equity_research,
    ),
    "private-suitability": SkillPlan(
        short_name="private-suitability",
        build_input=_build_suitability_input,
        postprocess=_postprocess_suitability,
    ),
}


def _resolve_project_location() -> tuple[str, str]:
    """Resolves the GCP project id and Agent Registry location from the environment."""
    project_id = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        try:
            _, project_id = google_auth_default()
        except Exception:
            pass
    if not project_id:
        project_id = "dummy-project"
    location = os.environ.get("AGENT_REGISTRY_LOCATION", "global")
    return project_id, location


@node(name="get_skills", rerun_on_resume=False)
async def get_skills_from_registry(ctx: Context, node_input: Any):
    """Queries the Agent Registry for available skills."""
    project_id, location = _resolve_project_location()
    logger.info(f"Goal received: {node_input}, project_id: {project_id}, location: {location}")
    client = AgentRegistryClient(project_id=project_id, location=location)
    skills = await client.list_authorized_skills()
    return skills


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
        emit_skill_failed_audit(plan.short_name, error=f"declined: {e}", registry_entry_id=registry_entry_id)
        report_skill_progress(plan.short_name, "skipped", detail=str(e))
        return {"status": "declined", "message": str(e)}
    except Exception as e:
        logger.exception("Skill %s preload failed", plan.short_name)
        emit_skill_failed_audit(
            plan.short_name,
            error=f"preload_failed: {e}",
            registry_entry_id=registry_entry_id,
        )
        report_skill_progress(plan.short_name, "failed", detail="preload failed")
        raise

    if node_input is None:
        logger.info(f"Skipping skill {plan.short_name} (no input built)")
        report_skill_progress(plan.short_name, "skipped")
        return None

    if isinstance(node_input, dict):
        if "precomputed_trade" in node_input:
            input_dict.setdefault("precomputed_trade", node_input.get("precomputed_trade"))
        if "preloaded" in node_input:
            input_dict.setdefault("preloaded", node_input.get("preloaded"))

    # 2. Emit SKILL_INVOKED (audit) and announce the stage as running (UI progress).
    emit_skill_invoked_audit(
        plan.short_name,
        detail=f"Dispatching {plan.short_name}",
        registry_entry_id=registry_entry_id,
    )
    report_skill_progress(plan.short_name, "running")

    # 3. Dispatch to Managed Agent
    t0 = time.monotonic()
    try:
        result = await dispatch_managed_skill(
            plan.short_name,
            node_input=node_input,
            ctx=ctx,
            registry_entry_id=registry_entry_id,
        )
    except Exception as e:
        logger.exception("Skill %s dispatch failed", plan.short_name)
        emit_skill_failed_audit(
            plan.short_name,
            error=f"dispatch_failed: {e}",
            registry_entry_id=registry_entry_id,
        )
        report_skill_progress(plan.short_name, "failed", detail="dispatch failed")
        raise
    finally:
        logger.info(
            "skill_dispatch_complete",
            extra={"skill": plan.short_name, "elapsed_sec": round(time.monotonic() - t0, 2)},
        )

    # 4. Postprocess (writes + rationale + context)
    try:
        payload, ctx_update = await plan.postprocess(user_id, result, ctx, input_dict, registry_entry_id)
    except Exception as e:
        logger.exception("Skill %s postprocess failed", plan.short_name)
        emit_skill_failed_audit(
            plan.short_name,
            error=f"postprocess_failed: {e}",
            registry_entry_id=registry_entry_id,
        )
        report_skill_progress(plan.short_name, "failed", detail="postprocess failed")
        raise

    context.update(ctx_update)
    report_skill_progress(plan.short_name, "done")
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
        (s.name if hasattr(s, "name") else str(s)): getattr(s, "default_revision", None) for s in current_skills
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
        except Exception:
            # Audit fail-closed raises; log and continue so a single failure doesn't
            # block detection of other revocations in the same cycle.
            logger.exception("Failed to audit revocation of %s", short_name)

    # Store current cycle for next comparison. Serialized as plain dicts so
    # ADK's ctx.state (which needs JSON-safe values) is happy.
    ctx.state["last_authorized_skills"] = [
        {"name": name, "default_revision": rev} for name, rev in current_by_name.items()
    ]


async def _load_authorized_manifests(skills: list[Any]) -> Optional[Dict[str, SkillManifest]]:
    """Fetches manifests for the authorized skills from the Agent Registry.

    Returns ``{clean_name: manifest}`` when *every* authorized skill yields a
    valid manifest, or ``None`` if any is missing or invalid. A ``None`` result
    tells the caller to fall back to the legacy hardcoded schedule — this keeps
    the planner working against registry revisions that predate ``manifest.json``
    (i.e. before the skills are re-registered), so Phase 3a is safe to deploy
    ahead of a `make register-skills`.
    """
    project_id, location = _resolve_project_location()
    client = AgentRegistryClient(project_id=project_id, location=location)

    async def _one(skill: Any) -> tuple[str, SkillManifest]:
        name = skill.name if hasattr(skill, "name") else str(skill)
        clean = _clean_skill_name(name)
        return clean, await client.get_skill_manifest(clean)

    try:
        results = await asyncio.gather(*(_one(s) for s in skills), return_exceptions=True)
    finally:
        await client.close()

    manifests: Dict[str, SkillManifest] = {}
    for r in results:
        if isinstance(r, BaseException):
            logger.warning("Manifest load failed; falling back to legacy schedule: %s", r)
            return None
        clean, manifest = r
        manifests[clean] = manifest
    return manifests


async def _execute_scheduled_layers(
    plan: Any,
    skills_by_clean: Dict[str, Any],
    manifests: Dict[str, SkillManifest],
    user_id: str,
    input_dict: Dict[str, Any],
    context: Dict[str, Any],
    ctx: Context,
) -> Dict[str, Any]:
    """Executes the computed schedule layer by layer, parallelizing within a layer.

    Returns ``{clean_name: payload}`` for every skill that ran (payload may be
    ``None`` when a skill self-skips). Layer boundaries guarantee a skill runs
    only after the producers of the artifacts it consumes, so context threading
    (drift_report → action-drafting, proposed_action → reviewer) is preserved.
    """
    payloads: Dict[str, Any] = {}
    for layer in plan.layers:
        runnable: list[tuple[str, SkillPlan, Optional[str]]] = []
        for clean in layer:
            skill_plan = SKILL_PLANS.get(_normalize_skill_key(clean))
            if skill_plan is None:
                continue
            skill_obj = skills_by_clean.get(clean)
            registry_entry_id = getattr(skill_obj, "default_revision", None) if skill_obj is not None else None
            runnable.append((clean, skill_plan, registry_entry_id))
        if not runnable:
            continue

        parallel = len(runnable) > 1 and all(
            clean in manifests and manifests[clean].parallelizable for clean, _, _ in runnable
        )
        if parallel:
            tasks = [
                _execute_skill(sp, _normalize_skill_key(clean), user_id, input_dict, context, ctx, registry_entry_id=rid)
                for clean, sp, rid in runnable
            ]
            layer_results = await asyncio.gather(*tasks, return_exceptions=True)
            errors = [r for r in layer_results if isinstance(r, Exception)]
            if errors:
                raise ExceptionGroup("parallel skill dispatch failed", errors)
            for (clean, _, _), res in zip(runnable, layer_results):
                payloads[clean] = res
        else:
            for clean, sp, rid in runnable:
                payloads[clean] = await _execute_skill(
                    sp, _normalize_skill_key(clean), user_id, input_dict, context, ctx, registry_entry_id=rid
                )
    return payloads


async def _execute_legacy_phases(
    skills: list[Any],
    user_id: str,
    input_dict: Dict[str, Any],
    context: Dict[str, Any],
    ctx: Context,
) -> list[Any]:
    """Legacy hardcoded three-phase execution (independent → parallel → dependent).

    Retained as the fallback for when manifests are unavailable from the registry
    (revisions predating ``manifest.json``). Behaviour is identical to the
    pre-ADR-0022 planner.
    """
    results: list[Any] = []
    independent_first = ("private-spending-analysis", "private-goals-onboarding")
    parallel_group = ("private-portfolio-analysis", "private-research")
    dependent_after = ("private-action-drafting", "private-reviewer")

    ordered_skills = sorted(skills, key=_skill_sort_key)

    # 1. Independent first group (sequential)
    for skill in ordered_skills:
        skill_name = skill.name if hasattr(skill, "name") else str(skill)
        short_name = _normalize_skill_key(skill_name)
        if short_name not in independent_first:
            continue
        plan = SKILL_PLANS.get(short_name)
        if plan is None:
            continue
        payload = await _execute_skill(
            plan, skill_name, user_id, input_dict, context, ctx, registry_entry_id=getattr(skill, "default_revision", None)
        )
        if payload is not None:
            results.append(f"{plan.short_name.replace('private-', '')}_result: {payload}")

    # 2. Parallel group: portfolio-analysis and research concurrent dispatch.
    # Concurrent context writes are safe (disjoint keys: portfolio_analysis_result / research_briefs).
    parallel_tasks = []
    parallel_plans = []
    for skill in ordered_skills:
        skill_name = skill.name if hasattr(skill, "name") else str(skill)
        short_name = _normalize_skill_key(skill_name)
        if short_name not in parallel_group:
            continue
        plan = SKILL_PLANS.get(short_name)
        if plan is None:
            continue
        parallel_plans.append(plan)
        parallel_tasks.append(
            _execute_skill(
                plan, skill_name, user_id, input_dict, context, ctx, registry_entry_id=getattr(skill, "default_revision", None)
            )
        )

    if parallel_tasks:
        parallel_results = await asyncio.gather(*parallel_tasks, return_exceptions=True)
        errors = [r for r in parallel_results if isinstance(r, Exception)]
        if errors:
            raise ExceptionGroup("parallel skill dispatch failed", errors)
        for plan, r in zip(parallel_plans, parallel_results):
            if r is not None:
                results.append(f"{plan.short_name.replace('private-', '')}_result: {r}")

    # 3. Dependent after group (sequential)
    for skill in ordered_skills:
        skill_name = skill.name if hasattr(skill, "name") else str(skill)
        short_name = _normalize_skill_key(skill_name)
        if short_name not in dependent_after:
            continue
        plan = SKILL_PLANS.get(short_name)
        if plan is None:
            continue
        payload = await _execute_skill(
            plan, skill_name, user_id, input_dict, context, ctx, registry_entry_id=getattr(skill, "default_revision", None)
        )
        if payload is not None:
            results.append(f"{plan.short_name.replace('private-', '')}_result: {payload}")

    return results


@node(rerun_on_resume=True)
async def root_planner(ctx: Context, node_input: Any):
    """Registry-driven dynamic planner. Iterates authorized skills in canonical order,
    dispatching each to the worker Managed Agent via a per-skill SkillPlan."""
    report_progress("discovery", "running", STAGE_LABELS["discovery"])
    all_skills = await ctx.run_node(get_skills_from_registry, node_input=node_input)
    logger.info(f"Available skills from registry: {all_skills}")

    # Filter strictly to the Portfolio Copilot skills (the 6 skills in skills/)
    skills = [s for s in all_skills if _normalize_skill_key(s.name if hasattr(s, "name") else str(s)) in SKILL_PLANS]
    logger.info(f"Filtered Portfolio Copilot skills ({len(skills)}): {skills}")
    report_progress(
        "discovery",
        "done",
        STAGE_LABELS["discovery"],
        detail=f"{len(skills)} authorized skill(s)",
    )

    # Delta-detect revocations vs the previous planning cycle in this session.
    # Emits SKILL_REVOKED audit for anything that disappeared.
    _detect_and_audit_revocations(ctx, skills)

    if not skills:
        msg = "No authorized Portfolio Copilot skills found in Agent Registry to complete the request."
        logger.warning(msg)
        return [f"error: {msg}"]

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

    user_id = (
        input_dict.get("user_id")
        or (getattr(ctx, "session", None) and getattr(ctx.session, "user_id", None))
        or getattr(ctx, "user_id", None)
        or "demo_user"
    )

    results: list[Any] = []
    context: Dict[str, Any] = {}

    # Construct the execution schedule from the skills' manifests (ADR-0022
    # Phase 3a). The three hardcoded phases become an emergent property of the
    # dependency graph. If manifests can't be sourced from the registry (e.g. a
    # revision predating manifest.json), fall back to the legacy phase order so
    # the planner keeps working — behaviour-preserving in both paths.
    manifests = await _load_authorized_manifests(skills)
    plan = None
    if manifests is not None:
        skills_by_clean = {_clean_skill_name(s.name if hasattr(s, "name") else str(s)): s for s in skills}
        # PLAN (ADR-0022 Phase 3b): read the user's intent and select the leaves.
        # v1 retrieval is list-all; the structured policy (rules + default floor)
        # narrows and augments it, recall-biased. The deterministic resolver then
        # adds prerequisites and gates. Unauthorized leaves (e.g. a floor skill
        # that isn't authorized) are dropped by resolve_and_schedule.
        prompt = _extract_prompt(node_input)
        decision_context = _build_decision_context(user_id, prompt)
        candidates = [c.id for c in DEFAULT_RETRIEVER.retrieve(prompt, manifests)]
        leaves = select_leaves(candidates, decision_context, DEFAULT_POLICY)
        try:
            plan = resolve_and_schedule(
                sorted(leaves), manifests, available_artifacts=(), canonical_order=CANONICAL_SKILL_ORDER
            )
        except Exception:
            logger.exception("Schedule computation failed; falling back to legacy phases")
            plan = None
        if plan is not None:
            emit_plan_constructed_audit(
                prompt_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12],
                candidates=candidates,
                leaves=list(leaves),
                resolved=list(plan.selected),
                layers=list(plan.layers),
                policy_applied=applied_rules(decision_context, DEFAULT_POLICY),
            )

    if plan is not None:
        # Plan pre-render (ADR-0022 §6): announce every scheduled stage as
        # "pending" up front so the UI stepper shows the whole plan before each
        # stage starts; execution then transitions each to running/done/skipped.
        for clean in plan.flat():
            report_progress(clean, "pending", stage_label(clean))
        payloads = await _execute_scheduled_layers(plan, skills_by_clean, manifests, user_id, input_dict, context, ctx)
        # Emit results in canonical order (preserving historical output ordering),
        # then any non-canonical skills after, in plan order.
        for clean in CANONICAL_SKILL_ORDER:
            payload = payloads.get(clean)
            if payload is not None:
                results.append(f"{clean}_result: {payload}")
        for clean, payload in payloads.items():
            if clean not in CANONICAL_SKILL_ORDER and payload is not None:
                results.append(f"{clean}_result: {payload}")
    else:
        results = await _execute_legacy_phases(skills, user_id, input_dict, context, ctx)

    # HITL approval gate: if action-drafting produced a ProposedAction, gate it before returning
    ad_result = context.get("action_drafting_result")
    if ad_result and isinstance(ad_result, dict) and ad_result.get("status") == "drafted":
        # ProposedAction was drafted this cycle -- run it past the human
        # Reviewer verdict may be present in context (once #106 lands); may be None until then
        gate_input = {
            "action": ad_result,
            "reviewer_verdict": context.get("reviewer_verdict"),
        }
        # The gate pauses the workflow (RequestInput) until the user responds, so
        # this "running" stage reads as "awaiting your approval" in the stepper.
        report_progress("approval", "running", STAGE_LABELS["approval"])
        try:
            hitl_result = await ctx.run_node(hitl_approval_gate, node_input=gate_input)
        except Exception as e:
            logger.exception("HITL gate failed")
            report_progress("approval", "failed", STAGE_LABELS["approval"])
            results.append(f"hitl_error: {e}")
        else:
            outcome = hitl_result.get("outcome") if isinstance(hitl_result, dict) else None
            report_progress("approval", "done", STAGE_LABELS["approval"], detail=outcome)
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
        report_progress("execution", "running", STAGE_LABELS["execution"])
        try:
            exec_result = await ctx.run_node(execution_gate, node_input=exec_input)
        except Exception as e:
            logger.exception("Execution gate raised")
            report_progress("execution", "failed", STAGE_LABELS["execution"])
            results.append(f"execution_error: {e}")
        else:
            exec_status = exec_result.get("status") if isinstance(exec_result, dict) else None
            report_progress(
                "execution",
                "skipped" if exec_status == "skipped" else "done",
                STAGE_LABELS["execution"],
                detail=exec_status,
            )
            results.append(f"execution_result: {exec_result}")
            context["execution_result"] = exec_result

    return results


root_agent = Workflow(
    name="portfolio_copilot_planner",
    description="Dynamic planner for Portfolio Copilot that queries Agent Registry to construct a plan.",
    edges=[("START", root_planner)],
)
