import json
from unittest.mock import MagicMock, patch

from scripts.deploy_managed_agent import (
    find_existing_managed_agent,
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


def test_store_secret_via_gcloud_cli():
    mock_describe = MagicMock()
    mock_describe.returncode = 1  # Not existing

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = mock_describe
        store_secret("test-proj", "MANAGED_AGENT_ID", "projects/p/locations/l/agents/w1")
        assert mock_run.called
