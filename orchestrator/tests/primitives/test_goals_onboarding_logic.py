import pytest

from orchestrator.contracts.ips import RiskTolerance
from orchestrator.primitives.goals_onboarding import (
    calculate_risk_tolerance,
    get_default_allocation_bands,
)


@pytest.mark.parametrize(
    "time_horizon, reaction, expected",
    [
        (15, "buy_more", RiskTolerance.AGGRESSIVE),
        (15, "hold", RiskTolerance.AGGRESSIVE),
        (7, "hold", RiskTolerance.MODERATE),
        (5, "hold", RiskTolerance.MODERATE),
        (20, "sell", RiskTolerance.CONSERVATIVE),
        (5, "sell", RiskTolerance.CONSERVATIVE),
    ],
)
def test_calculate_risk_tolerance(time_horizon, reaction, expected):
    assert calculate_risk_tolerance(time_horizon, reaction) == expected


def test_get_default_allocation_bands():
    bands = get_default_allocation_bands(RiskTolerance.CONSERVATIVE)
    assert len(bands) == 3
    assert any(b.asset_class == "equity" and b.target_percent == 30 for b in bands)

    bands = get_default_allocation_bands(RiskTolerance.MODERATE)
    assert any(b.asset_class == "equity" and b.target_percent == 60 for b in bands)

    bands = get_default_allocation_bands(RiskTolerance.AGGRESSIVE)
    assert any(b.asset_class == "equity" and b.target_percent == 85 for b in bands)


def test_unknown_risk_tier():
    with pytest.raises(ValueError):
        get_default_allocation_bands(RiskTolerance("unknown"))


def test_constraints_sanitization():
    from orchestrator.contracts.ips import Constraints

    c = Constraints(
        excluded_tickers=[" tsla ", "aapl", ""],
        excluded_sectors=[" Energy ", "tech"],
        concentration_limit_percent=20.0,
    )
    assert c.excluded_tickers == ["TSLA", "AAPL"]
    assert c.excluded_sectors == ["Energy", "tech"]


def test_goals_onboarding_result_bounds_validation():
    from orchestrator.contracts.goals_onboarding import GoalsOnboardingResult
    from orchestrator.contracts.ips import TargetAllocation

    valid_allocs = [
        TargetAllocation(asset_class="us_equities", target_percent=60.0, min_percent=50.0, max_percent=70.0),
        TargetAllocation(asset_class="bonds", target_percent=40.0, min_percent=30.0, max_percent=50.0),
    ]

    result = GoalsOnboardingResult(
        user_id="user_123",
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=valid_allocs,
        interview_summary="Goals onboarding completed.",
    )
    assert result.time_horizon_years == 10

    with pytest.raises(ValueError):
        GoalsOnboardingResult(
            user_id="user_123",
            risk_tolerance=RiskTolerance.MODERATE,
            time_horizon_years=-5,  # must be ge=0
            target_allocation=valid_allocs,
            interview_summary="Failed.",
        )
