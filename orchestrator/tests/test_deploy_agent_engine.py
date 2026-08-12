import sys
from pathlib import Path

# Add scripts directory to sys.path
scripts_dir = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from deploy_agent_engine import AGENT_IDENTITY_ROLES


def test_agent_identity_roles_includes_cloud_trace():
    """Verifies that AGENT_IDENTITY_ROLES includes roles/cloudtrace.agent for OpenTelemetry emission."""
    assert "roles/cloudtrace.agent" in AGENT_IDENTITY_ROLES
    assert "roles/datastore.user" in AGENT_IDENTITY_ROLES
    assert "roles/bigquery.dataViewer" in AGENT_IDENTITY_ROLES
    assert "roles/logging.logWriter" in AGENT_IDENTITY_ROLES
    assert "roles/monitoring.metricWriter" in AGENT_IDENTITY_ROLES
