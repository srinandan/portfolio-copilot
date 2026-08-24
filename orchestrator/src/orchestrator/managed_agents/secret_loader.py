"""Startup helper to resolve credentials from Secret Manager or environment."""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_MANAGED_AGENT_ID = "antigravity-preview-05-2026"
_CACHED_AGENT_ID: Optional[str] = None
_CACHED_ALPACA_KEY_ID: Optional[str] = None
_CACHED_ALPACA_SECRET: Optional[str] = None


class SecretLoadError(RuntimeError):
    """Raised when a required secret cannot be loaded from environment or Secret Manager."""


def _get_project_id() -> Optional[str]:
    project_id = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project_id:
        return project_id
    try:
        import google.auth

        _, project_id = google.auth.default()
        return project_id
    except Exception:
        return None


def _fetch_from_secret_manager(secret_name: str) -> Optional[str]:
    project_id = _get_project_id()
    if not project_id or project_id == "dummy-project":
        return None
    try:
        from google.cloud import secretmanager

        # In test environments, never make real GCP Secret Manager network calls unless the client is mocked
        if "PYTEST_CURRENT_TEST" in os.environ:
            from unittest.mock import Mock

            if not isinstance(secretmanager.SecretManagerServiceClient, Mock) and not hasattr(
                secretmanager.SecretManagerServiceClient, "return_value"
            ):
                return None

        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        value = response.payload.data.decode("UTF-8").strip()
        if value:
            logger.info(f"Loaded {secret_name} from Secret Manager")
            return value
    except Exception as e:
        logger.debug(f"Could not load {secret_name} from Secret Manager: {e}")
    return None


def _normalize_agent_id(val: str) -> str:
    """Ensures agent_id is compatible with interactions API."""
    trimmed = val.strip()
    if "/" in trimmed:
        short = trimmed.split("/")[-1]
    else:
        short = trimmed
    if short in ("portfolio-copilot-worker", "worker", "portfolio-worker"):
        return DEFAULT_MANAGED_AGENT_ID
    return short


def resolve_managed_agent_id(force_refresh: bool = False) -> str:
    """Resolves MANAGED_AGENT_ID checking env var, Secret Manager, then default."""
    global _CACHED_AGENT_ID

    # 1. Check environment variable first (allows overrides in dev/test/Cloud Run)
    env_val = os.environ.get("MANAGED_AGENT_ID")
    if env_val:
        _CACHED_AGENT_ID = _normalize_agent_id(env_val)
        return _CACHED_AGENT_ID

    if _CACHED_AGENT_ID is not None and not force_refresh:
        return _CACHED_AGENT_ID

    # 2. Check Secret Manager
    sm_val = _fetch_from_secret_manager("MANAGED_AGENT_ID")
    if sm_val:
        _CACHED_AGENT_ID = _normalize_agent_id(sm_val)
        return _CACHED_AGENT_ID

    # 3. Fall back to placeholder default with clear warning
    logger.warning(
        f"MANAGED_AGENT_ID not set in environment or Secret Manager; falling back to default {DEFAULT_MANAGED_AGENT_ID}"
    )
    _CACHED_AGENT_ID = DEFAULT_MANAGED_AGENT_ID
    return _CACHED_AGENT_ID



def resolve_alpaca_credentials(force_refresh: bool = False, require: bool = False) -> tuple[str, str]:
    """Resolves ALPACA_API_KEY_ID and ALPACA_API_SECRET checking env var, Secret Manager, and sets env vars.

    Args:
        force_refresh: If True, bypasses existing cache/env and queries Secret Manager.
        require: If True, raises SecretLoadError if either credential cannot be resolved.

    Returns:
        tuple[str, str]: (key_id, secret)

    Raises:
        SecretLoadError: If require is True and either credential is missing.
    """
    global _CACHED_ALPACA_KEY_ID, _CACHED_ALPACA_SECRET

    key_id = os.environ.get("ALPACA_API_KEY_ID", "").strip() if not force_refresh else ""
    secret = os.environ.get("ALPACA_API_SECRET", "").strip() if not force_refresh else ""

    if key_id and secret and not force_refresh:
        _CACHED_ALPACA_KEY_ID = key_id
        _CACHED_ALPACA_SECRET = secret
        return key_id, secret

    if (
        _CACHED_ALPACA_KEY_ID
        and _CACHED_ALPACA_SECRET
        and not force_refresh
        and "PYTEST_CURRENT_TEST" not in os.environ
    ):
        return _CACHED_ALPACA_KEY_ID, _CACHED_ALPACA_SECRET

    if not key_id:
        val = _fetch_from_secret_manager("ALPACA_API_KEY_ID")
        if val:
            key_id = val

    if not secret:
        val = _fetch_from_secret_manager("ALPACA_API_SECRET")
        if val:
            secret = val

    if key_id and secret:
        os.environ["ALPACA_API_KEY_ID"] = key_id
        os.environ["ALPACA_API_SECRET"] = secret
        _CACHED_ALPACA_KEY_ID = key_id
        _CACHED_ALPACA_SECRET = secret
        return key_id, secret

    if require:
        raise SecretLoadError(
            "Missing required Alpaca credentials: ALPACA_API_KEY_ID and/or "
            "ALPACA_API_SECRET not found in environment or Secret Manager."
        )

    return key_id, secret


def verify_required_secrets(strict: bool = False) -> None:
    """Verifies at startup that required secrets can be resolved.

    Checks MANAGED_AGENT_ID, ALPACA_API_KEY_ID, and ALPACA_API_SECRET.
    In strict mode (strict=True or PORTFOLIO_COPILOT_STRICT_SECRETS=true, or in Agent Runtime),
    raises SecretLoadError if any required secret cannot be loaded.
    """
    is_strict = (
        strict
        or os.environ.get("PORTFOLIO_COPILOT_STRICT_SECRETS", "").lower() == "true"
        or (
            os.environ.get("PROJECT_ID")
            and os.environ.get("PROJECT_ID") != "dummy-project"
            and not os.environ.get("PYTEST_CURRENT_TEST")
        )
    )

    agent_id = resolve_managed_agent_id()
    if is_strict and (not agent_id or agent_id == DEFAULT_MANAGED_AGENT_ID):
        raise SecretLoadError(
            f"Startup validation failed: MANAGED_AGENT_ID could not be loaded "
            f"from environment or Secret Manager (got default {DEFAULT_MANAGED_AGENT_ID})."
        )

    try:
        resolve_alpaca_credentials(require=is_strict)
    except SecretLoadError as e:
        raise SecretLoadError(f"Startup validation failed: {e}") from e


def clear_cache() -> None:
    """Clear cached IDs and credentials (useful for unit testing)."""
    global _CACHED_AGENT_ID, _CACHED_ALPACA_KEY_ID, _CACHED_ALPACA_SECRET
    _CACHED_AGENT_ID = None
    _CACHED_ALPACA_KEY_ID = None
    _CACHED_ALPACA_SECRET = None
