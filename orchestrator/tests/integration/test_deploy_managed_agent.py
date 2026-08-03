import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from scripts.deploy_managed_agent import (
    find_existing_managed_agent,
    grant_iam_role,
    provision_managed_agent,
    store_secret,
)


def test_find_existing_managed_agent_found():
    mock_proc = MagicMock()
    mock_proc.stdout = json.dumps([
        {"displayName": "other-agent", "name": "projects/p/locations/l/agents/agent-1"},
        {"displayName": "portfolio-copilot-worker", "name": "projects/p/locations/l/agents/worker-12345"},
    ])

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        result = find_existing_managed_agent("p", "l", "portfolio-copilot-worker")
        assert result == "projects/p/locations/l/agents/worker-12345"
        mock_run.assert_called_once()


def test_find_existing_managed_agent_not_found():
    mock_proc = MagicMock()
    mock_proc.stdout = json.dumps([
        {"displayName": "other-agent", "name": "projects/p/locations/l/agents/agent-1"},
    ])

    with patch("subprocess.run", return_value=mock_proc):
        result = find_existing_managed_agent("p", "l", "portfolio-copilot-worker")
        assert result is None


def test_provision_managed_agent_creates_and_returns_server_id():
    # 1. Not existing
    mock_list_proc = MagicMock()
    mock_list_proc.stdout = json.dumps([])

    # 2. Create succeeds with server-assigned ID
    mock_create_proc = MagicMock()
    mock_create_proc.stdout = json.dumps({
        "name": "projects/test-proj/locations/us-central1/agents/generated-id-789",
        "displayName": "portfolio-copilot-worker",
    })

    def subprocess_side_effect(cmd, **kwargs):
        if "list" in cmd:
            return mock_list_proc
        if "create" in cmd:
            return mock_create_proc
        return MagicMock()

    with patch("subprocess.run", side_effect=subprocess_side_effect):
        result = provision_managed_agent("test-proj", "us-central1", "portfolio-copilot-worker")
        assert result == "projects/test-proj/locations/us-central1/agents/generated-id-789"


def test_provision_managed_agent_fails_loud_by_default():
    # Both list and create fail
    with patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(1, ["gcloud"], stderr="Permission denied"),
    ):
        with pytest.raises(RuntimeError, match="Failed to provision Managed Agent"):
            provision_managed_agent("test-proj", "us-central1", "portfolio-copilot-worker", allow_placeholder=False)


def test_provision_managed_agent_allow_placeholder_returns_fallback():
    # Both list and create fail, but allow_placeholder is True
    with patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(1, ["gcloud"], stderr="Permission denied"),
    ):
        result = provision_managed_agent("test-proj", "us-central1", "portfolio-copilot-worker", allow_placeholder=True)
        assert result == "projects/test-proj/locations/us-central1/agents/portfolio-copilot-worker"


def test_grant_iam_role_executes_gcloud_binding():
    with patch("subprocess.run") as mock_run:
        grant_iam_role("test-proj", "principalSet://...", "roles/secretmanager.secretAccessor")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "add-iam-policy-binding" in args
        assert "--member=principalSet://..." in args
        assert "--role=roles/secretmanager.secretAccessor" in args


def test_store_secret_via_gcloud_cli():
    mock_describe = MagicMock()
    mock_describe.returncode = 1  # Not existing

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = mock_describe
        store_secret("test-proj", "MANAGED_AGENT_ID", "projects/p/locations/l/agents/w1")
        assert mock_run.called
