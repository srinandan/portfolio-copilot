"""Deterministic formulas for spending analysis and reserve calculations."""


def is_anomalous(current_month_spend: float, trailing_3mo_avg: float) -> bool:
    """Determines if a category's spend is anomalous.

    A category is flagged for a given month if both conditions hold:
    current_month_spend > (trailing_3_month_average * 1.4)
    current_month_spend > (trailing_3_month_average + 100)
    """
    return (current_month_spend > trailing_3mo_avg * 1.4) and (current_month_spend > trailing_3mo_avg + 100)


def calculate_savings_rate(total_income: float, total_outflow: float) -> float:
    """Calculates savings rate as a fraction of total income: (income - outflow) / income."""
    if total_income <= 0:
        return 0.0
    return (total_income - total_outflow) / total_income


def calculate_reserve_months(cash_usd: float, average_monthly_expenses: float) -> float:
    """Calculates cash reserve duration in months: cash_usd / average_monthly_expenses."""
    if average_monthly_expenses <= 0:
        return float("inf") if cash_usd > 0 else 0.0
    return cash_usd / average_monthly_expenses
