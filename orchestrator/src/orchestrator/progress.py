"""Out-of-band progress channel for streaming pipeline status to the frontend.

An analysis run takes 2-4 minutes. Without feedback the frontend shows a single
frozen line for the whole duration. This module lets the planner surface
human-meaningful stage transitions (a skill starting, completing, or being
skipped) as lightweight events that the streaming layer interleaves with the
ADK Runner's own events on the same SSE stream.

Mechanism
---------
The FastAPI streaming layer (`server._interleave_progress`) installs a per-run
``asyncio.Queue`` on the :data:`PROGRESS_CHANNEL` context variable. The planner
calls :func:`report_progress` at each checkpoint; the call puts a progress dict
onto that queue, from where the streaming layer drains it into the wire stream
in real arrival order. When no channel is installed (non-streaming code paths,
unit tests) the call is a silent no-op.

Authority
---------
Progress events are advisory UI signals ONLY. They never gate execution and
carry no governance weight, unlike the immutable Firestore audit log written by
``state/writers.py`` (SKILL_INVOKED, ACTION_PROPOSED, ...). Dropping a progress
event changes nothing but the UI; dropping an audit entry is fail-closed. Keep
the two concerns separate.

Wire shape
----------
Each progress event is a JSON object::

    {"kind": "progress", "stage": "portfolio-analysis",
     "status": "running", "label": "Analyzing portfolio drift",
     "detail": "US equities 8% over target"}   # detail optional

``stage`` is a stable identifier the frontend keys its stepper rows on;
``status`` is one of :data:`PROGRESS_STATUSES`.
"""

import contextvars
from asyncio import Queue
from typing import Any, Dict, Optional

from .logger import get_logger

logger = get_logger(__name__)

PROGRESS_CHANNEL: contextvars.ContextVar[Optional["Queue[Any]"]] = contextvars.ContextVar(
    "progress_channel", default=None
)

PROGRESS_KIND = "progress"

# Valid status transitions for a stage row in the frontend stepper.
PROGRESS_STATUSES = ("running", "done", "skipped", "failed")

# Ordered, user-facing labels for every pipeline stage the planner can surface.
# Stage ids match the short skill name (without the "private-" prefix) plus the
# built-in orchestrator stages (discovery, approval, execution).
STAGE_LABELS: Dict[str, str] = {
    "discovery": "Discovering authorized skills",
    "spending-analysis": "Analyzing spending",
    "goals-onboarding": "Reviewing goals & policy",
    "portfolio-analysis": "Analyzing portfolio drift",
    "research": "Researching market context",
    "action-drafting": "Drafting proposed action",
    "reviewer": "Running compliance review",
    "approval": "Awaiting your approval",
    "execution": "Placing order",
}


def _stage_id(skill_short_name: str) -> str:
    """Normalizes a skill name (``private-portfolio-analysis`` or ``portfolio-analysis``)
    to its stage id (``portfolio-analysis``)."""
    base = skill_short_name.split("/")[-1] if "/" in skill_short_name else skill_short_name
    return base[len("private-") :] if base.startswith("private-") else base


def stage_label(stage: str) -> str:
    """Returns the user-facing label for a stage id, prettifying unknown ids."""
    if stage in STAGE_LABELS:
        return STAGE_LABELS[stage]
    return stage.replace("-", " ").replace("_", " ").strip().capitalize()


def report_progress(
    stage: str,
    status: str,
    label: Optional[str] = None,
    *,
    detail: Optional[str] = None,
) -> None:
    """Emits a progress event onto the installed channel, if any.

    Safe to call from anywhere in the planning pipeline, including inside
    ``asyncio.gather`` sub-tasks (the context variable propagates to tasks
    created within the run's context). Never raises into the caller: a missing
    or full channel degrades to no feedback, not a failed analysis.
    """
    queue = PROGRESS_CHANNEL.get()
    if queue is None:
        return
    if status not in PROGRESS_STATUSES:
        logger.debug("report_progress: unknown status %r for stage %r", status, stage)
    event: Dict[str, Any] = {
        "kind": PROGRESS_KIND,
        "stage": stage,
        "status": status,
        "label": label or stage_label(stage),
    }
    if detail:
        event["detail"] = detail
    try:
        queue.put_nowait(event)
    except Exception:
        # An unbounded queue effectively never rejects; guard anyway so a
        # progress hiccup can never abort the analysis it's describing.
        logger.debug("progress channel unavailable; dropping event for stage %r", stage, exc_info=True)


def report_skill_progress(
    skill_short_name: str,
    status: str,
    *,
    detail: Optional[str] = None,
) -> None:
    """Convenience wrapper: reports progress for a skill turn, deriving the
    stage id and label from the skill name."""
    stage = _stage_id(skill_short_name)
    report_progress(stage, status, stage_label(stage), detail=detail)
