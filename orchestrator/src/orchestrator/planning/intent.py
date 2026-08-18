"""Prompt-intent classification for the planner (ADR-0022, Phase 3b).

Half of the planner's decision context is **state facts** (has_active_ips,
has_recent_drift_report, …), read deterministically from Firestore/session by
the caller. The other half is **prompt intent** — what the user is asking for —
which needs interpreting.

v1 does this **without an LLM** (the LLM prune is deferred until over-selection
is observed), so intent comes from a *narrow, high-precision keyword heuristic*.
The heuristic drives only the **include** path (an explicit trade verb pulls in
the trade path); it never gates an exclude, because a false positive there is
free — action-drafting self-skips when there's no real drift or trade — while a
false negative on an exclude would drop a skill the user needed (recall-bias,
design §3).

Pure and deterministic: prompt text in, signals out. No I/O, no model call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Narrow, high-precision set of explicit trade-action verbs. Kept deliberately
# tight: broad words like "invest" or "purchase" are excluded to avoid firing on
# informational questions ("how should I invest?"). Whole-word, case-insensitive.
_TRADE_VERB_RE = re.compile(
    r"\b("
    r"buy|buys|buying|bought|"
    r"sell|sells|selling|sold|"
    r"trade|trades|trading|traded|"
    r"rebalance|rebalances|rebalancing|"
    r"trim|trims|trimming|trimmed|"
    r"liquidate|liquidates|liquidating|"
    r"divest|divests|divesting|"
    r"reallocate|reallocates|reallocating"
    r")\b",
    re.IGNORECASE,
)

# Question-shaped openers — used only to label coarse `intent`, never to exclude.
_QUESTION_RE = re.compile(
    r"^\s*(what|how|why|when|where|which|who|is|are|do|does|did|can|could|should|would|"
    r"tell me|show me|explain)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class IntentSignals:
    """Prompt-derived fields for the planner's decision context.

    ``requested_trade`` drives the trade-intent include rule. ``intent`` is a
    coarse label ("action" / "informational" / "unknown") kept as metadata for
    the PLAN_CONSTRUCTED audit; it does not gate any exclude in v1.
    """

    requested_trade: bool
    intent: str

    def as_context(self) -> dict:
        """The prompt-intent slice of the decision context, ready to merge with state facts."""
        return {"requested_trade": self.requested_trade, "intent": self.intent}


def classify_intent(prompt: str) -> IntentSignals:
    """Classifies a prompt's trade intent with the narrow keyword heuristic."""
    text = prompt or ""
    requested_trade = bool(_TRADE_VERB_RE.search(text))
    if requested_trade:
        intent = "action"
    elif _QUESTION_RE.search(text.strip()):
        intent = "informational"
    else:
        intent = "unknown"
    return IntentSignals(requested_trade=requested_trade, intent=intent)
