import logging
import os
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.managed_agents.secret_loader import (
    DEFAULT_MANAGED_AGENT_ID,
    SecretLoadError,
    clear_cache,
    resolve_alpaca_credentials,
    resolve_managed_agent_id,
    verify_required_secrets,
)


def setup_function():
    clear_cache()


def test_resolve_from_env_var():
    with patch.dict(os.environ, {"MANAGED_AGENT_ID": "projects/test/agents/env-agent"}):
        assert resolve_managed_agent_id() == "env-agent"
        # Second call returns same value
        assert resolve_managed_agent_id() == "env-agent"


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
            assert res == "sm-agent"
            # Cached call does not call access_secret_version again
            res2 = resolve_managed_agent_id()
            assert res2 == "sm-agent"
            assert mock_client_instance.access_secret_version.call_count == 1

            # Force refresh calls again
            res3 = resolve_managed_agent_id(force_refresh=True)
            assert res3 == "sm-agent"
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


def test_resolve_alpaca_credentials_from_env():
    with patch.dict(
        os.environ,
        {"ALPACA_API_KEY_ID": "env-key-id", "ALPACA_API_SECRET": "env-secret"},
    ):
        key_id, secret = resolve_alpaca_credentials()
        assert key_id == "env-key-id"
        assert secret == "env-secret"


def test_resolve_alpaca_credentials_from_secret_manager():
    with patch.dict(
        os.environ,
        {"ALPACA_API_KEY_ID": "", "ALPACA_API_SECRET": "", "PROJECT_ID": "test-project"},
        clear=True,
    ):
        mock_client_instance = MagicMock()

        def _mock_access(request):
            name = request["name"]
            resp = MagicMock()
            if "ALPACA_API_KEY_ID" in name:
                resp.payload.data = b"sm-key-id"
            elif "ALPACA_API_SECRET" in name:
                resp.payload.data = b"sm-secret"
            else:
                resp.payload.data = b""
            return resp

        mock_client_instance.access_secret_version.side_effect = _mock_access
        with patch("google.cloud.secretmanager.SecretManagerServiceClient", return_value=mock_client_instance):
            key_id, secret = resolve_alpaca_credentials(force_refresh=True)
            assert key_id == "sm-key-id"
            assert secret == "sm-secret"
            assert os.environ["ALPACA_API_KEY_ID"] == "sm-key-id"
            assert os.environ["ALPACA_API_SECRET"] == "sm-secret"


def test_resolve_alpaca_credentials_missing_require_raises():
    with patch.dict(
        os.environ,
        {"ALPACA_API_KEY_ID": "", "ALPACA_API_SECRET": "", "PROJECT_ID": "dummy-project"},
        clear=True,
    ):
        with pytest.raises(SecretLoadError, match="Missing required Alpaca credentials"):
            resolve_alpaca_credentials(require=True)


def test_verify_required_secrets_strict_missing_agent_id_raises():
    with patch.dict(
        os.environ,
        {"MANAGED_AGENT_ID": "", "PROJECT_ID": "dummy-project"},
        clear=True,
    ):
        with pytest.raises(SecretLoadError, match="MANAGED_AGENT_ID could not be loaded"):
            verify_required_secrets(strict=True)


def test_verify_required_secrets_strict_missing_alpaca_raises():
    with patch.dict(
        os.environ,
        {
            "MANAGED_AGENT_ID": "projects/test/agents/real-id",
            "ALPACA_API_KEY_ID": "",
            "ALPACA_API_SECRET": "",
            "PROJECT_ID": "dummy-project",
        },
        clear=True,
    ):
        with pytest.raises(SecretLoadError, match="Missing required Alpaca credentials"):
            verify_required_secrets(strict=True)


def test_verify_required_secrets_strict_success():
    with patch.dict(
        os.environ,
        {
            "MANAGED_AGENT_ID": "projects/test/agents/real-id",
            "ALPACA_API_KEY_ID": "test-key",
            "ALPACA_API_SECRET": "test-secret",
        },
    ):
        verify_required_secrets(strict=True)
