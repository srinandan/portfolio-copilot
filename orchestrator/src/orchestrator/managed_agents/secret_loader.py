"""Startup helper to resolve MANAGED_AGENT_ID from Secret Manager or environment."""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_MANAGED_AGENT_ID = "antigravity-preview-05-2026"
_CACHED_AGENT_ID: Optional[str] = None


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


def _fetch_from_secret_manager() -> Optional[str]:
    project_id = _get_project_id()
    if not project_id or project_id == "dummy-project":
        return None
    try:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/MANAGED_AGENT_ID/versions/latest"
        response = client.access_secret_version(request={"name": name})
        value = response.payload.data.decode("UTF-8").strip()
        if value:
            logger.info(f"Loaded MANAGED_AGENT_ID from Secret Manager: {value}")
            return value
    except Exception as e:
        logger.debug(f"Could not load MANAGED_AGENT_ID from Secret Manager: {e}")
    return None


def resolve_managed_agent_id(force_refresh: bool = False) -> str:
    """Resolves MANAGED_AGENT_ID checking env var, Secret Manager, then default."""
    global _CACHED_AGENT_ID

    # 1. Check environment variable first (allows overrides in dev/test/Cloud Run)
    env_val = os.environ.get("MANAGED_AGENT_ID")
    if env_val:
        return env_val

    if _CACHED_AGENT_ID is not None and not force_refresh:
        return _CACHED_AGENT_ID

    # 2. Check Secret Manager
    sm_val = _fetch_from_secret_manager()
    if sm_val:
        _CACHED_AGENT_ID = sm_val
        return _CACHED_AGENT_ID

    # 3. Fall back to placeholder default with clear warning
    logger.warning(
        f"MANAGED_AGENT_ID not set in environment or Secret Manager; "
        f"falling back to default {DEFAULT_MANAGED_AGENT_ID}"
    )
    _CACHED_AGENT_ID = DEFAULT_MANAGED_AGENT_ID
    return _CACHED_AGENT_ID


def clear_cache() -> None:
    """Clear cached ID (useful for unit testing)."""
    global _CACHED_AGENT_ID
    _CACHED_AGENT_ID = None
