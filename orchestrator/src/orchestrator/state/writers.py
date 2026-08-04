"""Orchestrator state write operations and transactional updates."""

import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

from ..contracts.audit_log import Actor, ActorType, AuditLogEntry, EventType
from ..contracts.goals_onboarding import GoalsOnboardingResult
from ..contracts.ips import Constraints, InvestmentPolicyStatement, IPSStatus, LiquidityNeeds
from ..contracts.liabilities import LiabilitiesSnapshot
from ..contracts.proposed_action import ProposedAction
from ..contracts.reviewer_verdict import ReviewerVerdict
from ..data.firestore import FirestoreClient
from ..logger import get_logger
from ..skills._skill_metadata import read_skill_approval_scope, read_skill_version

logger = get_logger(__name__)


def write_ips_from_interview_result(
    user_id: str,
    result: GoalsOnboardingResult,
    trigger: str = "initial",
    existing_ips_ref: Optional[str] = None,
    registry_entry_id: Optional[str] = None,
    db_client: Optional[FirestoreClient] = None,
) -> Tuple[InvestmentPolicyStatement, LiabilitiesSnapshot]:
    """Persists synthesized goals onboarding interview results to Firestore.

    1. Determines whether creating version 1 or superseding version N.
    2. Writes the active InvestmentPolicyStatement.
    3. Overwrites the current LiabilitiesSnapshot.
    4. Records an authoritative audit log entry (IPS_CREATED or IPS_SUPERSEDED).
    """
    client = db_client or FirestoreClient()
    now = datetime.now(timezone.utc)

    existing_ips = None
    if existing_ips_ref:
        existing_ips = client.get_active_ips(existing_ips_ref)
    elif trigger in ("life_event", "drift_review"):
        existing_ips = client.get_active_ips_by_user(user_id)

    if existing_ips:
        ips_id = existing_ips.ips_id
        version = existing_ips.version + 1
        event_type = EventType.IPS_SUPERSEDED
    else:
        ips_id = str(uuid.uuid4())
        version = 1
        event_type = EventType.IPS_CREATED

    goals = []
    if result.primary_goal:
        goals.append(result.primary_goal)
    if result.additional_goals:
        goals.extend(result.additional_goals)

    new_ips = InvestmentPolicyStatement(
        ips_id=ips_id,
        user_id=user_id,
        version=version,
        status=IPSStatus.ACTIVE,
        effective_date=now.strftime("%Y-%m-%d"),
        risk_tolerance=result.risk_tolerance,
        time_horizon_years=result.time_horizon_years,
        goals=goals,
        liquidity_needs=result.liquidity_needs or LiquidityNeeds(),
        target_allocation=result.target_allocation,
        constraints=result.constraints or Constraints(concentration_limit_percent=15.0),
        rebalancing_rules=result.rebalancing_rules,
        created_at=now,
    )

    client.update_ips(new_ips)
    logger.info(f"Persisted IPS {ips_id} (version {version}) for user {user_id}")

    liab_snapshot = LiabilitiesSnapshot(
        user_id=user_id,
        as_of=now,
        liabilities=result.identified_liabilities,
    )
    client.set_liabilities(user_id, liab_snapshot)
    logger.info(f"Persisted {len(result.identified_liabilities)} liabilities for user {user_id}")

    skill_version = read_skill_version("goals-onboarding")
    approval_scope = read_skill_approval_scope("goals-onboarding")
    audit_entry = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        event_type=event_type,
        timestamp=now,
        actor=Actor(
            type=ActorType.AGENT,
            skill_name="private-goals-onboarding",
            skill_version=skill_version,
            registry_entry_id=registry_entry_id,
            approval_scope=approval_scope,
        ),
        detail=f"IPS {ips_id} version {version} written from goals onboarding interview.",
    )
    try:
        client.append_audit_log(audit_entry)
    except Exception as e:
        logger.error(f"Failed to append audit log for IPS creation: {e}")
        raise RuntimeError(f"Audit log write failed for IPS creation: {e}") from e

    return new_ips, liab_snapshot


