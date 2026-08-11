"""Unit tests for Reviewer/Critic deterministic rules."""

from orchestrator.contracts.holdings import Position
from orchestrator.contracts.ips import RelatedIPSVersion
from orchestrator.contracts.proposed_action import Side
from orchestrator.contracts.reviewer_verdict import RuleResult
from orchestrator.reviewer.rules import (
    RULES,
    ReviewInput,
    check_all_rules,
    compute_requires_human_approval,
    rule_allocation_band_direction,
    rule_concentration_limit,
    rule_excluded_sector,
    rule_excluded_ticker,
    rule_ips_version_current,
)


def test_excluded_ticker_passes_when_ticker_not_excluded(happy_review_input):
    res = rule_excluded_ticker(happy_review_input)
    assert res.passed is True
    assert res.rule_id == "excluded_ticker"


def test_excluded_ticker_fails_when_ticker_excluded(happy_review_input):
    action = happy_review_input.action.model_copy(update={"ticker": "TSLA"})
    inp = ReviewInput(action=action, ips=happy_review_input.ips, holdings=happy_review_input.holdings)
    res = rule_excluded_ticker(inp)
    assert res.passed is False
    assert res.rule_id == "excluded_ticker"
    assert "TSLA is in excluded_tickers" in res.detail


def test_excluded_sector_fails_when_unknown_and_excluded_sectors_set(happy_review_input):
    # When excluded_sectors is non-empty, an unknown ticker must fail-closed
    action = happy_review_input.action.model_copy(update={"ticker": "UNKNOWN_TICKER"})
    inp = ReviewInput(action=action, ips=happy_review_input.ips, holdings=happy_review_input.holdings)
    res = rule_excluded_sector(inp)
    assert res.passed is False
    assert res.rule_id == "excluded_sector"
    assert "Cannot classify sector for UNKNOWN_TICKER" in res.detail


def test_excluded_sector_passes_when_unknown_and_no_excluded_sectors(happy_review_input):
    # When excluded_sectors is empty, unknown tickers pass
    ips = happy_review_input.ips.model_copy(
        update={"constraints": happy_review_input.ips.constraints.model_copy(update={"excluded_sectors": []})}
    )
    action = happy_review_input.action.model_copy(update={"ticker": "UNKNOWN_TICKER"})
    inp = ReviewInput(action=action, ips=ips, holdings=happy_review_input.holdings)
    res = rule_excluded_sector(inp)
    assert res.passed is True
    assert res.rule_id == "excluded_sector"


def test_excluded_sector_fails_when_sector_excluded(happy_review_input):
    # XOM is in Energy sector in KNOWN_SECTOR_MAP, and Energy is in happy_ips excluded_sectors
    action = happy_review_input.action.model_copy(update={"ticker": "XOM"})
    inp = ReviewInput(action=action, ips=happy_review_input.ips, holdings=happy_review_input.holdings)
    res = rule_excluded_sector(inp)
    assert res.passed is False
    assert res.rule_id == "excluded_sector"
    assert "in excluded sector Energy" in res.detail


def test_excluded_sector_passes_when_sector_not_excluded(happy_review_input):
    # AAPL is in Technology sector in KNOWN_SECTOR_MAP, which is not in happy_ips excluded_sectors (Energy)
    action = happy_review_input.action.model_copy(update={"ticker": "AAPL"})
    inp = ReviewInput(action=action, ips=happy_review_input.ips, holdings=happy_review_input.holdings)
    res = rule_excluded_sector(inp)
    assert res.passed is True
    assert res.rule_id == "excluded_sector"


def test_concentration_limit_passes_below(happy_review_input):
    res = rule_concentration_limit(happy_review_input)
    assert res.passed is True
    assert res.rule_id == "concentration_limit"


def test_concentration_limit_fails_above(happy_review_input):
    # $50,000 buy of AAPL brings total AAPL to $60,000 / $100,000 = 60%, limit is 15%
    action = happy_review_input.action.model_copy(update={"estimated_value_usd": 50000.0})
    inp = ReviewInput(action=action, ips=happy_review_input.ips, holdings=happy_review_input.holdings)
    res = rule_concentration_limit(inp)
    assert res.passed is False
    assert res.rule_id == "concentration_limit"
    assert "60.00% (limit 15" in res.detail


def test_concentration_limit_zero_total_fails_gracefully(happy_review_input):
    holdings = happy_review_input.holdings.model_copy(update={"total_value_usd": 0.0, "cash_usd": 0.0, "positions": []})
    inp = ReviewInput(action=happy_review_input.action, ips=happy_review_input.ips, holdings=holdings)
    res = rule_concentration_limit(inp)
    assert res.passed is False
    assert "Portfolio total value is 0" in res.detail


