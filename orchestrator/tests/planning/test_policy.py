"""Tests for the planner routing policy (ADR-0022, Phase 3b)."""

from orchestrator.planning import (
    DEFAULT_POLICY,
    Op,
    PlannerPolicy,
    PolicyRule,
    Predicate,
    applied_rules,
    select_leaves,
)

ALL_SIX = [
    "spending-analysis",
    "goals-onboarding",
    "portfolio-analysis",
    "research",
    "action-drafting",
    "reviewer",
]


# --------------------------------------------------------------------------- #
# Predicates                                                                   #
# --------------------------------------------------------------------------- #


def test_predicate_operators():
    ctx = {"requested_trade": True, "intent": "action", "count": 0, "tags": ["a", "b"]}
    assert Predicate("requested_trade", Op.TRUTHY).evaluate(ctx)
    assert Predicate("count", Op.FALSY).evaluate(ctx)  # 0 is falsy
    assert Predicate("missing", Op.FALSY).evaluate(ctx)  # absent counts as falsy
    assert Predicate("intent", Op.EQ, "action").evaluate(ctx)
    assert Predicate("intent", Op.NE, "informational").evaluate(ctx)
    assert Predicate("intent", Op.IN, ("action", "trade")).evaluate(ctx)
    assert Predicate("tags", Op.CONTAINS, "a").evaluate(ctx)
    assert not Predicate("tags", Op.CONTAINS, "z").evaluate(ctx)


def test_predicate_missing_field_is_falsy_not_error():
    assert not Predicate("nope", Op.TRUTHY).evaluate({})
    assert not Predicate("nope", Op.EQ, "x").evaluate({})


def test_predicate_dotted_path():
    ctx = {"facts": {"has_active_ips": True}}
    assert Predicate("facts.has_active_ips", Op.TRUTHY).evaluate(ctx)
    assert not Predicate("facts.missing", Op.TRUTHY).evaluate(ctx)


# --------------------------------------------------------------------------- #
# select_leaves                                                                #
# --------------------------------------------------------------------------- #


def test_include_adds_when_condition_holds():
    policy = PlannerPolicy(
        rules=(PolicyRule("trade", Predicate("requested_trade", Op.TRUTHY), include=("action-drafting",)),)
    )
    assert "action-drafting" in select_leaves(["portfolio-analysis"], {"requested_trade": True}, policy)
    assert "action-drafting" not in select_leaves(["portfolio-analysis"], {"requested_trade": False}, policy)


def test_exclude_removes_when_condition_holds():
    policy = PlannerPolicy(
        rules=(PolicyRule("onboarded", Predicate("has_active_ips", Op.TRUTHY), exclude=("goals-onboarding",)),)
    )
    assert "goals-onboarding" not in select_leaves(ALL_SIX, {"has_active_ips": True}, policy)
    assert "goals-onboarding" in select_leaves(ALL_SIX, {"has_active_ips": False}, policy)


def test_exclude_wins_over_include():
    policy = PlannerPolicy(
        rules=(
            PolicyRule("inc", None, include=("action-drafting",)),
            PolicyRule("exc", None, exclude=("action-drafting",)),
        )
    )
    assert "action-drafting" not in select_leaves([], {}, policy)


def test_default_floor_is_exclude_proof():
    # The floor always survives, even if a rule excludes it — guarantees non-empty.
    policy = PlannerPolicy(
        default_floor="spending-analysis",
        rules=(PolicyRule("exc", None, exclude=("spending-analysis",)),),
    )
    assert select_leaves([], {}, policy) == {"spending-analysis"}


def test_empty_everything_yields_floor_only():
    assert select_leaves([], {}, PlannerPolicy(default_floor="spending-analysis")) == {"spending-analysis"}


def test_no_floor_and_all_excluded_is_empty():
    policy = PlannerPolicy(rules=(PolicyRule("exc", None, exclude=tuple(ALL_SIX)),))
    assert select_leaves(ALL_SIX, {}, policy) == set()


def test_applied_rules_reports_fired_rule_names():
    ctx = {"requested_trade": True, "has_active_ips": True}
    assert applied_rules(ctx, DEFAULT_POLICY) == ["trade-intent-include", "onboarding-once"]
    assert applied_rules({"requested_trade": False, "has_active_ips": False}, DEFAULT_POLICY) == []


# --------------------------------------------------------------------------- #
# The default (v1) policy behaviour                                            #
# --------------------------------------------------------------------------- #


def test_default_policy_informational_prompt():
    # "what did I spend on dining?" — no trade, has an IPS. Onboarding drops out;
    # the floor (spending-analysis) is always present.
    ctx = {"requested_trade": False, "has_active_ips": True, "intent": "informational"}
    leaves = select_leaves(ALL_SIX, ctx, DEFAULT_POLICY)
    assert "spending-analysis" in leaves
    assert "goals-onboarding" not in leaves
    assert "action-drafting" in leaves  # v1 keeps it (list-all recall); it self-skips at execution


def test_default_policy_trade_prompt_new_user():
    # A trade prompt from a user with no IPS: trade path included, onboarding kept.
    ctx = {"requested_trade": True, "has_active_ips": False, "intent": "action"}
    leaves = select_leaves(["portfolio-analysis"], ctx, DEFAULT_POLICY)
    assert {"portfolio-analysis", "action-drafting", "spending-analysis"} <= leaves
    assert "goals-onboarding" not in leaves  # not excluded here (no active IPS) — but not a candidate either


def test_default_policy_floor_is_spending_analysis():
    assert DEFAULT_POLICY.default_floor == "spending-analysis"