def write_proposed_action(
    user_id: str,
    action: ProposedAction,
    registry_entry_id: Optional[str] = None,
    db_client: Optional[FirestoreClient] = None,
) -> ProposedAction:
    """Persists a drafted ProposedAction and emits an ACTION_PROPOSED audit entry.

    Called by the orchestrator after the action-drafting Managed Agent returns
    a validated ProposedAction. The MA does not have Firestore write access.
    """
    client = db_client or FirestoreClient()
    client.set_proposed_action(action)
    logger.info(f"Persisted ProposedAction {action.action_id} for user {user_id}")

    skill_version = read_skill_version("action-drafting")
    approval_scope = read_skill_approval_scope("action-drafting")
    audit_entry = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        event_type=EventType.ACTION_PROPOSED,
        timestamp=datetime.now(timezone.utc),
        actor=Actor(
            type=ActorType.AGENT,
            skill_name="private-action-drafting",
            skill_version=skill_version,
            registry_entry_id=registry_entry_id,
            approval_scope=approval_scope,
        ),
        related_action_id=action.action_id,
        related_ips_version=action.ips_version_referenced.model_dump(),
        detail=f"Proposed {action.side.value} {action.quantity} {action.ticker}",
    )
    try:
        client.append_audit_log(audit_entry)
    except Exception as e:
        logger.error(f"Failed to append audit log for ProposedAction {action.action_id}: {e}")
        raise RuntimeError(f"Audit log write failed for ProposedAction: {e}") from e

    return action


def emit_review_completed_audit(
    action: ProposedAction,
    authoritative_verdict: ReviewerVerdict,
    llm_verdict: Optional[ReviewerVerdict] = None,
    registry_entry_id: Optional[str] = None,
    db_client: Optional[FirestoreClient] = None,
) -> None:
    """Emits REVIEW_COMPLETED. Fail-closed.

    `authoritative_verdict` is the orchestrator's deterministic re-check output
    (what the HITL and execution gates enforce). `llm_verdict` is the Managed
    Agent's advisory output — captured for audit, never enforced.

    Divergence (LLM says pass, deterministic says fail — or vice versa) is
    captured in the audit entry's `detail` field so post-hoc auditing can find
    prompt-injection or model-drift incidents.
    """
    from ..skills._skill_metadata import read_skill_approval_scope

    client = db_client or FirestoreClient()
    skill_version = read_skill_version("reviewer")
    approval_scope = read_skill_approval_scope("reviewer")

    divergence: Optional[str] = None
    if llm_verdict is not None:
        if llm_verdict.overall_pass != authoritative_verdict.overall_pass:
            divergence = (
                f"LLM verdict overall_pass={llm_verdict.overall_pass} "
                f"disagreed with deterministic re-check overall_pass={authoritative_verdict.overall_pass}"
            )
        else:
            llm_fails = {r.rule_id for r in llm_verdict.rule_results if not r.passed}
            det_fails = {r.rule_id for r in authoritative_verdict.rule_results if not r.passed}
            if llm_fails != det_fails:
                divergence = (
                    f"LLM failing rules {sorted(llm_fails)} != deterministic failing rules {sorted(det_fails)}"
                )

    pass_summary = (
        "all rules passed"
        if authoritative_verdict.overall_pass
        else f"failed rules: {sorted(r.rule_id for r in authoritative_verdict.rule_results if not r.passed)}"
    )
    detail = f"Reviewer completed for {action.action_id}: {pass_summary}"
    if divergence:
        detail += f" | LLM/deterministic divergence: {divergence}"

    audit_entry = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        event_type=EventType.REVIEW_COMPLETED,
        timestamp=datetime.now(timezone.utc),
        actor=Actor(
            type=ActorType.AGENT,
            skill_name="private-reviewer",
            skill_version=skill_version,
            registry_entry_id=registry_entry_id,
            approval_scope=approval_scope,
        ),
        related_action_id=action.action_id,
        related_ips_version=action.ips_version_referenced.model_dump() if hasattr(action.ips_version_referenced, "model_dump") else action.ips_version_referenced,
        detail=detail,
    )
    try:
        client.append_audit_log(audit_entry)
    except Exception as e:
        logger.error(f"Failed to append REVIEW_COMPLETED audit for {action.action_id}: {e}")
        raise RuntimeError(f"Audit log write failed for review completion: {e}") from e


def emit_skill_invoked_audit(
    skill_short_name: str,
    detail: Optional[str] = None,
    registry_entry_id: Optional[str] = None,
    db_client: Optional[FirestoreClient] = None,
) -> None:
    """Emits a SKILL_INVOKED audit entry for a skill turn. Fail-closed.

    Called by the dispatcher at the start of each Managed Agent invocation.
    """
    client = db_client or FirestoreClient()
    skill_dir_name = skill_short_name.replace("private-", "")
    skill_version = read_skill_version(skill_dir_name)
    approval_scope = read_skill_approval_scope(skill_dir_name)
    audit_entry = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        event_type=EventType.SKILL_INVOKED,
        timestamp=datetime.now(timezone.utc),
        actor=Actor(
            type=ActorType.AGENT,
            skill_name=skill_short_name if skill_short_name.startswith("private-") else f"private-{skill_short_name}",
            skill_version=skill_version,
            registry_entry_id=registry_entry_id,
            approval_scope=approval_scope,
        ),
        detail=detail,
    )
    try:
        client.append_audit_log(audit_entry)
    except Exception as e:
        logger.error(f"Failed to append SKILL_INVOKED audit for {skill_short_name}: {e}")
        raise RuntimeError(f"Audit log write failed for skill invocation: {e}") from e


