"""Deterministic re-check of the same rules the reviewer Managed Agent evaluates.

Each rule is a pure function taking a ReviewInput and returning a RuleResult.
The orchestrator invokes `check_all_rules(input)` after the Managed Agent
returns its own verdict; the results become the *authoritative* verdict.
Divergence between the LLM's verdict and this module's verdict is captured
in the REVIEW_COMPLETED audit entry.

Rule set matches skills/reviewer/SKILL.md's "Rules to evaluate" section.
If a rule is added here, add it there and to the evalset. If a rule is
added there and not here, the LLM's version wins by default (bad); always
mirror both.
"""

from dataclasses import dataclass
from typing import Callable, List

from ..contracts.holdings import HoldingsSnapshot
from ..contracts.ips import InvestmentPolicyStatement
from ..contracts.proposed_action import ProposedAction, Side
from ..contracts.reviewer_verdict import RuleResult
from ..primitives.action_drafting import get_mock_sector
from ..primitives.portfolio_analysis import calculate_drift


@dataclass(frozen=True)
class ReviewInput:
    """What every rule needs. Assembled by the reviewer preloader."""

    action: ProposedAction
    ips: InvestmentPolicyStatement
    holdings: HoldingsSnapshot


# ---------- individual rules ----------


def rule_excluded_ticker(inp: ReviewInput) -> RuleResult:
    excluded = [t.upper() for t in (inp.ips.constraints.excluded_tickers or [])]
    if inp.action.ticker.upper() in excluded:
        return RuleResult(
            rule_id="excluded_ticker",
            description="Ticker must not be in IPS constraints.excluded_tickers",
            passed=False,
            detail=f"{inp.action.ticker} is in excluded_tickers",
        )
    return RuleResult(
        rule_id="excluded_ticker",
        description="Ticker must not be in IPS constraints.excluded_tickers",
        passed=True,
    )


def rule_excluded_sector(inp: ReviewInput) -> RuleResult:
    sector = get_mock_sector(inp.action.ticker)
    excluded = [s.lower() for s in (inp.ips.constraints.excluded_sectors or [])]
    if sector != "Unknown" and sector.lower() in excluded:
        return RuleResult(
            rule_id="excluded_sector",
            description="Sector must not be in IPS constraints.excluded_sectors",
            passed=False,
            detail=f"{inp.action.ticker} is in excluded sector {sector}",
        )
    return RuleResult(
        rule_id="excluded_sector",
        description="Sector must not be in IPS constraints.excluded_sectors",
        passed=True,
    )


def rule_concentration_limit(inp: ReviewInput) -> RuleResult:
    total = inp.holdings.total_value_usd
    if total is None:
        total = sum(p.market_value_usd for p in inp.holdings.positions) + (
            inp.holdings.cash_usd or 0.0
        )
    if total <= 0:
        return RuleResult(
            rule_id="concentration_limit",
            description="Resulting position must be at/below concentration_limit_percent",
            passed=False,
            detail="Portfolio total value is 0; cannot evaluate concentration.",
        )
    current_value = next(
        (
            p.market_value_usd
            for p in inp.holdings.positions
            if p.ticker == inp.action.ticker
        ),
        0.0,
    )
    trade_value = inp.action.estimated_value_usd or 0.0
    if inp.action.side == Side.BUY:
        resulting = current_value + trade_value
    else:
        resulting = max(0.0, current_value - trade_value)
    pct = (resulting / total) * 100.0
    limit = inp.ips.constraints.concentration_limit_percent
    if limit is not None and pct > limit:
        return RuleResult(
            rule_id="concentration_limit",
            description="Resulting position must be at/below concentration_limit_percent",
            passed=False,
            detail=f"Resulting {inp.action.ticker} position would be {pct:.2f}% (limit {limit}%)",
        )
    return RuleResult(
        rule_id="concentration_limit",
        description="Resulting position must be at/below concentration_limit_percent",
        passed=True,
    )


