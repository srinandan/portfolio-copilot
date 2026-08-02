from datetime import datetime, timezone
from typing import Any

from google.adk import Context
from google.adk.events import RequestInput
from google.adk.workflow import node

from ...data.bigquery import BigQueryClient
from ...data.firestore import FirestoreClient
from .logic import calculate_reserve_months, calculate_savings_rate, is_anomalous


@node(name="spending_analysis_skill", rerun_on_resume=True)
async def spending_analysis_skill(ctx: Context, node_input: Any):
    """
    Skill for analyzing Chase transaction data via BigQuery.
    Supports query_intent: "savings_rate", "anomaly_check", or ad-hoc NL queries.
    """
    user_id = node_input.get("user_id")
    if not user_id:
        raise ValueError("user_id is required")

    query_intent = node_input.get("query_intent")
    if not query_intent:
        raise ValueError("query_intent is required")

    firestore_client = FirestoreClient()
    bq_client = BigQueryClient()

    current_month_start = datetime.now(timezone.utc).replace(day=1).strftime("%Y-%m-%d")

    if query_intent == "savings_rate":
        totals = bq_client.get_trailing_income_and_outflow(user_id, current_month_start)
        total_income = totals["total_income"]
        total_outflow = totals["total_outflow"]

        savings_rate = calculate_savings_rate(total_income, total_outflow)
        average_monthly_expenses = total_outflow / 3.0

        holdings = firestore_client.get_holdings(user_id)
        cash_usd = holdings.cash_usd if holdings and holdings.cash_usd else 0.0

        reserve_months = calculate_reserve_months(cash_usd, average_monthly_expenses)

        yield {
            "savings_rate": savings_rate,
            "reserve_months": reserve_months
        }

    elif query_intent == "anomaly_check":
        totals = bq_client.get_monthly_spending_totals(user_id, current_month_start)
        anomalies = []
        for row in totals:
            cat = row.get("normalized_category")
            curr = row.get("current_month_spend", 0.0) or 0.0
            avg = row.get("trailing_3mo_avg", 0.0) or 0.0

            if is_anomalous(curr, avg):
                anomalies.append({
                    "category": cat,
                    "current_month_spend": curr,
                    "trailing_3mo_avg": avg
                })
        yield {"anomalies": anomalies}

    else:
        is_ambiguous = node_input.get("is_ambiguous", False)
        if is_ambiguous:
            clarification = yield RequestInput(message="I'm not sure I understand your query. Could you clarify what category or date range you mean?")
            yield {"status": "clarified", "user_response": clarification}
            return

        sql_query = node_input.get("sql_query")
        if not sql_query:
            clarification = yield RequestInput(message="I couldn't map your request to a valid query. Could you rephrase it?")
            yield {"status": "clarified", "user_response": clarification}
            return

        try:
            results = bq_client.validate_and_execute_nl_sql(user_id, sql_query)
            yield {"results": results}
        except ValueError as e:
            yield {"error": str(e)}
