"""State preloaders for the Managed Agents dispatch path.

Each preloader fetches all read-only state a skill needs and pre-computes
any derived deterministic values, producing a single input payload for the
worker Managed Agent to reason over. No writes happen here — writes are the
orchestrator's job after the Managed Agent returns.
"""

from typing import Any, Dict, List, Optional

from ..contracts.proposed_action import ProposedAction
from ..data.firestore import FirestoreClient
from ..logger import get_logger
from ..primitives.action_drafting import calculate_draft_action
from ..primitives.portfolio_analysis import calculate_drift

logger = get_logger(__name__)


class PreloadDeclinedError(Exception):
    """Raised when a preloader cannot proceed because required state is missing
    (e.g. no active IPS, no holdings). Callers should surface this as a
    skill-declined result rather than a hard error."""


def preload_for_portfolio_analysis(
    user_id: str,
    firestore_client: Optional[FirestoreClient] = None,
) -> Dict[str, Any]:
    """Pre-fetches IPS + holdings and pre-computes DriftReport.

    Raises:
        PreloadDeclinedError: if no active IPS or holdings for the user.
    """
    fs = firestore_client or FirestoreClient()
    ips = fs.get_active_ips_by_user(user_id)
    if not ips:
        raise PreloadDeclinedError(
            f"No active IPS found for user {user_id}; complete goals onboarding first."
        )
    holdings = fs.get_holdings(user_id)
    if not holdings:
        raise PreloadDeclinedError(f"No holdings found for user {user_id}.")

    drift_report = calculate_drift(holdings, ips)
    return {
        "user_id": user_id,
        "ips": ips.model_dump(),
        "holdings": holdings.model_dump(),
        "drift_report": drift_report.model_dump(),
    }


def preload_for_action_drafting(
    user_id: str,
    drift_report: Optional[Dict[str, Any]] = None,
    research_briefs: Optional[List[Any]] = None,
    requested_trade: Optional[Dict[str, Any]] = None,
    firestore_client: Optional[FirestoreClient] = None,
) -> Dict[str, Any]:
    """Pre-fetches IPS + holdings, threads in upstream context, pre-computes
    a candidate trade via calculate_draft_action.

    drift_report / research_briefs / requested_trade come from the planner's
    context dict (populated by earlier skill invocations in the same session).

    Raises:
        PreloadDeclinedError: if no active IPS or holdings.
        ValueError: if calculate_draft_action raises a constraint violation
            (excluded ticker/sector/concentration). Callers should re-raise
            and let the orchestrator emit a SKILL_INVOCATION_FAILED audit entry.
    """
    fs = firestore_client or FirestoreClient()
    ips = fs.get_active_ips_by_user(user_id)
    if not ips:
        raise PreloadDeclinedError(f"No active IPS found for user {user_id}.")
    holdings = fs.get_holdings(user_id)
    if not holdings:
        raise PreloadDeclinedError(f"No holdings found for user {user_id}.")

    # Compose drift_report_input for calculate_draft_action:
    # - if requested_trade given, wrap as {"requested_trade": ...}
    # - else use drift_report from upstream
    drift_input: Dict[str, Any] = dict(drift_report or {})
    if requested_trade:
        drift_input["requested_trade"] = requested_trade

    precomputed_trade = calculate_draft_action(drift_input, holdings, ips)

    return {
        "user_id": user_id,
        "ips": ips.model_dump(),
        "holdings": holdings.model_dump(),
        "drift_report": drift_report,
        "research_briefs": [
            b.model_dump() if hasattr(b, "model_dump") else b for b in (research_briefs or [])
        ],
        "requested_trade": requested_trade,
        "precomputed_trade": precomputed_trade.model_dump() if hasattr(precomputed_trade, "model_dump") and precomputed_trade is not None else precomputed_trade,
    }


def preload_for_research(user_id: str, research_question: str) -> Dict[str, Any]:
    """Validates research inputs. The research skill has strict data isolation
    (SKILL.md acceptance criterion 1) — no Firestore/BigQuery reads happen here.

    Raises:
        ValueError: if research_question is empty.
    """
    if not research_question or not research_question.strip():
        raise ValueError("research_question is required for research preloader")
    return {
        "user_id": user_id,
        "research_question": research_question.strip(),
    }


def preload_for_reviewer(
    user_id: str,
    action: Dict[str, Any] | ProposedAction,
    firestore_client: Optional[FirestoreClient] = None,
) -> Dict[str, Any]:
    """Pre-fetches active IPS + holdings for the reviewer skill.

    The `action` is the drafted ProposedAction (from context, populated by
    action-drafting's postprocess). Passed through as-is to the Managed
    Agent input.

    Raises:
        PreloadDeclinedError: if no active IPS or holdings.
        ValueError: if action is missing or invalid.
    """
    if action is None:
        raise ValueError("preload_for_reviewer requires 'action' from prior action-drafting step")

    fs = firestore_client or FirestoreClient()
    ips = fs.get_active_ips_by_user(user_id)
    if not ips:
        raise PreloadDeclinedError(f"No active IPS found for user {user_id}.")
    holdings = fs.get_holdings(user_id)
    if not holdings:
        raise PreloadDeclinedError(f"No holdings found for user {user_id}.")

    action_dict = action.model_dump() if hasattr(action, "model_dump") else dict(action)

    return {
        "user_id": user_id,
        "action": action_dict,
        "ips": ips.model_dump(),
        "holdings": holdings.model_dump(),
    }
