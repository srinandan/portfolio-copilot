import pytest

from src.orchestrator.contracts.ips import RiskTolerance
from src.orchestrator.skills.goals_onboarding.logic import (
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
