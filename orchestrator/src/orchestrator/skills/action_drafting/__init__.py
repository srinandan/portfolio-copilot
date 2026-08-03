"""Action drafting skill for proposing executable orders within IPS boundaries."""

import uuid
from datetime import datetime, timezone
from typing import Any

from google.adk import Context
from google.adk.workflow import node

from ...contracts import ConfidenceLevel, ResearchBrief
from ...contracts.audit_log import Actor, ActorType, AuditLogEntry, EventType
from ...contracts.ips import RelatedIPSVersion
from ...contracts.proposed_action import (
    ActionStatus,
    ActionType,
    ProposedAction,
    SkillVersionRef,
)
from ...data.firestore import FirestoreClient
from ...logger import get_logger
from .._skill_metadata import read_skill_version
from .logic import calculate_draft_action

logger = get_logger(__name__)

SKILL_VERSION = read_skill_version("action-drafting")


@node(name="action_drafting_skill", rerun_on_resume=True)
async def action_drafting_skill(ctx: Context, node_input: Any):
    """Drafts a specific proposed trade based on drift report and research context.

    Returns a list of ProposedActions, which may be empty if no action is warranted.
    """
    user_id = node_input.get("user_id") if isinstance(node_input, dict) else None
    if not user_id:
        raise ValueError("user_id is required")

    drift_report = node_input.get("drift_report") if isinstance(node_input, dict) else None
    raw_briefs = node_input.get("research_briefs") if isinstance(node_input, dict) else None
    requested_trade = node_input.get("requested_trade") if isinstance(node_input, dict) else None

    # Merge requested_trade into drift_report dict if passed at top level
    if requested_trade:
        drift_dict = drift_report.model_dump() if hasattr(drift_report, "model_dump") else (drift_report or {})
        drift_dict["requested_trade"] = requested_trade
        drift_report = drift_dict

    db_client = FirestoreClient()
    now = datetime.now(timezone.utc)

    # 1. Audit log: Skill invoked (Fail closed per I3)
    try:
        db_client.append_audit_log(
            AuditLogEntry(
                log_id=str(uuid.uuid4()),
                event_type=EventType.SKILL_INVOKED,
                timestamp=now,
                actor=Actor(
                    type=ActorType.AGENT,
                    skill_name="private-action-drafting",
                    skill_version=SKILL_VERSION,
                ),
                detail=f"Action drafting invoked for user {user_id}",
            )
        )
    except Exception as audit_err:
        logger.error(f"Failed to append audit log for skill invocation: {audit_err}")
        raise RuntimeError(f"Audit log write failed for skill invocation: {audit_err}") from audit_err

    # 2. Fetch active IPS
    ips_id = node_input.get("ips_id") if isinstance(node_input, dict) else None
    if ips_id:
        ips = db_client.get_active_ips(ips_id)
    else:
        ips = db_client.get_active_ips_by_user(user_id)

    if not ips:
        raise ValueError(f"No active IPS found for user: {user_id}")

    # 3. Fetch holdings
    holdings = db_client.get_holdings(user_id)
    if not holdings:
        raise ValueError(f"No holdings found for user_id: {user_id}")

    try:
        trade_details = calculate_draft_action(drift_report, holdings, ips)
    except ValueError as e:
        logger.error(f"Action drafting failed constraints check: {e}")
        try:
            db_client.append_audit_log(
                AuditLogEntry(
                    log_id=str(uuid.uuid4()),
                    event_type=EventType.SKILL_INVOCATION_FAILED,
                    timestamp=datetime.now(timezone.utc),
                    actor=Actor(
                        type=ActorType.AGENT,
                        skill_name="private-action-drafting",
                        skill_version=SKILL_VERSION,
                    ),
                    detail=f"Drafting blocked by constraints: {e}",
                )
            )
        except Exception as audit_err:
            logger.error(f"Failed to append audit log: {audit_err}")
        raise

    if not trade_details:
        return []

    # 4. Build rationale, adding research context if any (D4)
    rationale = trade_details["rationale"]
    supporting_research_refs = []

    # Normalize research_briefs to a list
    briefs_list = []
    if isinstance(raw_briefs, list):
        briefs_list = raw_briefs
    elif isinstance(raw_briefs, (dict, ResearchBrief)):
        briefs_list = [raw_briefs]

    has_low_confidence = False
    for brief in briefs_list:
        if isinstance(brief, ResearchBrief):
            if brief.research_run_id:
                supporting_research_refs.append(brief.research_run_id)
            if brief.confidence == ConfidenceLevel.LOW:
                has_low_confidence = True
        elif isinstance(brief, dict):
            run_id = brief.get("research_run_id") or brief.get("research_run_ids")
            if isinstance(run_id, list):
                supporting_research_refs.extend(run_id)
            elif isinstance(run_id, str):
                supporting_research_refs.append(run_id)
            conf = brief.get("confidence")
            if conf in (ConfidenceLevel.LOW, "low"):
                has_low_confidence = True

    if briefs_list:
        if has_low_confidence:
            rationale += " Note: Supporting research confidence was low."
    else:
        rationale += " Note: No research briefs were provided."

    action = ProposedAction(
        action_id=str(uuid.uuid4()),
        session_id=node_input.get("session_id", "default_session") if isinstance(node_input, dict) else "default_session",
        type=ActionType.TRADE,
        ticker=trade_details["ticker"],
        side=trade_details["side"],
        quantity=trade_details["quantity"],
        order_type=trade_details["order_type"],
        estimated_price_usd=trade_details["estimated_price_usd"],
        estimated_value_usd=trade_details["estimated_value_usd"],
        rationale=rationale,
        supporting_research_refs=supporting_research_refs,
        ips_version_referenced=RelatedIPSVersion(ips_id=ips.ips_id, version=ips.version),
        proposed_by_skill_version=SkillVersionRef(skill_name="private-action-drafting", skill_version=SKILL_VERSION),
        status=ActionStatus.DRAFTED,
        created_at=now,
    )

    # 5. Audit log: Action proposed (Fail closed per I3)
    try:
        db_client.append_audit_log(
            AuditLogEntry(
                log_id=str(uuid.uuid4()),
                event_type=EventType.ACTION_PROPOSED,
                timestamp=now,
                actor=Actor(
                    type=ActorType.AGENT,
                    skill_name="private-action-drafting",
                    skill_version=SKILL_VERSION,
                ),
                detail=f"Proposed {action.side.value} {action.quantity} {action.ticker}",
                related_action_id=action.action_id,
                related_ips_version={"ips_id": ips.ips_id, "version": ips.version},
            )
        )
    except Exception as audit_err:
        logger.error(f"Failed to append audit log for proposed action: {audit_err}")
        raise RuntimeError(f"Audit log write failed for proposed action: {audit_err}") from audit_err

    return [action.model_dump()]
