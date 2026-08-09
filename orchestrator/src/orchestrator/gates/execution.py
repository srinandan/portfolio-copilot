"""Post-HITL execution gate.

Reads `context["hitl_decision"]` and `context["reviewer_verdict"]` and, if both
conditions are met, executes the ProposedAction against Alpaca's paper-trading
API. Owned by trusted orchestrator code per ADR-0005 — the Managed Agent
sandbox never sees Alpaca write credentials.

Behavior matrix:
  HITL outcome | Reviewer verdict | Action
  -------------|------------------|--------
  approved     | pass             | execute
  approved     | absent/revoked   | refuse, emit ACTION_FAILED ("reviewer_verdict_missing_or_reviewer_revoked")
  approved     | fail             | refuse, emit ACTION_FAILED ("reviewer_verdict_failed")
  rejected     | (any)            | skip silently (already audited by HITL gate)
  missing      | (any)            | skip silently (nothing was drafted or gated)
"""

import os
from typing import Any, Dict, Optional

from google.adk import Context
from google.adk.workflow import node

from ..contracts.hitl_decision import HITLOutcome
from ..contracts.proposed_action import ActionStatus, ProposedAction
from ..contracts.reviewer_verdict import ReviewerVerdict
from ..data.firestore import FirestoreClient
from ..executors.alpaca import AlpacaExecutionError, AlpacaExecutor, ExecutionResult
from ..logger import get_logger
from ..state.writers import emit_action_executed_audit, emit_action_failed_audit

logger = get_logger(__name__)


def _extract_hitl(context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw = context.get("hitl_decision")
    if not isinstance(raw, dict):
        return None
    return raw


def _extract_verdict(context: Dict[str, Any]) -> Optional[ReviewerVerdict]:
    raw = context.get("reviewer_verdict")
    if raw is None:
        return None
    if isinstance(raw, ReviewerVerdict):
        return raw
    if isinstance(raw, dict):
        return ReviewerVerdict.model_validate(raw)
    return None


def _is_reviewer_authorized(ctx: Optional[Context]) -> bool:
    if ctx is None or not hasattr(ctx, "state") or ctx.state is None:
        return False
    authorized_list = ctx.state.get("last_authorized_skills")
    if not isinstance(authorized_list, list):
        return False
    for item in authorized_list:
        if isinstance(item, dict):
            name = item.get("name", "")
        else:
            name = str(item)
        short_name = name.split("/")[-1] if "/" in name else name
        if short_name in ("reviewer", "private-reviewer"):
            return True
    return False


@node(name="execution_gate", rerun_on_resume=False)
async def execution_gate(ctx: Context, node_input: Any):
    """Reads HITL decision + reviewer verdict from node_input.

    node_input shape:
      {
        "hitl_decision": {...HITLDecision.model_dump()...},
        "reviewer_verdict": {...ReviewerVerdict.model_dump()...} | None,
        "executor": AlpacaExecutor  # optional; test DI hook, else fresh instance
      }

    Returns a dict:
      {"status": "executed" | "skipped" | "failed",
       "broker_order_id": str | None,
       "action_id": str | None,
       "reason": str | None}
    """
    if not isinstance(node_input, dict):
        return {
            "status": "skipped",
            "action_id": None,
            "broker_order_id": None,
            "reason": "no execution context provided",
        }

    hitl = _extract_hitl(node_input)
    if hitl is None:
        logger.info("Execution gate: no HITL decision in context; skipping.")
        return {
            "status": "skipped",
            "action_id": None,
            "broker_order_id": None,
            "reason": "no_hitl_decision",
        }

    outcome = hitl.get("outcome")
    if outcome != HITLOutcome.APPROVED:
        logger.info(f"Execution gate: HITL outcome '{outcome}' is not approved; skipping.")
        return {
            "status": "skipped",
            "action_id": hitl.get("action", {}).get("action_id") if isinstance(hitl.get("action"), dict) else getattr(hitl.get("action"), "action_id", None),
            "broker_order_id": None,
            "reason": f"hitl_{outcome}",
        }

    raw_action = hitl.get("action")
    if not raw_action:
        logger.error("Execution gate: HITL decision has no 'action'; skipping.")
        return {
            "status": "skipped",
            "action_id": None,
            "broker_order_id": None,
            "reason": "hitl_decision_missing_action",
        }
    action = (
        raw_action
        if isinstance(raw_action, ProposedAction)
        else ProposedAction.model_validate(raw_action)
    )

    verdict = _extract_verdict(node_input)
    admin_bypass = os.environ.get("PORTFOLIO_COPILOT_ADMIN_BYPASS_REVIEWER", "").lower() == "true"

    if verdict is None:
        if admin_bypass:
            logger.warning(
                f"Execution gate: reviewer verdict absent for {action.action_id}, but PORTFOLIO_COPILOT_ADMIN_BYPASS_REVIEWER=true; allowing execution."
            )
        else:
            if not _is_reviewer_authorized(ctx):
                logger.warning(
                    f"Execution gate: reviewer skill 'private-reviewer' not authorized in registry for {action.action_id}; refusing execution."
                )
            else:
                logger.warning(
                    f"Execution gate: reviewer verdict missing for {action.action_id} (LLM crash or no verdict produced); refusing execution."
                )
            db_client = FirestoreClient()
            db_client.update_proposed_action_status(action.action_id, ActionStatus.FAILED)
            emit_action_failed_audit(
                action,
                error="reviewer_verdict_missing_or_reviewer_revoked",
                db_client=db_client,
            )
            return {
                "status": "failed",
                "action_id": action.action_id,
                "broker_order_id": None,
                "reason": "reviewer_verdict_missing_or_reviewer_revoked",
            }

    if verdict is not None and not verdict.overall_pass:
        logger.warning(
            f"Execution gate: reviewer verdict failed for {action.action_id}; refusing execution."
        )
        db_client = FirestoreClient()
        db_client.update_proposed_action_status(action.action_id, ActionStatus.FAILED)
        emit_action_failed_audit(
            action,
            error="reviewer_verdict_failed",
            db_client=db_client,
        )
        return {
            "status": "failed",
            "action_id": action.action_id,
            "broker_order_id": None,
            "reason": "reviewer_verdict_failed",
        }

    # Execute
    executor: AlpacaExecutor = node_input.get("executor") or AlpacaExecutor()
    db_client = FirestoreClient()
    try:
        result: ExecutionResult = executor.submit_order(action)
    except AlpacaExecutionError as e:
        logger.error(f"Execution gate: Alpaca submission failed for {action.action_id}: {e}")
        db_client.update_proposed_action_status(action.action_id, ActionStatus.FAILED)
        emit_action_failed_audit(action, error=str(e), db_client=db_client)
        return {
            "status": "failed",
            "action_id": action.action_id,
            "broker_order_id": None,
            "reason": str(e),
        }

    # Success path
    db_client.update_proposed_action_status(
        action.action_id,
        ActionStatus.EXECUTED,
        updated_fields={"broker_order_id": result.broker_order_id},
    )
    emit_action_executed_audit(
        action,
        broker_order_id=result.broker_order_id,
        executing_user_id=hitl.get("approving_user_id"),
        db_client=db_client,
    )
    return {
        "status": "executed",
        "action_id": action.action_id,
        "broker_order_id": result.broker_order_id,
        "reason": None,
    }