def rule_allocation_band_direction(inp: ReviewInput) -> RuleResult:
    """A sell in an under-allocated class fails; a buy in an over-allocated class fails."""
    asset_class = next(
        (
            p.asset_class
            for p in inp.holdings.positions
            if p.ticker == inp.action.ticker
        ),
        None,
    )
    if asset_class is None:
        return RuleResult(
            rule_id="allocation_band_direction",
            description="Trade must move asset class toward IPS target band, not away",
            passed=True,
            detail=f"{inp.action.ticker} is a new position; direction rule not applicable.",
        )
    drift_report = calculate_drift(inp.holdings, inp.ips)
    entry = next(
        (e for e in drift_report.entries if e.asset_class == asset_class), None
    )
    if entry is None:
        return RuleResult(
            rule_id="allocation_band_direction",
            description="Trade must move asset class toward IPS target band, not away",
            passed=True,
            detail=f"Asset class {asset_class} isn't in IPS bands; direction rule not applicable.",
        )
    is_over = entry.current_percent > entry.max_percent
    is_under = entry.current_percent < entry.min_percent
    if inp.action.side == Side.BUY and is_over:
        return RuleResult(
            rule_id="allocation_band_direction",
            description="Trade must move asset class toward IPS target band, not away",
            passed=False,
            detail=f"Cannot BUY into {asset_class} which is already over-allocated at {entry.current_percent:.2f}% (max {entry.max_percent}%)",
        )
    if inp.action.side == Side.SELL and is_under:
        return RuleResult(
            rule_id="allocation_band_direction",
            description="Trade must move asset class toward IPS target band, not away",
            passed=False,
            detail=f"Cannot SELL from {asset_class} which is already under-allocated at {entry.current_percent:.2f}% (min {entry.min_percent}%)",
        )
    return RuleResult(
        rule_id="allocation_band_direction",
        description="Trade must move asset class toward IPS target band, not away",
        passed=True,
    )


def rule_ips_version_current(inp: ReviewInput) -> RuleResult:
    referenced = inp.action.ips_version_referenced
    if referenced.ips_id != inp.ips.ips_id or referenced.version != inp.ips.version:
        return RuleResult(
            rule_id="ips_version_current",
            description="ProposedAction must reference the currently active IPS version",
            passed=False,
            detail=(
                f"Action referenced IPS {referenced.ips_id} v{referenced.version}, "
                f"but current active is {inp.ips.ips_id} v{inp.ips.version}"
            ),
        )
    return RuleResult(
        rule_id="ips_version_current",
        description="ProposedAction must reference the currently active IPS version",
        passed=True,
    )


# ---------- rule registry ----------

RULES: List[Callable[[ReviewInput], RuleResult]] = [
    rule_excluded_ticker,
    rule_excluded_sector,
    rule_concentration_limit,
    rule_allocation_band_direction,
    rule_ips_version_current,
]


def check_all_rules(inp: ReviewInput) -> List[RuleResult]:
    """Runs every rule in RULES against the input. Returns results in the same
    order as RULES for stable ordering."""
    return [rule(inp) for rule in RULES]


def compute_requires_human_approval(inp: ReviewInput, overall_pass: bool) -> bool:
    """Per SKILL.md: requires_human_approval is true if
    (a) overall_pass is false, OR
    (b) estimated_value_usd exceeds IPS approval_required_above_usd, OR
    (c) value as fraction of portfolio exceeds approval_required_above_percent.
    """
    if not overall_pass:
        return True
    thresh_usd = inp.ips.approval_required_above_usd
    if thresh_usd is not None and (inp.action.estimated_value_usd or 0.0) > thresh_usd:
        return True
    thresh_pct = inp.ips.approval_required_above_percent
    if thresh_pct is not None:
        total = inp.holdings.total_value_usd or (
            sum(p.market_value_usd for p in inp.holdings.positions)
            + (inp.holdings.cash_usd or 0.0)
        )
        if (
            total > 0
            and ((inp.action.estimated_value_usd or 0.0) / total * 100.0) > thresh_pct
        ):
            return True
    return False
