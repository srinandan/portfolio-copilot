"""Orchestrator state write operations and transactional updates."""

import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

from ..contracts.audit_log import Actor, ActorType, AuditLogEntry, EventType
from ..contracts.goals_onboarding import GoalsOnboardingResult
from ..contracts.ips import Constraints, InvestmentPolicyStatement, IPSStatus, LiquidityNeeds
from ..contracts.liabilities import LiabilitiesSnapshot
from ..data.firestore import FirestoreClient
from ..logger import get_logger
from ..skills._skill_metadata import read_skill_version

logger = get_logger(__name__)


def write_ips_from_interview_result(
    user_id: str,
    result: GoalsOnboardingResult,
    trigger: str = "initial",
    existing_ips_ref: Optional[str] = None,
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
    audit_entry = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        event_type=event_type,
        timestamp=now,
        actor=Actor(
            type=ActorType.AGENT,
            skill_name="private-goals-onboarding",
            skill_version=skill_version,
        ),
        detail=f"IPS {ips_id} version {version} written from goals onboarding interview.",
    )
    try:
        client.append_audit_log(audit_entry)
    except Exception as e:
        logger.error(f"Failed to append audit log for IPS creation: {e}")
        raise RuntimeError(f"Audit log write failed for IPS creation: {e}") from e

    return new_ips, liab_snapshot
