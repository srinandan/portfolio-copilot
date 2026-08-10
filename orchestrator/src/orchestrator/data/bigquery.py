import os
import re
from typing import Any, Dict, List, Optional

from google.api_core.client_options import ClientOptions
from google.auth.transport import mtls
from google.cloud import bigquery


class BigQueryClient:
    def __init__(self, project: Optional[str] = None):
        self.project = (
            project or os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "test-project"
        )
        client_options = None
        if mtls.has_default_client_cert_source():
            client_options = ClientOptions(client_cert_source=mtls.default_client_cert_source())
        self.client = bigquery.Client(project=self.project, client_options=client_options)

    def get_monthly_spending_totals(
        self, user_id: str, current_month_start: str, window_months: int = 3
    ) -> List[Dict[str, Any]]:
        query = f"""
        WITH monthly_totals AS (
          SELECT
            normalized_category,
            DATE_TRUNC(transaction_date, MONTH) AS month,
            SUM(-amount) AS total_spend
          FROM `{self.project}.portfolio_copilot.chase_transactions`
          WHERE user_id = @user_id
            AND amount < 0
            AND transaction_date >= DATE_SUB(CAST(@current_month_start AS DATE), INTERVAL @window_months MONTH)
            AND transaction_date < DATE_ADD(CAST(@current_month_start AS DATE), INTERVAL 1 MONTH)
          GROUP BY normalized_category, month
        )
        SELECT
          normalized_category,
          SUM(IF(month = CAST(@current_month_start AS DATE), total_spend, 0)) AS current_month_spend,
          AVG(IF(month < CAST(@current_month_start AS DATE), total_spend, NULL)) AS trailing_3mo_avg
        FROM monthly_totals
        GROUP BY normalized_category
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                bigquery.ScalarQueryParameter("current_month_start", "STRING", current_month_start),
                bigquery.ScalarQueryParameter("window_months", "INT64", window_months),
            ]
        )

        query_job = self.client.query(query, job_config=job_config)
        results = query_job.result()
        return [dict(row) for row in results]

    def get_trailing_income_and_outflow(
        self, user_id: str, current_month_start: str, window_months: int = 3
    ) -> Dict[str, float]:
        query = f"""
        SELECT
            SUM(IF(amount > 0, amount, 0)) as total_income,
            SUM(IF(amount < 0, -amount, 0)) as total_outflow
        FROM `{self.project}.portfolio_copilot.chase_transactions`
        WHERE user_id = @user_id
          AND transaction_date >= DATE_SUB(CAST(@current_month_start AS DATE), INTERVAL @window_months MONTH)
          AND transaction_date < CAST(@current_month_start AS DATE)
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                bigquery.ScalarQueryParameter("current_month_start", "STRING", current_month_start),
                bigquery.ScalarQueryParameter("window_months", "INT64", window_months),
            ]
        )

        query_job = self.client.query(query, job_config=job_config)
        results = list(query_job.result())

        total_income = results[0].total_income if results and results[0].total_income else 0.0
        total_outflow = results[0].total_outflow if results and results[0].total_outflow else 0.0

        return {"total_income": float(total_income), "total_outflow": float(total_outflow)}

    def validate_and_execute_nl_sql(self, user_id: str, sql_query: str) -> List[Dict[str, Any]]:
        sql_upper = sql_query.upper()

        forbidden_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE", "MERGE"]
        for kw in forbidden_keywords:
            if re.search(r"\b" + kw + r"\b", sql_upper):
                raise ValueError(f"Write-intent SQL refused: {kw} is not allowed.")

        if "FROM" in sql_upper:
            if "CHASE_TRANSACTIONS" not in sql_upper:
                raise ValueError("Query must target the chase_transactions table.")

        if "@user_id" not in sql_query:
            raise ValueError("Query must include @user_id parameter for scoping.")

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
            ],
            maximum_bytes_billed=10 * 1024 * 1024,
        )

        query_job = self.client.query(sql_query, job_config=job_config)
        results = query_job.result()
        return [dict(row) for row in results]
