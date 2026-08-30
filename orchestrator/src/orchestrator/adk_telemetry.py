"""Opt-in wiring for ADK's native per-request telemetry (ADR-0019, #364).

ADK 2.8.0 emits per-invocation **token-spend** and per-workflow inference /
tool-call metrics, gated behind experimental telemetry (default OFF). This
module threads that opt-in through ``RunConfig`` at the Runner call sites, so it
is a code-controlled, testable setting rather than a bare process-global env
var — the orchestrator decides per deploy whether to emit the extra telemetry.

Default OFF. :func:`build_adk_run_config` returns ``None`` (``run_async`` uses
its own default ``RunConfig``) unless ``ORCHESTRATOR_ADK_TELEMETRY_ENABLED`` is
truthy. When enabled it returns a ``RunConfig`` carrying
``TelemetryConfig(adk_experimental_telemetry_opt_in=True)``, turning on the
experimental token-spend / workflow metrics for the invocation. Those metrics
export through the OTel MeterProvider the server's telemetry setup already
installs; this module only flips the per-request opt-in, it does not change the
existing hand-rolled spans (that reconciliation is a separate, larger step).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

from .logger import get_logger

if TYPE_CHECKING:
    from google.adk.agents.run_config import RunConfig

logger = get_logger(__name__)

ADK_TELEMETRY_ENABLED_ENV = "ORCHESTRATOR_ADK_TELEMETRY_ENABLED"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def adk_telemetry_enabled() -> bool:
    """Whether the ADK experimental-telemetry opt-in is turned on for this deploy."""
    return _env_bool(ADK_TELEMETRY_ENABLED_ENV)


def build_adk_run_config() -> Optional["RunConfig"]:
    """Builds the per-request ``RunConfig`` that opts into ADK experimental telemetry.

    Returns ``None`` when disabled (the default), so callers can pass the result
    straight to ``run_async(run_config=...)`` — ``None`` selects ``run_async``'s
    own default config. Never raises: if the telemetry types are unavailable the
    opt-in degrades to "default telemetry", logged, rather than failing the run.
    """
    if not adk_telemetry_enabled():
        return None
    try:
        from google.adk.agents.run_config import RunConfig
        from google.adk.telemetry import TelemetryConfig
    except ImportError:
        logger.exception("ADK telemetry opt-in requested but telemetry types are unavailable; using default RunConfig.")
        return None

    logger.info(
        "ADK experimental telemetry enabled via RunConfig (%s): per-invocation token-spend + per-workflow metrics.",
        ADK_TELEMETRY_ENABLED_ENV,
    )
    return RunConfig(telemetry=TelemetryConfig(adk_experimental_telemetry_opt_in=True))
