from orchestrator.logger import get_logger

logger = get_logger(__name__)

import uuid
from datetime import datetime, timezone
from typing import Any

from google.adk import Context
from google.adk.events import RequestInput
from google.adk.workflow import node
from google.genai.types import Part, UserContent

from ...contracts.audit_log import Actor, ActorType, AuditLogEntry, EventType
from ...contracts.ips import (
    Constraints,
    Goal,
    InvestmentPolicyStatement,
    IPSStatus,
    LiquidityNeeds,
    TargetAllocation,
)
from ...contracts.liabilities import LiabilitiesSnapshot, Liability, LiabilityType
from ...data.firestore import FirestoreClient
from .._skill_metadata import read_skill_version
from .logic import calculate_risk_tolerance, get_default_allocation_bands

SKILL_VERSION = read_skill_version("goals-onboarding")


@node(name="goals_onboarding_interview", rerun_on_resume=False)
async def goals_onboarding_interview(ctx: Context, node_input: Any):
    """
    Orchestrates the multi-turn interview to gather Goals, Risk Tolerance,
    and Liabilities, returning the gathered data. State is not saved to Firestore
    until the final confirmation.
    """
    trigger = node_input.get("trigger", "initial")
    user_id = node_input.get("user_id")

    # 1. Gather Goals
    goals_response = yield RequestInput(
        message="What are your primary financial goals? (e.g. name, target amount in USD, target date like YYYY-MM-DD)"
    )
    if goals_response is None:
        return
    if not (isinstance(goals_response, dict) and "goals" in goals_response and goals_response["goals"]):
        raise ValueError("onboarding interview: missing required field(s) in goals")

    goals = []
    for g in goals_response["goals"]:
        goals.append(Goal(name=g["name"], target_amount_usd=g["target_amount_usd"], target_date=g["target_date"]))

    # 2. Gather Risk Tolerance inputs
    risk_response = yield RequestInput(
        message="What is your time horizon (in years) for your primary goal? And how would you react to a 20% drop in your portfolio ('sell', 'hold', 'buy_more')?"
    )
    if risk_response is None:
        return
    if not (
        isinstance(risk_response, dict) and "time_horizon" in risk_response and "drawdown_reaction" in risk_response
    ):
        raise ValueError("onboarding interview: missing required field(s) in risk_tolerance")

    time_horizon = risk_response["time_horizon"]
    drawdown_reaction = risk_response["drawdown_reaction"]
    risk_tolerance = calculate_risk_tolerance(time_horizon, drawdown_reaction)

    # 3. Gather Liabilities
    liabilities_response = yield RequestInput(
        message="What are your current debts? (mortgage, credit cards, auto loans, etc. Include balance and minimum payments)"
    )
    if liabilities_response is None:
        return
    if not (isinstance(liabilities_response, dict) and "liabilities" in liabilities_response):
        raise ValueError("onboarding interview: missing required field(s) in liabilities")

    liabilities = []
    for l_item in liabilities_response["liabilities"]:
        liabilities.append(
            Liability(
                liability_id=l_item.get("liability_id", str(uuid.uuid4())),
                type=LiabilityType(l_item["type"]),
                description=l_item.get("description"),
                balance_usd=l_item["balance_usd"],
                interest_rate_percent=l_item.get("interest_rate_percent"),
                minimum_payment_usd=l_item["minimum_payment_usd"],
            )
        )

    # 4. Gather Liquidity Needs
    # TODO(P1): Derive reserve_months / savings rate from BigQuery Spending Analysis instead of asking directly
    liquidity_response = yield RequestInput(
        message="How many months of living expenses do you keep in reserve, and do you have any known upcoming major expenses (USD)?"
    )
    if liquidity_response is None:
        return
    if not (isinstance(liquidity_response, dict) and "reserve_months" in liquidity_response):
        raise ValueError("onboarding interview: missing required field(s) in liquidity_needs")

    reserve_months = liquidity_response["reserve_months"]
    known_expenses = liquidity_response.get("known_upcoming_expenses_usd", 0.0)

    # Calculate default allocation bands based on the derived risk tolerance
    bands = get_default_allocation_bands(risk_tolerance)

    # 5. Confirm Allocation Bands and finalize
    confirm_response = yield RequestInput(
        message=f"Based on your risk tolerance ({risk_tolerance.value}), we propose these allocation bands: {[b.model_dump() for b in bands]}. "
        "Do you want to override these bands or set constraints? Provide confirmation."
    )
    if confirm_response is None:
        return
    if not isinstance(confirm_response, dict):
        raise ValueError("onboarding interview: missing required field(s) in confirmation")

    # If the user overrides bands in the response:
    if "overridden_bands" in confirm_response:
        bands = [TargetAllocation(**b) for b in confirm_response["overridden_bands"]]

    constraints = Constraints(concentration_limit_percent=15)
    if "constraints" in confirm_response:
        constraints = Constraints(**confirm_response["constraints"])

    yield {
        "user_id": user_id,
        "trigger": trigger,
        "goals": goals,
        "risk_tolerance": risk_tolerance,
        "time_horizon_years": time_horizon,
        "liabilities": liabilities,
        "reserve_months": reserve_months,
        "known_upcoming_expenses_usd": known_expenses,
        "target_allocation": bands,
        "constraints": constraints,
    }


