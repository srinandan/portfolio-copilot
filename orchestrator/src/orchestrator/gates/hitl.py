"""Human-in-the-Loop approval gate.

Sits between action-drafting (produces ProposedAction) and Alpaca execution (#23).
Owns the pause-for-human contract: emit APPROVAL_REQUESTED -> yield RequestInput ->
wait for response -> apply decision (approve / edit / reject) -> emit outcome audit
-> update stored ProposedAction status -> return HITLDecision.

Owned by the orchestrator per ADR-0005 (HITL never delegated) and ADR-0014
(state writes never delegated).
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from google.adk import Context
from google.adk.events import RequestInput
from google.adk.workflow import node

from ..contracts.hitl_decision import HITLDecision, HITLOutcome
from ..contracts.proposed_action import ActionStatus, ProposedAction
from ..contracts.reviewer_verdict import ReviewerVerdict
from ..data.firestore import FirestoreClient
from ..logger import get_logger
from ..state.writers import (
    emit_approval_granted_audit,
    emit_approval_rejected_audit,
    emit_approval_requested_audit,
)

logger = get_logger(__name__)

MAX_EDIT_ROUNDS = 3
"""Safety limit on edit-round cycles. Beyond this the gate auto-rejects with
`reason='edit_limit_exceeded'` to prevent an infinite ping-pong."""


def _build_request_payload(
    action: ProposedAction,
    verdict: Optional[ReviewerVerdict],
    edit_round: int,
) -> Dict[str, Any]:
    """Structured payload the frontend U4 approval card consumes.

    Wire Format Contract:
        Because ADK's RequestInput.message requires a string (Optional[str]),
        this dictionary is serialized to a JSON string via json.dumps(payload, default=str)
        before being yielded in RequestInput(message=...).
        Frontend clients (and tests) consuming the RequestInput.message string MUST parse
        it with JSON.parse (or json.loads in Python) to access the underlying dictionary:
        {
            "kind": "hitl_approval_request",
            "action": <ProposedAction dict>,
            "reviewer_verdict": <ReviewerVerdict dict | None>,
            "edit_round": <int>,
            "max_edit_rounds": <int>,
            "allowed_decisions": ["approve", "edit", "reject"]
        }

    Deliberately dict-not-prose: the frontend renders a card, not a chat bubble.
    Verdict is optional so the gate works before #106 (Reviewer) lands.
    """
    return {
        "kind": "hitl_approval_request",
        "action": action.model_dump(),
        "reviewer_verdict": verdict.model_dump() if verdict else None,
        "edit_round": edit_round,
        "max_edit_rounds": MAX_EDIT_ROUNDS,
        "allowed_decisions": ["approve", "edit", "reject"],
    }


def _apply_edit(action: ProposedAction, changes: Dict[str, Any]) -> ProposedAction:
    """Applies user-provided field overrides to a ProposedAction.

    Only the whitelisted fields below can be edited by the user. Everything else
    (action_id, ips_version_referenced, proposed_by_skill_version, created_at)
    is immutable -- editing those would break audit provenance.
    """
    EDITABLE_FIELDS = {
        "quantity",
        "order_type",
        "limit_price_usd",
        "estimated_price_usd",
        "estimated_value_usd",
        "rationale",
    }
    invalid = set(changes.keys()) - EDITABLE_FIELDS
    if invalid:
        raise ValueError(
            f"Cannot edit fields {sorted(invalid)}; only {sorted(EDITABLE_FIELDS)} are user-editable."
        )

    updated = action.model_copy(update=changes)
    return updated


def _extract_from_obj(obj: Any) -> Any:
    if isinstance(obj, dict) and "payload" in obj:
        return obj["payload"]
    if isinstance(obj, dict) and "decision" in obj:
        return obj
    if isinstance(obj, str):
        try:
            parsed = json.loads(obj)
            if isinstance(parsed, dict) and "decision" in parsed:
                return parsed
        except Exception:
            pass
        return obj
    if hasattr(obj, "parts") and obj.parts:
        for p in obj.parts:
            if getattr(p, "function_response", None) and getattr(
                p.function_response, "response", None
            ):
                res = _extract_from_obj(p.function_response.response)
                if res is not None:
                    return res
            if getattr(p, "text", None):
                res = _extract_from_obj(p.text)
                if res is not None and isinstance(res, dict) and "decision" in res:
                    return res
    return None


def _extract_resume_response(ctx: Context, node_input: Any) -> Any:
    """Extracts the HITL resume decision from either direct dict, ADK event envelope, or session events."""
    res = _extract_from_obj(node_input)
    if res is not None:
        return res
    if ctx.session and hasattr(ctx.session, "events") and ctx.session.events:
        recent_events = list(ctx.session.events)[-50:]
        for e in reversed(recent_events):
            if hasattr(e, "content") and e.content:
                res = _extract_from_obj(e.content)
                if res is not None:
                    return res
    return None


@node(name="hitl_approval_gate", rerun_on_resume=True)
async def hitl_approval_gate(ctx: Context, node_input: Any):
    """Pauses the workflow for human approval of a ProposedAction.

    node_input shape:
      {
        "action": ProposedAction | dict,
        "reviewer_verdict": ReviewerVerdict | dict | None,
      }

    Returns: HITLDecision (as model_dump dict -- outer planner will keep as-is
    or coerce).
    """
    db_client = FirestoreClient()

    # 1. Check if we are resuming with a user decision
    if ctx.state.get("hitl_action"):
        # We are resuming from a RequestInput
        response = _extract_resume_response(ctx, node_input)
        if not isinstance(response, dict) or "decision" not in response:
            raise ValueError(
                f"HITL response must be a dict with 'decision' key; got {response}"
            )

        raw_saved = ctx.state.get("hitl_action")
        if not raw_saved:
            raise ValueError("No saved ProposedAction in state during HITL resume")
        current_action = ProposedAction.model_validate(raw_saved)
        edit_rounds = ctx.state.get("hitl_edit_rounds", 0)

        decision = response.get("decision")
        user_id = response.get("user_id")

        if decision == "approve":
            db_client.update_proposed_action_status(
                current_action.action_id, ActionStatus.APPROVED
            )
            emit_approval_granted_audit(
                current_action,
                approving_user_id=user_id or "unknown",
                edit_rounds=edit_rounds,
                db_client=db_client,
            )
            ctx.state["hitl_action"] = None
            yield HITLDecision(
                outcome=HITLOutcome.APPROVED,
                action=current_action,
                edit_rounds=edit_rounds,
                approved_at=datetime.now(timezone.utc),
                approving_user_id=user_id,
            ).model_dump()
            return

        if decision == "reject":
            reason = response.get("reason", "no reason provided")
            db_client.update_proposed_action_status(
                current_action.action_id, ActionStatus.REJECTED
            )
            emit_approval_rejected_audit(
                current_action,
                reason=reason,
                rejecting_user_id=user_id,
                db_client=db_client,
            )
            ctx.state["hitl_action"] = None
            yield HITLDecision(
                outcome=HITLOutcome.REJECTED,
                action=current_action,
                reason=reason,
                edit_rounds=edit_rounds,
                approved_at=datetime.now(timezone.utc),
                approving_user_id=user_id,
            ).model_dump()
            return

        if decision == "edit":
            changes = response.get("changes") or {}
            try:
                current_action = _apply_edit(current_action, changes)
            except ValueError as e:
                logger.warning(f"Edit rejected: {e}")
                emit_approval_rejected_audit(
                    current_action,
                    reason=f"invalid_edit: {e}",
                    rejecting_user_id=user_id,
                    db_client=db_client,
                )
                db_client.update_proposed_action_status(
                    current_action.action_id, ActionStatus.REJECTED
                )
                ctx.state["hitl_action"] = None
                yield HITLDecision(
                    outcome=HITLOutcome.REJECTED,
                    action=current_action,
                    reason=f"invalid_edit: {e}",
                    edit_rounds=edit_rounds,
                    approved_at=datetime.now(timezone.utc),
                    approving_user_id=user_id,
                ).model_dump()
                return

            db_client.set_proposed_action(current_action)
            edit_rounds += 1
            ctx.state["hitl_action"] = current_action.model_dump()
            ctx.state["hitl_edit_rounds"] = edit_rounds

            if edit_rounds >= MAX_EDIT_ROUNDS:
                db_client.update_proposed_action_status(
                    current_action.action_id, ActionStatus.REJECTED
                )
                emit_approval_rejected_audit(
                    current_action,
                    reason="edit_limit_exceeded",
                    rejecting_user_id=user_id,
                    db_client=db_client,
                )
                ctx.state["hitl_action"] = None
                yield HITLDecision(
                    outcome=HITLOutcome.REJECTED,
                    action=current_action,
                    reason="edit_limit_exceeded",
                    edit_rounds=edit_rounds,
                    approved_at=datetime.now(timezone.utc),
                    approving_user_id=user_id,
                ).model_dump()
                return

            # Emit APPROVAL_REQUESTED again for the edited action and yield RequestInput
            raw_verdict = ctx.state.get("hitl_verdict")
            verdict = (
                ReviewerVerdict.model_validate(raw_verdict) if raw_verdict else None
            )
            emit_approval_requested_audit(
                current_action,
                reviewer_verdict_id=verdict.verdict_id if verdict else None,
                db_client=db_client,
            )
            payload = _build_request_payload(current_action, verdict, edit_rounds)
            yield RequestInput(message=json.dumps(payload, default=str))
            return

        raise ValueError(f"Unknown decision '{decision}'; expected approve|edit|reject")

    # 2. Initial run -- parse new action
    raw_input = node_input
    if hasattr(node_input, "parts") and node_input.parts:
        part = node_input.parts[0]
        raw_input = getattr(part, "text", None) or part
    if isinstance(raw_input, str):
        try:
            raw_input = json.loads(raw_input)
        except Exception:
            pass
    if not isinstance(raw_input, dict):
        raw_input = {}

    raw_action = raw_input.get("action")
    if raw_action is None:
        raise ValueError("hitl_approval_gate requires 'action' in node_input")
    action = (
        raw_action
        if isinstance(raw_action, ProposedAction)
        else ProposedAction.model_validate(raw_action)
    )

    raw_verdict = raw_input.get("reviewer_verdict")
    verdict: Optional[ReviewerVerdict] = None
    if raw_verdict is not None:
        verdict = (
            raw_verdict
            if isinstance(raw_verdict, ReviewerVerdict)
            else ReviewerVerdict.model_validate(raw_verdict)
        )

    # Save initial state across resumes
    ctx.state["hitl_action"] = action.model_dump()
    ctx.state["hitl_verdict"] = verdict.model_dump() if verdict else None
    ctx.state["hitl_edit_rounds"] = 0

    emit_approval_requested_audit(
        action,
        reviewer_verdict_id=verdict.verdict_id if verdict else None,
        db_client=db_client,
    )

    payload = _build_request_payload(action, verdict, 0)
    yield RequestInput(message=json.dumps(payload, default=str))
    return
