import json
import os
from unittest.mock import mock_open, patch

from orchestrator.mtls_setup import setup_workload_mtls


def test_setup_workload_mtls_no_files():
    with patch("os.path.exists", return_value=False):
        assert setup_workload_mtls() is False


def test_setup_workload_mtls_with_spiffe_files(tmp_path):
    cert_path = str(tmp_path / "certificates.pem")
    key_path = str(tmp_path / "private_key.pem")
    out_config = str(tmp_path / "config.json")

    def mock_exists(path):
        return path in (cert_path, key_path)

    with (
        patch("orchestrator.mtls_setup.WELL_KNOWN_SPIFFE_CERT", cert_path),
        patch("orchestrator.mtls_setup.WELL_KNOWN_SPIFFE_KEY", key_path),
        patch("orchestrator.mtls_setup.GENERATED_CERT_CONFIG", out_config),
        patch("os.path.exists", side_effect=mock_exists),
        patch.dict(os.environ, {}, clear=True),
    ):
        res = setup_workload_mtls()
        assert res is True
        assert os.environ.get("GOOGLE_API_CERTIFICATE_CONFIG") == out_config
        assert os.environ.get("GOOGLE_API_USE_CLIENT_CERTIFICATE") == "true"
        with open(out_config, "r") as f:
            data = json.load(f)
            assert data["cert_configs"]["workload"]["cert_path"] == cert_path
            assert data["cert_configs"]["workload"]["key_path"] == key_path
