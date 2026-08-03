import logging
import os
from unittest.mock import MagicMock, patch

from orchestrator.managed_agents.secret_loader import (
    DEFAULT_MANAGED_AGENT_ID,
    clear_cache,
    resolve_managed_agent_id,
)


def setup_function():
    clear_cache()


def test_resolve_from_env_var():
    with patch.dict(os.environ, {"MANAGED_AGENT_ID": "projects/test/agents/env-agent"}):
        assert resolve_managed_agent_id() == "projects/test/agents/env-agent"
        # Second call returns same value
        assert resolve_managed_agent_id() == "projects/test/agents/env-agent"


def test_resolve_from_secret_manager():
    with patch.dict(
        os.environ,
        {"MANAGED_AGENT_ID": "", "PROJECT_ID": "test-project"},
        clear=True,
    ):
        mock_client_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.payload.data = b"projects/test-project/agents/sm-agent"
        mock_client_instance.access_secret_version.return_value = mock_response

        with patch("google.cloud.secretmanager.SecretManagerServiceClient", return_value=mock_client_instance):
            res = resolve_managed_agent_id()
            assert res == "projects/test-project/agents/sm-agent"
            # Cached call does not call access_secret_version again
            res2 = resolve_managed_agent_id()
            assert res2 == "projects/test-project/agents/sm-agent"
            assert mock_client_instance.access_secret_version.call_count == 1

            # Force refresh calls again
            res3 = resolve_managed_agent_id(force_refresh=True)
            assert res3 == "projects/test-project/agents/sm-agent"
            assert mock_client_instance.access_secret_version.call_count == 2


def test_resolve_fallback_to_default_logs_warning(caplog):
    with patch.dict(
        os.environ,
        {"MANAGED_AGENT_ID": "", "PROJECT_ID": "test-project"},
        clear=True,
    ):
        with patch(
            "google.cloud.secretmanager.SecretManagerServiceClient",
            side_effect=Exception("SM not reachable"),
        ):
            with caplog.at_level(logging.WARNING):
                res = resolve_managed_agent_id()
                assert res == DEFAULT_MANAGED_AGENT_ID
                assert "MANAGED_AGENT_ID not set in environment or Secret Manager" in caplog.text