def emit_skill_failed_audit(
    skill_short_name: str,
    error: str,
    registry_entry_id: Optional[str] = None,
    db_client: Optional[FirestoreClient] = None,
) -> None:
    """Emits a SKILL_INVOCATION_FAILED audit entry. Fail-closed.

    Called by the dispatcher when a Managed Agent invocation or its
    validation fails.
    """
    client = db_client or FirestoreClient()
    skill_dir_name = skill_short_name.replace("private-", "")
    skill_version = read_skill_version(skill_dir_name)
    approval_scope = read_skill_approval_scope(skill_dir_name)
    audit_entry = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        event_type=EventType.SKILL_INVOCATION_FAILED,
        timestamp=datetime.now(timezone.utc),
        actor=Actor(
            type=ActorType.AGENT,
            skill_name=skill_short_name if skill_short_name.startswith("private-") else f"private-{skill_short_name}",
            skill_version=skill_version,
            registry_entry_id=registry_entry_id,
            approval_scope=approval_scope,
        ),
        detail=f"Skill invocation failed: {error}",
    )
    try:
        client.append_audit_log(audit_entry)
    except Exception as e:
        logger.error(f"Failed to append SKILL_INVOCATION_FAILED audit for {skill_short_name}: {e}")
        raise RuntimeError(f"Audit log write failed for skill failure: {e}") from e


def emit_skill_revoked_audit(
    revoked_skill_short_name: str,
    prior_registry_entry_id: Optional[str] = None,
    detail: Optional[str] = None,
    db_client: Optional[FirestoreClient] = None,
) -> None:
    """Emits SKILL_REVOKED when the planner detects a skill that was authorized
    last planning cycle but isn't authorized this cycle. Fail-closed.

    The registry_entry_id passed here is the *prior* revision — the one that
    was active before revocation. This lets an auditor trace "what was revoked
    and when" precisely.

    detail should describe what triggered the revocation observation (e.g.
    "detected on planning cycle for session {sess_id}").
    """
    client = db_client or FirestoreClient()
    skill_dir_name = revoked_skill_short_name.replace("private-", "")
    skill_version = read_skill_version(skill_dir_name)
    approval_scope = read_skill_approval_scope(skill_dir_name)
    audit_entry = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        event_type=EventType.SKILL_REVOKED,
        timestamp=datetime.now(timezone.utc),
        actor=Actor(
            type=ActorType.AGENT,
            skill_name=(
                revoked_skill_short_name
                if revoked_skill_short_name.startswith("private-")
                else f"private-{revoked_skill_short_name}"
            ),
            skill_version=skill_version,
            registry_entry_id=prior_registry_entry_id,
            approval_scope=approval_scope,
        ),
        detail=detail or f"Skill {revoked_skill_short_name} observed as revoked at planning cycle",
    )
    try:
        client.append_audit_log(audit_entry)
    except Exception as e:
        logger.error(f"Failed to append SKILL_REVOKED audit for {revoked_skill_short_name}: {e}")
        raise RuntimeError(f"Audit log write failed for skill revocation: {e}") from e


def emit_approval_requested_audit(
    action: ProposedAction,
    reviewer_verdict_id: Optional[str] = None,
    db_client: Optional[FirestoreClient] = None,
) -> None:
    """Emits APPROVAL_REQUESTED right before the gate yields RequestInput. Fail-closed."""
    client = db_client or FirestoreClient()
    audit_entry = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        event_type=EventType.APPROVAL_REQUESTED,
        timestamp=datetime.now(timezone.utc),
        actor=Actor(
            type=ActorType.AGENT,
            skill_name="orchestrator-hitl-gate",
            skill_version="0.1.0",
            registry_entry_id=None,
            approval_scope=None,
        ),
        related_action_id=action.action_id,
        related_ips_version=action.ips_version_referenced.model_dump(),
        detail=f"Approval requested for {action.side.value} {action.quantity} {action.ticker}"
               + (f" (reviewer_verdict={reviewer_verdict_id})" if reviewer_verdict_id else " (no reviewer verdict available)"),
    )
    try:
        client.append_audit_log(audit_entry)
    except Exception as e:
        logger.error(f"Failed to append APPROVAL_REQUESTED audit for {action.action_id}: {e}")
        raise RuntimeError(f"Audit log write failed for approval request: {e}") from e


