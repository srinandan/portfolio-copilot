from typing import Any

from google.adk import Context
from google.adk.workflow import node

from ...data.firestore import FirestoreClient
from .logic import calculate_drift


@node(name="portfolio_analysis_skill", rerun_on_resume=True)
async def portfolio_analysis_skill(ctx: Context, node_input: Any):
    """
    Skill for analyzing portfolio drift against the active IPS.
    """
    user_id = node_input.get("user_id")
    if not user_id:
        raise ValueError("user_id is required")

    firestore_client = FirestoreClient()

    ips = firestore_client.get_active_ips_by_user(user_id)
    if not ips:
        yield {"status": "declined", "message": "No active Investment Policy Statement (IPS) found for the user. Please complete goals onboarding first."}
        return

    holdings = firestore_client.get_holdings(user_id)
    if not holdings:
        yield {"status": "error", "message": "No holdings found for the user."}
        return

    drift_report = calculate_drift(holdings, ips)

    yield {
        "status": "completed",
        "drift_report": drift_report.model_dump()
    }
