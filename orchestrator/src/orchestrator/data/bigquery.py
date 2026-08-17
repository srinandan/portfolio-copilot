import os
import re
import time
from typing import Any, Dict, List, Optional

from google.cloud import bigquery

from ..logger import get_logger

logger = get_logger(__name__)


class BigQueryClient:
    def __init__(
        self,
        project: Optional[str] = None,
        table: Optional[str] = None,
        enable_mcp: Optional[bool] = None,
    ):
        self.project = (
            project or os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "test-project"
        )
        self.table = table or os.environ.get("TRANSACTIONS_TABLE", "checking_transactions")
        self.client = bigquery.Client(project=self.project)
        self.enable_mcp = (
            enable_mcp
            if enable_mcp is not None
            else (os.environ.get("ENABLE_BIGQUERY_MCP", "true").lower() in ("true", "1", "yes"))
        )
        self._mcp_client = None
        if self.enable_mcp:
            try:
                from .bigquery_mcp import BigQueryMCPClient

                self._mcp_client = BigQueryMCPClient(project=self.project)
            except Exception as e:
                logger.warning("Failed to initialize BigQueryMCPClient: %s", e)

    def get_spending_snapshot(
        self, user_id: str, current_month_start: str, window_months: int = 3
    ) -> tuple[Dict[str, float], List[Dict[str, Any]]]:
        """Combines income/outflow totals and per-category spending into a single BigQuery job."""
        t0 = time.monotonic()
        query = f"""
        WITH scoped AS (
          SELECT
            user_id,
            transaction_date,
            normalized_category,
            amount,
            DATE_TRUNC(transaction_date, MONTH) AS month
          FROM `{self.project}.portfolio_copilot.{self.table}`
          WHERE user_id = @user_id
            AND transaction_date >= DATE_SUB(CAST(@current_month_start AS DATE), INTERVAL @window_months MONTH)
            AND transaction_date < DATE_ADD(CAST(@current_month_start AS DATE), INTERVAL 1 MONTH)
        ),
        income_outflow AS (
          SELECT
            SUM(IF(amount > 0 AND transaction_date < CAST(@current_month_start AS DATE), amount, 0)) AS total_income,
            SUM(IF(amount < 0 AND transaction_date < CAST(@current_month_start AS DATE), -amount, 0)) AS total_outflow
          FROM scoped
        ),
        per_category AS (
          SELECT
            normalized_category,
            SUM(IF(month = CAST(@current_month_start AS DATE), -amount, 0)) AS current_month_spend,
            AVG(IF(month < CAST(@current_month_start AS DATE), -amount, NULL)) AS trailing_3mo_avg
          FROM scoped
          WHERE amount < 0
          GROUP BY normalized_category
        )
        SELECT
          (SELECT total_income FROM income_outflow) AS total_income,
          (SELECT total_outflow FROM income_outflow) AS total_outflow,
          ARRAY(
            SELECT AS STRUCT
              normalized_category,
              current_month_spend,
              trailing_3mo_avg
            FROM per_category
          ) AS category_totals
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                bigquery.ScalarQueryParameter("current_month_start", "STRING", current_month_start),
                bigquery.ScalarQueryParameter("window_months", "INT64", window_months),
            ]
        )
        logger.info(
            "bigquery_spending_query_start: querying table '%s' for user '%s' (window=%d months, current_month_start=%s)",
            self.table,
            user_id,
            window_months,
            current_month_start,
            extra={
                "event": "bigquery_spending_query_start",
                "user_id": user_id,
                "table": self.table,
                "current_month_start": current_month_start,
                "window_months": window_months,
            },
        )
        query_job = self.client.query(query, job_config=job_config)
        results = list(query_job.result())
        elapsed_sec = round(time.monotonic() - t0, 3)
        job_id = getattr(query_job, "job_id", "unknown")
        bytes_billed = getattr(query_job, "total_bytes_billed", 0)

        if not results:
            logger.info(
                "bigquery_spending_query_complete: table '%s', user '%s', elapsed=%.3fs, job_id=%s, rows_returned=0, bytes_billed=%s",
                self.table,
                user_id,
                elapsed_sec,
                job_id,
                bytes_billed,
                extra={
                    "event": "bigquery_spending_query_complete",
                    "user_id": user_id,
                    "table": self.table,
                    "elapsed_sec": elapsed_sec,
                    "job_id": job_id,
                    "rows_returned": 0,
                    "bytes_billed": bytes_billed,
                },
            )
            return {"total_income": 0.0, "total_outflow": 0.0}, []

        row = results[0]
        totals = {
            "total_income": float(row.total_income or 0.0),
            "total_outflow": float(row.total_outflow or 0.0),
        }
        category_rows = [
            {
                "normalized_category": c["normalized_category"],
                "current_month_spend": float(c["current_month_spend"] or 0.0),
                "trailing_3mo_avg": float(c["trailing_3mo_avg"]) if c["trailing_3mo_avg"] is not None else 0.0,
            }
            for c in (row.category_totals or [])
        ]
        logger.info(
            "bigquery_spending_query_complete: table '%s', user '%s', elapsed=%.3fs, job_id=%s, category_count=%d, income=$%.2f, outflow=$%.2f, bytes_billed=%s",
            self.table,
            user_id,
            elapsed_sec,
            job_id,
            len(category_rows),
            totals["total_income"],
            totals["total_outflow"],
            bytes_billed,
            extra={
                "event": "bigquery_spending_query_complete",
                "user_id": user_id,
                "table": self.table,
                "elapsed_sec": elapsed_sec,
                "job_id": job_id,
                "category_count": len(category_rows),
                "total_income": totals["total_income"],
                "total_outflow": totals["total_outflow"],
                "bytes_billed": bytes_billed,
            },
        )
        return totals, category_rows

    def get_monthly_spending_totals(
        self, user_id: str, current_month_start: str, window_months: int = 3
    ) -> List[Dict[str, Any]]:
        t0 = time.monotonic()
        query = f"""
        WITH monthly_totals AS (
          SELECT
            normalized_category,
            DATE_TRUNC(transaction_date, MONTH) AS month,
            SUM(-amount) AS total_spend
          FROM `{self.project}.portfolio_copilot.{self.table}`
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
        logger.info(
            "bigquery_monthly_totals_start: querying table '%s' for user '%s'",
            self.table,
            user_id,
            extra={"event": "bigquery_monthly_totals_start", "user_id": user_id, "table": self.table},
        )
        query_job = self.client.query(query, job_config=job_config)
        results = query_job.result()
        rows = [dict(row) for row in results]
        elapsed_sec = round(time.monotonic() - t0, 3)
        logger.info(
            "bigquery_monthly_totals_complete: table '%s', user '%s', elapsed=%.3fs, rows=%d",
            self.table,
            user_id,
            elapsed_sec,
            len(rows),
            extra={
                "event": "bigquery_monthly_totals_complete",
                "user_id": user_id,
                "table": self.table,
                "elapsed_sec": elapsed_sec,
                "rows_returned": len(rows),
            },
        )
        return rows

    def get_trailing_income_and_outflow(
        self, user_id: str, current_month_start: str, window_months: int = 3
    ) -> Dict[str, float]:
        t0 = time.monotonic()
        query = f"""
        SELECT
            SUM(IF(amount > 0, amount, 0)) as total_income,
            SUM(IF(amount < 0, -amount, 0)) as total_outflow
        FROM `{self.project}.portfolio_copilot.{self.table}`
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
        logger.info(
            "bigquery_income_outflow_start: querying table '%s' for user '%s'",
            self.table,
            user_id,
            extra={"event": "bigquery_income_outflow_start", "user_id": user_id, "table": self.table},
        )
        query_job = self.client.query(query, job_config=job_config)
        results = list(query_job.result())
        elapsed_sec = round(time.monotonic() - t0, 3)

        total_income = results[0].total_income if results and results[0].total_income else 0.0
        total_outflow = results[0].total_outflow if results and results[0].total_outflow else 0.0

        logger.info(
            "bigquery_income_outflow_complete: table '%s', user '%s', elapsed=%.3fs, income=$%.2f, outflow=$%.2f",
            self.table,
            user_id,
            elapsed_sec,
            float(total_income),
            float(total_outflow),
            extra={
                "event": "bigquery_income_outflow_complete",
                "user_id": user_id,
                "table": self.table,
                "elapsed_sec": elapsed_sec,
                "total_income": float(total_income),
                "total_outflow": float(total_outflow),
            },
        )
        return {"total_income": float(total_income), "total_outflow": float(total_outflow)}

    def validate_and_execute_nl_sql(self, user_id: str, sql_query: str) -> List[Dict[str, Any]]:
        sql_upper = sql_query.upper()

        forbidden_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE", "MERGE"]
        for kw in forbidden_keywords:
            if re.search(r"\b" + kw + r"\b", sql_upper):
                raise ValueError(f"Write-intent SQL refused: {kw} is not allowed.")

        if "FROM" in sql_upper:
            if not re.search(r"\b[A-Z0-9_]+_TRANSACTIONS\b", sql_upper):
                raise ValueError("Query must target a transactions table (e.g. checking_transactions).")

        if "@user_id" not in sql_query:
            raise ValueError("Query must include @user_id parameter for scoping.")

        if self._mcp_client is not None:
            try:
                return self._execute_nl_sql_mcp(user_id, sql_query)
            except Exception as e:
                logger.warning(
                    "BigQuery Remote MCP execution failed (%s), falling back to direct SDK",
                    e,
                )

        return self._execute_nl_sql_direct(user_id, sql_query)

    def _execute_nl_sql_mcp(self, user_id: str, sql_query: str) -> List[Dict[str, Any]]:
        t0 = time.monotonic()
        logger.info(
            "bigquery_nl_sql_mcp_start: executing query via MCP for user '%s': %s",
            user_id,
            sql_query,
            extra={"event": "bigquery_nl_sql_mcp_start", "user_id": user_id, "query": sql_query},
        )
        query_params = [{"name": "user_id", "parameterType": {"type": "STRING"}, "parameterValue": {"value": user_id}}]
        assert self._mcp_client is not None
        rows = self._mcp_client.execute_query(
            query=sql_query,
            project_id=self.project,
            query_parameters=query_params,
            maximum_bytes_billed=10 * 1024 * 1024,
        )
        elapsed_sec = round(time.monotonic() - t0, 3)
        logger.info(
            "bigquery_nl_sql_mcp_complete: user '%s', elapsed=%.3fs, rows=%d",
            user_id,
            elapsed_sec,
            len(rows),
            extra={
                "event": "bigquery_nl_sql_mcp_complete",
                "user_id": user_id,
                "elapsed_sec": elapsed_sec,
                "rows_returned": len(rows),
            },
        )
        return rows

    def _execute_nl_sql_direct(self, user_id: str, sql_query: str) -> List[Dict[str, Any]]:
        t0 = time.monotonic()
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
            ],
            maximum_bytes_billed=10 * 1024 * 1024,
        )

        logger.info(
            "bigquery_nl_sql_start: executing query for user '%s': %s",
            user_id,
            sql_query,
            extra={"event": "bigquery_nl_sql_start", "user_id": user_id, "query": sql_query},
        )
        query_job = self.client.query(sql_query, job_config=job_config)
        results = query_job.result()
        rows = [dict(row) for row in results]
        elapsed_sec = round(time.monotonic() - t0, 3)
        logger.info(
            "bigquery_nl_sql_complete: user '%s', elapsed=%.3fs, rows=%d, bytes_billed=%s",
            user_id,
            elapsed_sec,
            len(rows),
            getattr(query_job, "total_bytes_billed", 0),
            extra={
                "event": "bigquery_nl_sql_complete",
                "user_id": user_id,
                "elapsed_sec": elapsed_sec,
                "rows_returned": len(rows),
                "bytes_billed": getattr(query_job, "total_bytes_billed", 0),
            },
        )
        return rows
