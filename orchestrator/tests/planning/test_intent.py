"""Tests for the keyword intent classifier (ADR-0022, Phase 3b)."""

import pytest

from orchestrator.planning import classify_intent

TRADE_PROMPTS = [
    "should I trim my tech exposure?",
    "buy 10 shares of VTI",
    "sell my NVDA position",
    "can you rebalance my portfolio?",
    "I want to liquidate some bonds",
    "divest from fossil fuels",
    "reallocate toward international equities",
]

NON_TRADE_PROMPTS = [
    "what did I spend on dining last month?",
    "how is my portfolio doing?",
    "what's my current asset allocation?",
    "explain my drift report",
    "how much do I have in cash?",
]


@pytest.mark.parametrize("prompt", TRADE_PROMPTS)
def test_trade_prompts_flag_requested_trade(prompt):
    sig = classify_intent(prompt)
    assert sig.requested_trade is True
    assert sig.intent == "action"


@pytest.mark.parametrize("prompt", NON_TRADE_PROMPTS)
def test_non_trade_prompts_do_not_flag_trade(prompt):
    sig = classify_intent(prompt)
    assert sig.requested_trade is False


def test_question_shaped_prompt_is_informational():
    assert classify_intent("what did I spend on dining?").intent == "informational"


def test_non_question_non_trade_is_unknown():
    assert classify_intent("dining summary").intent == "unknown"


def test_whole_word_matching_avoids_false_positives():
    # "buyer" / "overselling" must not trip the trade verbs.
    assert classify_intent("who is the biggest buyer of treasuries?").requested_trade is False
    assert classify_intent("am I overselling my risk tolerance?").requested_trade is False


def test_empty_prompt_is_safe():
    sig = classify_intent("")
    assert sig.requested_trade is False
    assert sig.intent == "unknown"


def test_as_context_shape():
    ctx = classify_intent("sell NVDA").as_context()
    assert ctx == {"requested_trade": True, "intent": "action", "requested_equity_analysis": False}


# --- Equity-advice intent (issue #344) ------------------------------------- #

EQUITY_ADVICE_PROMPTS = [
    "should I buy more AAPL now?",
    "is AAPL a good buy?",
    "is it worth buying TSLA?",
    "should I invest in NVDA?",
    "what's AAPL's valuation?",
    "do you think I should sell my MSFT?",
]

NON_EQUITY_ADVICE_PROMPTS = [
    "should I trim my tech exposure?",  # portfolio-level, not single-name
    "sell my NVDA position",  # imperative command, not advice-shaped
    "how is my portfolio doing?",
    "what did I spend on dining last month?",
    "rebalance my portfolio",
]


@pytest.mark.parametrize("prompt", EQUITY_ADVICE_PROMPTS)
def test_equity_advice_prompts_flag_analysis(prompt):
    assert classify_intent(prompt).requested_equity_analysis is True


@pytest.mark.parametrize("prompt", NON_EQUITY_ADVICE_PROMPTS)
def test_non_equity_advice_prompts_do_not_flag_analysis(prompt):
    assert classify_intent(prompt).requested_equity_analysis is False
