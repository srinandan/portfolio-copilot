import json
from pathlib import Path
from unittest.mock import MagicMock

import jsonschema

from orchestrator.contracts.drift_report import DriftReport, DriftReportEntry
from orchestrator.data.firestore import FirestoreClient
from orchestrator.state.writers import write_drift_report


def test_write_drift_report_persists_to_firestore():
    mock_client = MagicMock()
    report = DriftReport(
        user_id="user_123",
        as_of="2026-08-01T00:00:00Z",
        bands=[
            DriftReportEntry(
                asset_class="Equity",
                current_percent=67.5,
                target_percent=60.0,
                min_percent=50.0,
                max_percent=65.0,
                in_band=False,
                drift_amount_percent=2.5,
            )
        ],
        unclassified_value_usd=10000.0,
        rebalance_recommended=True,
        has_active_ips=True,
    )

    write_drift_report(
        user_id="user_123",
        report=report,
        db_client=mock_client,
    )

    mock_client.set_drift_report.assert_called_once_with("user_123", report)


def test_drift_report_serialized_shape_matches_schema():
    client = FirestoreClient(project="test-project")
    report = DriftReport(
        user_id="user_123",
        as_of="2026-08-01T00:00:00Z",
        bands=[
            DriftReportEntry(
                asset_class="Equity",
                current_percent=67.5,
                target_percent=60.0,
                min_percent=50.0,
                max_percent=65.0,
                in_band=False,
                drift_amount_percent=2.5,
            )
        ],
        unclassified_value_usd=10000.0,
        rebalance_recommended=True,
        has_active_ips=True,
    )

    serialized = client._dict_factory(report)
    assert "bands" in serialized
    assert serialized["bands"][0]["asset_class"] == "Equity"
    assert serialized["rebalance_recommended"] is True

    schema_path = Path(__file__).resolve().parent.parent.parent.parent / "schemas" / "drift-report.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    jsonschema.validate(instance=serialized, schema=schema)
