from orchestrator.logger import get_logger

logger = get_logger(__name__)

import uuid
import json
from datetime import datetime, timezone
from typing import Any, Dict

from google.adk import Context
from google.adk.events import RequestInput
from google.adk.workflow import node
from google.genai.types import UserContent, Part

from ...data.firestore import FirestoreClient
from ...contracts.ips import (
    InvestmentPolicyStatement,
    IPSStatus,
    RiskTolerance,
    Goal,
    LiquidityNeeds,
    TargetAllocation,
    Constraints
)
from ...contracts.liabilities import LiabilitiesSnapshot, Liability, LiabilityType
from ...contracts.audit_log import AuditLogEntry, EventType, Actor, ActorType
from .logic import calculate_risk_tolerance, get_default_allocation_bands


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
    goals_response = yield RequestInput(message="What are your primary financial goals? (e.g. name, target amount in USD, target date like YYYY-MM-DD)")
    # For a real implementation, we would use an LLM or structured form to parse this.
    # For now, we assume the UI/Action passes a structured payload or we mock a parsed response.
    # We will simulate parsed extraction:
    goals = []
    if isinstance(goals_response, dict) and "goals" in goals_response:
        for g in goals_response["goals"]:
            goals.append(Goal(name=g["name"], target_amount_usd=g["target_amount_usd"], target_date=g["target_date"]))
    else:
        # Fallback dummy for testing
        goals.append(Goal(name="Retirement", target_amount_usd=1000000, target_date="2045-01-01"))

    # 2. Gather Risk Tolerance inputs
    risk_response = yield RequestInput(message="What is your time horizon (in years) for your primary goal? And how would you react to a 20% drop in your portfolio ('sell', 'hold', 'buy_more')?")
    time_horizon = 10
    drawdown_reaction = "hold"
    if isinstance(risk_response, dict):
        time_horizon = risk_response.get("time_horizon", time_horizon)
        drawdown_reaction = risk_response.get("drawdown_reaction", drawdown_reaction)

    risk_tolerance = calculate_risk_tolerance(time_horizon, drawdown_reaction)

    # 3. Gather Liabilities
    # Note: If it was a drift_review or life_event we'd pass back the existing liabilities here,
    # but for simplicity we ask for them or take structured input.
    liabilities_response = yield RequestInput(message="What are your current debts? (mortgage, credit cards, auto loans, etc. Include balance and minimum payments)")
    liabilities = []
    if isinstance(liabilities_response, dict) and "liabilities" in liabilities_response:
        for l in liabilities_response["liabilities"]:
            liabilities.append(Liability(
                liability_id=l.get("liability_id", str(uuid.uuid4())),
                type=LiabilityType(l["type"]),
                description=l.get("description"),
                balance_usd=l["balance_usd"],
                interest_rate_percent=l.get("interest_rate_percent"),
                minimum_payment_usd=l["minimum_payment_usd"]
            ))

    # 4. Gather Liquidity Needs
    # TODO(P1): Derive reserve_months / savings rate from BigQuery Spending Analysis instead of asking directly
    liquidity_response = yield RequestInput(message="How many months of living expenses do you keep in reserve, and do you have any known upcoming major expenses (USD)?")
    reserve_months = 6.0
    known_expenses = 0.0
    if isinstance(liquidity_response, dict):
        reserve_months = liquidity_response.get("reserve_months", reserve_months)
        known_expenses = liquidity_response.get("known_upcoming_expenses_usd", known_expenses)

    # Calculate default allocation bands based on the derived risk tolerance
    bands = get_default_allocation_bands(risk_tolerance)

    # 5. Confirm Allocation Bands and finalize
    confirm_response = yield RequestInput(
        message=f"Based on your risk tolerance ({risk_tolerance.value}), we propose these allocation bands: {[b.model_dump() for b in bands]}. "
                "Do you want to override these bands or set constraints? Provide confirmation."
    )

    # If the user overrides bands in the response:
    if isinstance(confirm_response, dict) and "overridden_bands" in confirm_response:
        bands = [TargetAllocation(**b) for b in confirm_response["overridden_bands"]]

    constraints = Constraints(concentration_limit_percent=15)
    if isinstance(confirm_response, dict) and "constraints" in confirm_response:
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
        actor=Actor(type=ActorType.AGENT, skill_name="private-goals-onboarding", skill_version="0.2.0")
    )
    db_client.append_audit_log(invoke_log)

    # 1. Run the multi-turn interview
    interview_data = await ctx.run_node(goals_onboarding_interview, node_input=node_input)

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
            known_upcoming_expenses_usd=interview_data["known_upcoming_expenses_usd"]
        ),
        target_allocation=interview_data["target_allocation"],
        constraints=interview_data["constraints"],
        created_at=now
    )

    # Transactional dual-write via FirestoreClient
    db_client.update_ips(new_ips)

    # Write Liabilities Snapshot
    liab_snapshot = LiabilitiesSnapshot(
        user_id=user_id,
        as_of=now,
        liabilities=interview_data["liabilities"]
    )
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
        actor=Actor(type=ActorType.AGENT, skill_name="private-goals-onboarding", skill_version="0.2.0"),
        detail=f"IPS {ips_id} version {next_version} written."
    )
    db_client.append_audit_log(completion_log)

    yield {"status": "completed", "ips_id": ips_id, "version": next_version}
