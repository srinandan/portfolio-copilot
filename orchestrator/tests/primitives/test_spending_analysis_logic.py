import pytest

from orchestrator.primitives.spending_analysis import calculate_reserve_months, calculate_savings_rate, is_anomalous


@pytest.mark.parametrize(
    "current, avg, expected",
    [
        (500, 300, True),
        (35, 20, False),
        (140, 100, False),
        (1100, 1000, False),
        (140.01, 100, False),
    ],
)
def test_is_anomalous(current, avg, expected):
    assert is_anomalous(current, avg) == expected


@pytest.mark.parametrize(
    "income, outflow, expected",
    [
        (5000, 3000, 0.4),
        (5000, 5000, 0.0),
        (5000, 6000, -0.2),
        (0, 3000, 0.0),
        (-1000, 1000, 0.0),
    ],
)
def test_calculate_savings_rate(income, outflow, expected):
    assert calculate_savings_rate(income, outflow) == expected


@pytest.mark.parametrize(
    "cash, expenses, expected",
    [
        (10000, 2000, 5.0),
        (0, 2000, 0.0),
        (5000, 0, float("inf")),
        (0, 0, 0.0),
    ],
)
def test_calculate_reserve_months(cash, expenses, expected):
    assert calculate_reserve_months(cash, expenses) == expected
