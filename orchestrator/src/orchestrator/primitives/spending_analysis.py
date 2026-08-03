"""Pure deterministic math and constraint primitives for Spending Analysis."""


def is_anomalous(current_month_spend: float, trailing_3mo_avg: float) -> bool:
    """Evaluates whether current month category spend is anomalous.

    Rule: current_month_spend > (trailing_3mo_avg * 1.4) AND current_month_spend > (trailing_3mo_avg + 100)
    """
    return (current_month_spend > trailing_3mo_avg * 1.4) and (current_month_spend > trailing_3mo_avg + 100)


def calculate_savings_rate(total_income: float, total_outflow: float) -> float:
    """Calculates savings rate fraction from income and outflow totals.

    Rule: (total_income - total_outflow) / total_income
    """
    if total_income <= 0:
        return 0.0
    return max(0.0, (total_income - total_outflow) / total_income)


def calculate_reserve_months(cash_usd: float, average_monthly_expenses: float) -> float:
    """Calculates months of emergency reserve cash available.

    Rule: cash_usd / average_monthly_expenses
    """
    if average_monthly_expenses <= 0:
        return 0.0
    return cash_usd / average_monthly_expenses
