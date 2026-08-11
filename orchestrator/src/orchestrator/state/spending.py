import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..contracts.spending_analysis import CategorySpending, SpendingAnomaly
from ..data.bigquery import BigQueryClient
from ..data.firestore import FirestoreClient
from ..logger import get_logger
from ..primitives.spending_analysis import (
    calculate_reserve_months,
    calculate_savings_rate,
    is_anomalous,
)

logger = get_logger(__name__)


def preload_spending_facts(
    user_id: str,
    window_months: int = 3,
    bq_client: Optional[BigQueryClient] = None,
    firestore_client: Optional[FirestoreClient] = None,
) -> Dict[str, Any]:
    """Deterministically queries BigQuery and Firestore to precompute spending facts for the Managed Agent."""
    t0 = time.monotonic()
    bq = bq_client or BigQueryClient()
    fs = firestore_client or FirestoreClient()
    current_month_start = datetime.now(timezone.utc).replace(day=1).strftime("%Y-%m-%d")
    valid_window = int(window_months) if isinstance(window_months, (int, float)) and window_months > 0 else 3

    totals, spending_totals = bq.get_spending_snapshot(user_id, current_month_start, window_months=valid_window)
    total_income = float(totals.get("total_income", 0.0) or 0.0)
    total_outflow = float(totals.get("total_outflow", 0.0) or 0.0)
    savings_rate = calculate_savings_rate(total_income, total_outflow)

    holdings = fs.get_holdings(user_id)
    cash_usd = float(holdings.cash_usd) if holdings and holdings.cash_usd else 0.0

    avg_monthly_expenses = (total_outflow / float(valid_window)) if total_outflow > 0 else 0.0
    reserve_months = calculate_reserve_months(cash_usd, avg_monthly_expenses)

    anomalies = []
    category_breakdown = []

    for row in spending_totals:
        cat = row.get("normalized_category") or "other"
        curr = float(row.get("current_month_spend", 0.0) or 0.0)
        avg = float(row.get("trailing_3mo_avg", 0.0) or 0.0)
        pct = (curr / total_outflow * 100.0) if total_outflow > 0 else 0.0

        category_breakdown.append(CategorySpending(category=cat, amount_usd=curr, percentage=pct))

        if is_anomalous(curr, avg):
            anomalies.append(
                SpendingAnomaly(
                    category=cat,
                    current_spend_usd=curr,
                    trailing_avg_usd=avg,
                    description=f"Spending in '{cat}' surged from 3-month average ${avg:.2f} to ${curr:.2f}.",
                )
            )

    elapsed_sec = round(time.monotonic() - t0, 2)
    logger.info(
        f"Preloaded spending facts for {user_id}: income=${total_income}, outflow=${total_outflow}, "
        f"savings_rate={savings_rate:.2%}, reserve_months={reserve_months:.1f}, anomalies={len(anomalies)}"
    )
    logger.info(
        "spending_preload_complete",
        extra={"user_id": user_id, "elapsed_sec": elapsed_sec, "anomalies": len(anomalies)},
    )

    return {
        "user_id": user_id,
        "window_months": int(valid_window),
        "total_income_usd": total_income,
        "total_outflow_usd": total_outflow,
        "savings_rate": savings_rate,
        "reserve_months": reserve_months,
        "category_breakdown": [c.model_dump() for c in category_breakdown],
        "anomalies": [a.model_dump() for a in anomalies],
    }
