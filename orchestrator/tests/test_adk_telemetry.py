"""Tests for the ADK experimental-telemetry opt-in wiring (ADR-0019, #364)."""

import pytest

from orchestrator.adk_telemetry import (
    ADK_TELEMETRY_ENABLED_ENV,
    adk_telemetry_enabled,
    build_adk_run_config,
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv(ADK_TELEMETRY_ENABLED_ENV, raising=False)


def test_disabled_by_default():
    assert adk_telemetry_enabled() is False
    # None so callers can pass it straight to run_async(run_config=...).
    assert build_adk_run_config() is None


@pytest.mark.parametrize("value", ["true", "1", "yes", "on", "TRUE", "On"])
def test_enabled_truthy_values(monkeypatch, value):
    monkeypatch.setenv(ADK_TELEMETRY_ENABLED_ENV, value)
    assert adk_telemetry_enabled() is True


@pytest.mark.parametrize("value", ["false", "0", "no", "", "off"])
def test_disabled_falsy_values(monkeypatch, value):
    monkeypatch.setenv(ADK_TELEMETRY_ENABLED_ENV, value)
    assert adk_telemetry_enabled() is False
    assert build_adk_run_config() is None


def test_enabled_builds_run_config_opting_into_experimental(monkeypatch):
    monkeypatch.setenv(ADK_TELEMETRY_ENABLED_ENV, "true")

    run_config = build_adk_run_config()

    assert run_config is not None
    assert run_config.telemetry is not None
    assert run_config.telemetry.adk_experimental_telemetry_opt_in is True
