"""Adversarial suite: every canned attack must be caught by the deterministic
re-check. This test is the hardest gate in the whole test suite — a failure
means the reviewer is not doing its job. Do not skip, do not weaken."""

import pytest
from orchestrator.reviewer.rules import check_all_rules

from .scenarios import ALL_SCENARIOS


@pytest.mark.parametrize("scenario_fn", ALL_SCENARIOS, ids=lambda fn: fn.__name__)
def test_reviewer_catches_adversarial(scenario_fn):
    name, review_input, expected_failing_rule = scenario_fn()
    results = check_all_rules(review_input)
    failing = {r.rule_id for r in results if not r.passed}
    if expected_failing_rule is None:
        assert len(failing) == 0, f"Scenario '{name}' should pass all rules, but failed: {failing}"
    else:
        assert expected_failing_rule in failing, (
            f"Adversarial scenario '{name}' should have been caught by rule "
            f"'{expected_failing_rule}' but it was not. Failing rules: {failing}"
        )