def emit_approval_granted_audit(
    action: ProposedAction,
    approving_user_id: str,
    edit_rounds: int = 0,
    db_client: Optional[FirestoreClient] = None,
) -> None:
    """Emits APPROVAL_GRANTED after human approve. Fail-closed."""
    client = db_client or FirestoreClient()
    audit_entry = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        event_type=EventType.APPROVAL_GRANTED,
        timestamp=datetime.now(timezone.utc),
        actor=Actor(
            type=ActorType.HUMAN,
            user_id=approving_user_id,
        ),
        related_action_id=action.action_id,
        related_ips_version=action.ips_version_referenced.model_dump(),
        detail=f"Human approved {action.side.value} {action.quantity} {action.ticker}"
               + (f" after {edit_rounds} edit round(s)" if edit_rounds else ""),
    )
    try:
        client.append_audit_log(audit_entry)
    except Exception as e:
        logger.error(f"Failed to append APPROVAL_GRANTED audit for {action.action_id}: {e}")
        raise RuntimeError(f"Audit log write failed for approval grant: {e}") from e


def emit_approval_rejected_audit(
    action: ProposedAction,
    reason: str,
    rejecting_user_id: Optional[str] = None,
    db_client: Optional[FirestoreClient] = None,
) -> None:
    """Emits APPROVAL_REJECTED after human reject (or edit-limit exceeded). Fail-closed."""
    client = db_client or FirestoreClient()
    audit_entry = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        event_type=EventType.APPROVAL_REJECTED,
        timestamp=datetime.now(timezone.utc),
        actor=Actor(
            type=ActorType.HUMAN if rejecting_user_id else ActorType.AGENT,
            user_id=rejecting_user_id,
            skill_name=None if rejecting_user_id else "orchestrator-hitl-gate",
            skill_version=None if rejecting_user_id else "0.1.0",
            registry_entry_id=None,
            approval_scope=None,
        ),
        related_action_id=action.action_id,
        related_ips_version=action.ips_version_referenced.model_dump(),
        detail=f"Rejected: {reason}",
    )
    try:
        client.append_audit_log(audit_entry)
    except Exception as e:
        logger.error(f"Failed to append APPROVAL_REJECTED audit for {action.action_id}: {e}")
        raise RuntimeError(f"Audit log write failed for approval rejection: {e}") from e


def emit_action_executed_audit(
    action: ProposedAction,
    broker_order_id: str,
    executing_user_id: Optional[str] = None,
    db_client: Optional[FirestoreClient] = None,
) -> None:
    """Emits ACTION_EXECUTED after successful Alpaca submission. Fail-closed."""
    client = db_client or FirestoreClient()
    audit_entry = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        event_type=EventType.ACTION_EXECUTED,
        timestamp=datetime.now(timezone.utc),
        actor=Actor(
            type=ActorType.AGENT,
            skill_name="orchestrator-execution-gate",
            skill_version="0.1.0",
            registry_entry_id=None,
            approval_scope=None,
        ),
        related_action_id=action.action_id,
        related_ips_version=action.ips_version_referenced.model_dump(),
        detail=(
            f"Alpaca accepted {action.side.value} {action.quantity} {action.ticker} "
            f"(broker_order_id={broker_order_id}, approved_by={executing_user_id or 'unknown'})"
        ),
    )
    try:
        client.append_audit_log(audit_entry)
    except Exception as e:
        logger.error(f"Failed to append ACTION_EXECUTED audit for {action.action_id}: {e}")
        raise RuntimeError(f"Audit log write failed for action execution: {e}") from e


def emit_action_failed_audit(
    action: ProposedAction,
    error: str,
    db_client: Optional[FirestoreClient] = None,
) -> None:
    """Emits ACTION_FAILED when Alpaca rejects the order or the executor errors. Fail-closed."""
    client = db_client or FirestoreClient()
    audit_entry = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        event_type=EventType.ACTION_FAILED,
        timestamp=datetime.now(timezone.utc),
        actor=Actor(
            type=ActorType.AGENT,
            skill_name="orchestrator-execution-gate",
            skill_version="0.1.0",
            registry_entry_id=None,
            approval_scope=None,
        ),
        related_action_id=action.action_id,
        related_ips_version=action.ips_version_referenced.model_dump(),
        detail=f"Execution failed: {error}",
    )
    try:
        client.append_audit_log(audit_entry)
    except Exception as e:
        logger.error(f"Failed to append ACTION_FAILED audit for {action.action_id}: {e}")
        raise RuntimeError(f"Audit log write failed for action failure: {e}") from e

