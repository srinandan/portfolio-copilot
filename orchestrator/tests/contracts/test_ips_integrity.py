"""Integrity-floor regression tests for the IPS contracts (SEC-04, issue #355).

The deterministic reviewer evaluates every rule against the active IPS, so a
permissive-but-schema-valid policy would silently neuter it. These tests pin the
fail-closed bounds that make such a policy non-constructable: the concentration
band, the allocation-sum requirement, and the degenerate-band ceiling.
"""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from orchestrator.contracts.goals_onboarding import GoalsOnboardingResult
from orchestrator.contracts.ips import (
    CONCENTRATION_LIMIT_MAX_PERCENT,
    CONCENTRATION_LIMIT_MIN_PERCENT,
    Constraints,
    InvestmentPolicyStatement,
    IPSStatus,
    RiskTolerance,
    TargetAllocation,
)

# A complete, moderate allocation set that sums to 100 with sane bands.
VALID_ALLOCATION = [
    TargetAllocation(asset_class="equity", target_percent=60, min_percent=50, max_percent=70),
    TargetAllocation(asset_class="bonds", target_percent=40, min_percent=30, max_percent=50),
]


def _ips(*, concentration=15.0, allocation=None):
    return InvestmentPolicyStatement(
        ips_id="ips_1",
        user_id="demo_user",
        version=1,
        status=IPSStatus.ACTIVE,
        effective_date=date(2026, 1, 1),
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=VALID_ALLOCATION if allocation is None else allocation,
        constraints=Constraints(concentration_limit_percent=concentration),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


# ---------- concentration band ----------


@pytest.mark.parametrize("value", [CONCENTRATION_LIMIT_MIN_PERCENT, 15.0, 30.0, CONCENTRATION_LIMIT_MAX_PERCENT])
def test_concentration_within_band_is_accepted(value):
    assert Constraints(concentration_limit_percent=value).concentration_limit_percent == value


@pytest.mark.parametrize("value", [0.0, 4.9, 50.1, 90.0, 100.0])
def test_concentration_outside_band_is_rejected(value):
    with pytest.raises(ValidationError, match="concentration_limit_percent"):
        Constraints(concentration_limit_percent=value)


# ---------- allocation sum ----------


def test_moderate_ips_validates():
    ips = _ips()
    assert sum(a.target_percent for a in ips.target_allocation) == pytest.approx(100.0)


@pytest.mark.parametrize(
    "allocation",
    [
        [],  # empty — no bands, so the direction rule never fires
        [TargetAllocation(asset_class="equity", target_percent=60, min_percent=50, max_percent=70)],  # sums to 60
    ],
)
def test_allocation_not_summing_to_100_is_rejected(allocation):
    with pytest.raises(ValidationError, match="sum to"):
        _ips(allocation=allocation)


def test_allocation_sum_within_tolerance_is_accepted():
    # 60 + 39.5 = 99.5 is within the 1-point tolerance.
    allocation = [
        TargetAllocation(asset_class="equity", target_percent=60, min_percent=50, max_percent=70),
        TargetAllocation(asset_class="bonds", target_percent=39.5, min_percent=30, max_percent=50),
    ]
    assert _ips(allocation=allocation) is not None


# ---------- degenerate bands ----------


def test_full_width_band_is_rejected():
    with pytest.raises(ValidationError, match="too wide"):
        TargetAllocation(asset_class="equity", target_percent=50, min_percent=0, max_percent=100)


def test_reasonable_band_is_accepted():
    band = TargetAllocation(asset_class="equity", target_percent=60, min_percent=40, max_percent=80)
    assert band.max_percent - band.min_percent == 40


# ---------- the "defanged IPS" from the issue ----------


def test_defanged_ips_is_rejected():
    """The exact neutering policy from #355: concentration 100, empty exclusions,
    allocation bands 0-100. It must be non-constructable — not silently clamped."""
    with pytest.raises(ValidationError):
        InvestmentPolicyStatement(
            ips_id="ips_evil",
            user_id="demo_user",
            version=1,
            status=IPSStatus.ACTIVE,
            effective_date=date(2026, 1, 1),
            risk_tolerance=RiskTolerance.AGGRESSIVE,
            time_horizon_years=10,
            target_allocation=[
                TargetAllocation(asset_class="equity", target_percent=50, min_percent=0, max_percent=100),
                TargetAllocation(asset_class="cash", target_percent=50, min_percent=0, max_percent=100),
            ],
            constraints=Constraints(concentration_limit_percent=100.0, excluded_tickers=[], excluded_sectors=[]),
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )


# ---------- GoalsOnboardingResult mirrors the allocation-sum floor ----------


def test_goals_onboarding_result_rejects_incomplete_allocation():
    """The onboarding-interview result feeds write_ips_from_interview_result, so it
    carries the same allocation-sum floor to fail closed before an IPS is written."""
    with pytest.raises(ValidationError, match="sum to"):
        GoalsOnboardingResult(
            user_id="demo_user",
            risk_tolerance=RiskTolerance.MODERATE,
            time_horizon_years=10,
            target_allocation=[
                TargetAllocation(asset_class="equity", target_percent=60, min_percent=50, max_percent=70),
            ],
            interview_summary="incomplete",
        )


def test_goals_onboarding_result_accepts_complete_allocation():
    result = GoalsOnboardingResult(
        user_id="demo_user",
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=VALID_ALLOCATION,
        interview_summary="complete",
    )
    assert len(result.target_allocation) == 2
