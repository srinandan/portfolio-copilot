import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from google.adk import Context
from google.adk.workflow import node

from ...contracts.audit_log import Actor, ActorType, AuditLogEntry, EventType
from ...contracts.ips import RelatedIPSVersion
from ...contracts.proposed_action import (
    ActionStatus,
    ActionType,
    OrderType,
    ProposedAction,
    Side,
    SkillVersionRef,
)
from ...data.firestore import FirestoreClient
from ...logger import get_logger
from .logic import calculate_draft_action

logger = get_logger(__name__)


def _load_skill_version() -> str:
    # Look for SKILL.md in the original repo structure
    # skills/action-drafting/SKILL.md
    current_file = Path(__file__).resolve()
    # orchestrator/src/orchestrator/skills/action_drafting/__init__.py
    root = current_file.parents[5]
    candidate = root / "skills" / "action-drafting" / "SKILL.md"
    if candidate.exists():
        content = candidate.read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                parsed = yaml.safe_load(parts[1])
                if isinstance(parsed, dict) and "metadata" in parsed and "version" in parsed["metadata"]:
                    return str(parsed["metadata"]["version"])

    # Fallback for testing
    return "0.1.0"


SKILL_VERSION = _load_skill_version()


@node(name="action_drafting_skill", rerun_on_resume=True)
async def action_drafting_skill(ctx: Context, node_input: Any):
    """
    Drafts a specific proposed trade based on drift report.
    Returns a list of ProposedActions, which may be empty.
    """
    user_id = node_input.get("user_id")
    if not user_id:
        raise ValueError("user_id is required")

    drift_report = node_input.get("drift_report", {})
    research_briefs = node_input.get("research_briefs", {})

    db_client = FirestoreClient()

    # Audit log: skill invoked
    invoke_log = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        event_type=EventType.SKILL_INVOKED,
        timestamp=datetime.now(timezone.utc),
        actor=Actor(
            type=ActorType.AGENT,
            skill_name="private-action-drafting",
            skill_version=SKILL_VERSION,
        ),
    )
    db_client.append_audit_log(invoke_log)

    # Fetch active IPS
    ips_id = node_input.get("ips_id")
    if not ips_id:
        raise ValueError("ips_id is required in node_input to fetch IPS")

    ips = db_client.get_active_ips(ips_id)
    if not ips:
        raise ValueError(f"No active IPS found for ips_id: {ips_id}")

    # Fetch holdings
    holdings = db_client.get_holdings(user_id)
    if not holdings:
        raise ValueError(f"No holdings found for user_id: {user_id}")

    try:
        trade_details = calculate_draft_action(drift_report, holdings, ips)
    except ValueError as e:
        # Re-raise the exception, the orchestrator should handle it (or let it fail)
        logger.error(f"Action drafting failed constraints check: {e}")

        failed_log = AuditLogEntry(
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
        db_client.append_audit_log(failed_log)
        raise

    if not trade_details:
        return []

    # Build rationale, adding research context if any
    rationale = trade_details["rationale"]
    supporting_research_refs = []

    if research_briefs:
        # e.g., if there's a list of research run IDs
        if "research_run_ids" in research_briefs:
            supporting_research_refs = research_briefs["research_run_ids"]

        if research_briefs.get("confidence") == "low":
            rationale += " Note: Supporting research confidence was low."
    else:
        rationale += " Note: No research briefs were provided."

    now = datetime.now(timezone.utc)

    action = ProposedAction(
        action_id=str(uuid.uuid4()),
        session_id=node_input.get("session_id", "default_session"),
        type=ActionType.TRADE,
        ticker=trade_details["ticker"],
        side=Side(trade_details["side"]),
        quantity=trade_details["quantity"],
        order_type=OrderType(trade_details["order_type"]),
        estimated_price_usd=trade_details["estimated_price_usd"],
        estimated_value_usd=trade_details["estimated_value_usd"],
        rationale=rationale,
        supporting_research_refs=supporting_research_refs,
        ips_version_referenced=RelatedIPSVersion(ips_id=ips.ips_id, version=ips.version),
        proposed_by_skill_version=SkillVersionRef(skill_name="private-action-drafting", skill_version=SKILL_VERSION),
        status=ActionStatus.DRAFTED,
        created_at=now,
    )

    # Audit log: action drafted
    completion_log = AuditLogEntry(
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
    db_client.append_audit_log(completion_log)

    return [action.model_dump()]