@node(name="goals_onboarding_skill", rerun_on_resume=True)
async def goals_onboarding_skill(ctx: Context, node_input: Any):
    """
    The main workflow for the goals-onboarding skill.
    Runs the interview, then writes to Firestore and emits an audit log.
    If the interview is abandoned (e.g. session drops before completion),
    no writes occur.
    """
    user_id = node_input.get("user_id")
    if not user_id:
        raise ValueError("user_id is required")

    trigger = node_input.get("trigger", "initial")

    db_client = FirestoreClient()

    # Audit log: skill invoked
    invoke_log = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        event_type=EventType.SKILL_INVOKED,
        timestamp=datetime.now(timezone.utc),
        actor=Actor(type=ActorType.AGENT, skill_name="private-goals-onboarding", skill_version=SKILL_VERSION),
    )
    db_client.append_audit_log(invoke_log)

    # 1. Run the multi-turn interview
    try:
        interview_data = await ctx.run_node(goals_onboarding_interview, node_input=node_input)
    except Exception as e:
        failed_log = AuditLogEntry(
            log_id=str(uuid.uuid4()),
            event_type=EventType.SKILL_INVOCATION_FAILED,
            timestamp=datetime.now(timezone.utc),
            actor=Actor(type=ActorType.AGENT, skill_name="private-goals-onboarding", skill_version=SKILL_VERSION),
            detail=f"Interview failed or abandoned: {e}",
        )
        db_client.append_audit_log(failed_log)
        raise

    if interview_data is None:
        return

    # 2. Persist to Firestore
    # Retrieve existing IPS to get the stable ips_id and next version number
    existing_ips = None
    if trigger in ("life_event", "drift_review"):
        # We need the existing active IPS for this user.
        # In a real system, the caller might pass the ips_id.
        # For our simple demo, we query it.
        # But wait, FirestoreClient.get_active_ips takes an ips_id.
        # The schema doesn't explicitly link user_id -> ips_id directly outside of the IPS document itself.
        # Let's assume node_input provides existing_ips_ref if applicable.
        existing_ips_id = node_input.get("existing_ips_ref")
        if existing_ips_id:
            existing_ips = db_client.get_active_ips(existing_ips_id)

    if existing_ips:
        ips_id = existing_ips.ips_id
        next_version = existing_ips.version + 1
        event_type = EventType.IPS_SUPERSEDED
    else:
        ips_id = str(uuid.uuid4())
        next_version = 1
        event_type = EventType.IPS_CREATED

    now = datetime.now(timezone.utc)

    new_ips = InvestmentPolicyStatement(
        ips_id=ips_id,
        user_id=user_id,
        version=next_version,
        status=IPSStatus.ACTIVE,
        effective_date=now.strftime("%Y-%m-%d"),
        risk_tolerance=interview_data["risk_tolerance"],
        time_horizon_years=interview_data["time_horizon_years"],
        goals=interview_data["goals"],
        liquidity_needs=LiquidityNeeds(
            reserve_months=interview_data["reserve_months"],
            known_upcoming_expenses_usd=interview_data["known_upcoming_expenses_usd"],
        ),
        target_allocation=interview_data["target_allocation"],
        constraints=interview_data["constraints"],
        created_at=now,
    )

    # Transactional dual-write via FirestoreClient
    db_client.update_ips(new_ips)

    # Write Liabilities Snapshot
    liab_snapshot = LiabilitiesSnapshot(user_id=user_id, as_of=now, liabilities=interview_data["liabilities"])
    db_client.set_liabilities(user_id, liab_snapshot)

    # Summary to memory bank
    try:
        summary_text = f"User {user_id} completed goals onboarding. Risk tolerance: {new_ips.risk_tolerance.value}. Primary horizon: {new_ips.time_horizon_years} years."
        fact = UserContent(parts=[Part.from_text(text=summary_text)])
        await ctx.add_events_to_memory(events=[fact])
    except Exception as e:
        logger.warning(f"add_events_to_memory failed (expected if not implemented fully): {e}")

    # Audit log: IPS created/superseded
    completion_log = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        event_type=event_type,
        timestamp=now,
        actor=Actor(type=ActorType.AGENT, skill_name="private-goals-onboarding", skill_version=SKILL_VERSION),
        detail=f"IPS {ips_id} version {next_version} written.",
    )
    db_client.append_audit_log(completion_log)

    yield {"status": "completed", "ips_id": ips_id, "version": next_version}