def test_allocation_band_direction_passes_moving_toward(happy_review_input):
    res = rule_allocation_band_direction(happy_review_input)
    assert res.passed is True
    assert res.rule_id == "allocation_band_direction"


def test_allocation_band_direction_fails_buying_into_over_allocated(happy_review_input):
    # Current Equity is $80k / $100k = 80%, max target is 70%
    holdings = happy_review_input.holdings.model_copy(
        update={
            "positions": [
                Position(
                    ticker="AAPL",
                    quantity=400,
                    asset_class="Equity",
                    market_value_usd=80000.0,
                )
            ],
            "cash_usd": 20000.0,
        }
    )
    inp = ReviewInput(action=happy_review_input.action, ips=happy_review_input.ips, holdings=holdings)
    res = rule_allocation_band_direction(inp)
    assert res.passed is False
    assert res.rule_id == "allocation_band_direction"
    assert "over-allocated" in res.detail


def test_allocation_band_direction_fails_selling_from_under_allocated(happy_review_input):
    # Current Equity is $40k / $100k = 40%, min target is 50%
    holdings = happy_review_input.holdings.model_copy(
        update={
            "positions": [
                Position(
                    ticker="AAPL",
                    quantity=200,
                    asset_class="Equity",
                    market_value_usd=40000.0,
                )
            ],
            "cash_usd": 60000.0,
        }
    )
    action = happy_review_input.action.model_copy(update={"side": Side.SELL})
    inp = ReviewInput(action=action, ips=happy_review_input.ips, holdings=holdings)
    res = rule_allocation_band_direction(inp)
    assert res.passed is False
    assert "under-allocated" in res.detail


def test_allocation_band_direction_passes_new_ticker(happy_review_input):
    action = happy_review_input.action.model_copy(update={"ticker": "NEW_TICKER"})
    inp = ReviewInput(action=action, ips=happy_review_input.ips, holdings=happy_review_input.holdings)
    res = rule_allocation_band_direction(inp)
    assert res.passed is True
    assert "new position" in res.detail


def test_ips_version_current_passes_when_matched(happy_review_input):
    res = rule_ips_version_current(happy_review_input)
    assert res.passed is True
    assert res.rule_id == "ips_version_current"


def test_ips_version_current_fails_when_stale(happy_review_input):
    action = happy_review_input.action.model_copy(
        update={"ips_version_referenced": RelatedIPSVersion(ips_id="ips_happy", version=999)}
    )
    inp = ReviewInput(action=action, ips=happy_review_input.ips, holdings=happy_review_input.holdings)
    res = rule_ips_version_current(inp)
    assert res.passed is False
    assert res.rule_id == "ips_version_current"
    assert "current active is ips_happy v1" in res.detail


def test_check_all_rules_returns_result_per_rule(happy_review_input):
    results = check_all_rules(happy_review_input)
    assert len(results) == len(RULES)
    assert all(isinstance(r, RuleResult) for r in results)
    assert {r.rule_id for r in results} == {
        "excluded_ticker",
        "excluded_sector",
        "concentration_limit",
        "allocation_band_direction",
        "ips_version_current",
    }


def test_compute_requires_human_approval_true_on_rule_fail(happy_review_input):
    assert compute_requires_human_approval(happy_review_input, overall_pass=False) is True


def test_compute_requires_human_approval_true_on_usd_threshold(happy_review_input):
    # Action estimated value = $30,000 > threshold of $25,000
    action = happy_review_input.action.model_copy(update={"estimated_value_usd": 30000.0})
    inp = ReviewInput(action=action, ips=happy_review_input.ips, holdings=happy_review_input.holdings)
    assert compute_requires_human_approval(inp, overall_pass=True) is True


def test_compute_requires_human_approval_true_on_pct_threshold(happy_review_input):
    # Action estimated value = $21,000 / $100,000 = 21% > threshold of 20%
    action = happy_review_input.action.model_copy(update={"estimated_value_usd": 21000.0})
    inp = ReviewInput(action=action, ips=happy_review_input.ips, holdings=happy_review_input.holdings)
    assert compute_requires_human_approval(inp, overall_pass=True) is True


def test_compute_requires_human_approval_false_when_all_clear(happy_review_input):
    # Action estimated value = $5,000 (5% < 20% and < $25,000)
    assert compute_requires_human_approval(happy_review_input, overall_pass=True) is False
