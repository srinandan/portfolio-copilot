import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add scripts directory to sys.path
scripts_dir = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

import model_armor_floor_settings


def test_build_floor_setting_payload_defaults():
    """Golden path: default floor setting payload matches Portfolio Copilot specification."""
    payload = model_armor_floor_settings.build_floor_setting_payload()

    assert payload["enableFloorSettingEnforcement"] is True
    assert payload["integratedServices"] == ["AI_PLATFORM", "GOOGLE_MCP_SERVER"]
    assert payload["aiPlatformFloorSetting"] == {"inspectOnly": True, "enableCloudLogging": True}
    assert payload["googleMcpServerFloorSetting"] == {"inspectOnly": True, "enableCloudLogging": True}
    assert payload["floorSettingMetadata"]["multiLanguageDetection"]["enableMultiLanguageDetection"] is True

    filter_cfg = payload["filterConfig"]
    assert filter_cfg["sdpSettings"]["basicConfig"]["filterEnforcement"] == "ENABLED"
    assert filter_cfg["maliciousUriFilterSettings"]["filterEnforcement"] == "ENABLED"
    assert filter_cfg["piAndJailbreakFilterSettings"]["filterEnforcement"] == "ENABLED"
    assert filter_cfg["piAndJailbreakFilterSettings"]["confidenceLevel"] == "MEDIUM_AND_ABOVE"

    rai_filters = filter_cfg["raiSettings"]["raiFilters"]
    assert len(rai_filters) == 4
    filter_types = {f["filterType"] for f in rai_filters}
    assert filter_types == {"HATE_SPEECH", "DANGEROUS", "SEXUALLY_EXPLICIT", "HARASSMENT"}
    for f in rai_filters:
        assert f["confidenceLevel"] == "HIGH"


def test_build_floor_setting_payload_custom_enforcement_and_mode():
    """Verifies custom enforcement disabled and INSPECT_AND_BLOCK mode."""
    payload = model_armor_floor_settings.build_floor_setting_payload(
        enable_enforcement=False,
        enforcement_mode="INSPECT_AND_BLOCK",
        enable_cloud_logging=False,
        multi_language=False,
        rai_confidence="MEDIUM_AND_ABOVE",
        pi_confidence="HIGH",
    )

    assert payload["enableFloorSettingEnforcement"] is False
    assert payload["aiPlatformFloorSetting"]["inspectOnly"] is False
    assert payload["aiPlatformFloorSetting"]["enableCloudLogging"] is False
    assert payload["googleMcpServerFloorSetting"]["inspectOnly"] is False
    assert payload["floorSettingMetadata"]["multiLanguageDetection"]["enableMultiLanguageDetection"] is False
    assert payload["filterConfig"]["piAndJailbreakFilterSettings"]["confidenceLevel"] == "HIGH"


def test_get_auth_headers():
    """Verifies ADC auth headers construction."""
    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.token = "mock-token-xyz"

    with patch("google.auth.default", return_value=(mock_creds, "test-proj")):
        headers = model_armor_floor_settings.get_auth_headers()
        mock_creds.refresh.assert_called_once()
        assert headers["Authorization"] == "Bearer mock-token-xyz"
        assert headers["Content-Type"] == "application/json"


def test_get_default_project(monkeypatch):
    """Verifies default project resolution from env or ADC."""
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
    assert model_armor_floor_settings.get_default_project() == "env-project"

    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.setenv("PROJECT_ID", "env-proj-2")
    assert model_armor_floor_settings.get_default_project() == "env-proj-2"

    monkeypatch.delenv("PROJECT_ID", raising=False)
    with patch("google.auth.default", return_value=(MagicMock(), "adc-proj")):
        assert model_armor_floor_settings.get_default_project() == "adc-proj"


def test_get_floor_setting_success():
    """Verifies GET floorSetting call."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "name": "projects/p1/locations/global/floorSetting",
        "enableFloorSettingEnforcement": True,
    }

    with (
        patch("model_armor_floor_settings.get_auth_headers", return_value={"Authorization": "Bearer tok"}),
        patch("httpx.Client.get", return_value=mock_resp),
    ):
        result = model_armor_floor_settings.get_floor_setting("p1")
        assert result["enableFloorSettingEnforcement"] is True


def test_get_floor_setting_not_found():
    """Verifies 404 returns empty dict."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with (
        patch("model_armor_floor_settings.get_auth_headers", return_value={"Authorization": "Bearer tok"}),
        patch("httpx.Client.get", return_value=mock_resp),
    ):
        assert model_armor_floor_settings.get_floor_setting("p1") == {}


def test_update_floor_setting_success():
    """Verifies PATCH floorSetting call with updateMask."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "name": "projects/p1/locations/global/floorSetting",
        "enableFloorSettingEnforcement": True,
    }

    with (
        patch("model_armor_floor_settings.get_auth_headers", return_value={"Authorization": "Bearer tok"}),
        patch("httpx.Client.patch", return_value=mock_resp) as mock_patch,
    ):
        result = model_armor_floor_settings.update_floor_setting("p1", enable_enforcement=True)
        assert result["name"] == "projects/p1/locations/global/floorSetting"
        assert mock_patch.called
        call_kwargs = mock_patch.call_args.kwargs
        assert "updateMask" in call_kwargs["params"]


def test_main_cli_describe(capsys):
    """Verifies CLI --describe flag."""
    sample_data = {"name": "projects/demo-p/locations/global/floorSetting", "enableFloorSettingEnforcement": True}
    with patch("model_armor_floor_settings.get_floor_setting", return_value=sample_data):
        exit_code = model_armor_floor_settings.main(["--project=demo-p", "--describe"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "demo-p" in captured.out


def test_main_cli_update_apply(capsys):
    """Verifies CLI update/apply invocation."""
    sample_data = {"name": "projects/demo-p/locations/global/floorSetting", "enableFloorSettingEnforcement": True}
    with patch("model_armor_floor_settings.update_floor_setting", return_value=sample_data):
        exit_code = model_armor_floor_settings.main(["--project=demo-p", "--mode=INSPECT_AND_BLOCK"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Successfully configured Model Armor" in captured.out


def test_main_cli_missing_project(monkeypatch, capsys):
    """Verifies CLI failure on missing project ID."""
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("PROJECT_ID", raising=False)
    with patch("model_armor_floor_settings.get_default_project", return_value=""):
        exit_code = model_armor_floor_settings.main([])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Project ID must be specified" in captured.err


def test_main_cli_exception_handling(capsys):
    """Verifies error handling on network or API failure."""
    with patch("model_armor_floor_settings.update_floor_setting", side_effect=RuntimeError("Permission Denied")):
        exit_code = model_armor_floor_settings.main(["--project=demo-p"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Error managing Model Armor floor settings" in captured.err
