#!/usr/bin/env python3
"""Loads canonical test and seed data fixtures into Google Cloud BigQuery and Firestore.

Usage:
  python3 scripts/load_test_data.py [--project PROJECT_ID] [--location LOCATION] [--dry-run]
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import jsonschema

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTDATA_DIR = REPO_ROOT / "testdata"
SCHEMAS_DIR = REPO_ROOT / "schemas"


def load_json(filepath: Path) -> Any:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_fixtures() -> None:
    """Validates all canonical test fixtures against repository schemas."""
    print("Validating test fixtures against schemas...")

    schema_map = {
        "holdings.json": "holdings.schema.json",
        "liabilities.json": "liabilities.schema.json",
        "ips.json": "ips.schema.json",
        "spending_report.json": "spending-report.schema.json",
        "drift_report.json": "drift-report.schema.json",
        "checking_transactions.json": "account-transaction.schema.json",
        "chase_transactions.json": "account-transaction.schema.json",
    }

    for fixture_name, schema_name in schema_map.items():
        fixture_path = TESTDATA_DIR / fixture_name
        schema_path = SCHEMAS_DIR / schema_name

        if not fixture_path.exists():
            raise FileNotFoundError(f"Fixture file not found: {fixture_path}")
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        fixture_data = load_json(fixture_path)
        schema_data = load_json(schema_path)

        if isinstance(fixture_data, list):
            for i, item in enumerate(fixture_data):
                jsonschema.validate(instance=item, schema=schema_data)
        else:
            jsonschema.validate(instance=fixture_data, schema=schema_data)

        print(f"  ✓ {fixture_name} matches {schema_name}")

    # Validate poisoned research payload has required fields
    poisoned_path = TESTDATA_DIR / "poisoned_research.json"
    if not poisoned_path.exists():
        raise FileNotFoundError(f"Poisoned research fixture missing: {poisoned_path}")
    poisoned_data = load_json(poisoned_path)
    assert "ticker" in poisoned_data, "Poisoned research must specify target ticker"
    assert "adversarial_prompt_injection" in poisoned_data, "Poisoned research must specify prompt injection"
    print("  ✓ poisoned_research.json verified")


def get_default_project() -> str:
    project = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project:
        return project
    try:
        res = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True,
            text=True,
            check=True,
        )
        project = res.stdout.strip()
        if project and project != "(unset)":
            return project
    except Exception:
        pass
    return "demo-project"


def seed_bigquery(project_id: str, location: str, dataset_name: str, table_name: str, dry_run: bool) -> None:
    csv_file = TESTDATA_DIR / f"{table_name}.csv"
    if not csv_file.exists():
        # Fallback to checking_transactions.csv or chase_transactions.csv
        csv_file = TESTDATA_DIR / "checking_transactions.csv"
        if not csv_file.exists():
            csv_file = TESTDATA_DIR / "chase_transactions.csv"
    table_id = f"{project_id}.{dataset_name}.{table_name}"
    print(f"\n[BigQuery] Seeding {csv_file.name} -> {table_id} (location: {location})...")

    if dry_run:
        print(f"  [DRY-RUN] Would load {csv_file} into BigQuery table {table_id}")
        return

    try:
        from google.cloud import bigquery

        client = bigquery.Client(project=project_id)
        dataset_ref = bigquery.DatasetReference(project_id, dataset_name)

        # Ensure dataset exists and obtain its actual location
        try:
            dataset = client.get_dataset(dataset_ref)
            ds_location = dataset.location
        except Exception:
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = location
            dataset.labels = {"app": "portfolio-copilot"}
            dataset = client.create_dataset(dataset, exists_ok=True)
            ds_location = dataset.location
            print(f"  Created dataset {dataset_name}")

        client = bigquery.Client(project=project_id, location=ds_location)

        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            autodetect=False,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            schema=[
                bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("transaction_date", "DATE", mode="REQUIRED"),
                bigquery.SchemaField("amount", "FLOAT64", mode="REQUIRED"),
                bigquery.SchemaField("description", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("raw_category", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("normalized_category", "STRING", mode="REQUIRED"),
            ],
        )

        with open(csv_file, "rb") as source_file:
            job = client.load_table_from_file(source_file, table_id, job_config=job_config)
        job.result()
        print(f"  ✓ BigQuery load completed: {job.output_rows} rows loaded into {table_id}")

    except ImportError:
        # Fallback to bq CLI
        print("  google-cloud-bigquery package not installed, falling back to bq CLI...")
        cmd = [
            "bq",
            "load",
            f"--project_id={project_id}",
            f"--location={location}",
            "--source_format=CSV",
            "--skip_leading_rows=1",
            "--replace",
            f"{dataset_name}.{table_name}",
            str(csv_file),
            "user_id:STRING,transaction_date:DATE,amount:FLOAT64,description:STRING,raw_category:STRING,normalized_category:STRING",
        ]
        subprocess.run(cmd, check=True)
        print(f"  ✓ bq load completed into {table_id}")


def seed_firestore(project_id: str, location: str, dry_run: bool) -> None:
    print(
        f"\n[Firestore] Seeding IPS, Holdings, Liabilities, Spending Report, and Drift Report into project {project_id}..."
    )

    ips_data = load_json(TESTDATA_DIR / "ips.json")
    holdings_data = load_json(TESTDATA_DIR / "holdings.json")
    liabilities_data = load_json(TESTDATA_DIR / "liabilities.json")
    spending_report_data = load_json(TESTDATA_DIR / "spending_report.json")
    drift_report_data = load_json(TESTDATA_DIR / "drift_report.json")

    user_id = ips_data["user_id"]
    ips_id = ips_data["ips_id"]
    ips_doc_id = f"{ips_id}_v{ips_data['version']}"

    if dry_run:
        print(f"  [DRY-RUN] Would write ips/{ips_doc_id} for user '{user_id}'")
        print(f"  [DRY-RUN] Would write holdings/{user_id}")
        print(f"  [DRY-RUN] Would write liabilities/{user_id}")
        print(f"  [DRY-RUN] Would write spending_reports/{user_id}")
        print(f"  [DRY-RUN] Would write drift_reports/{user_id}")
        return

    try:
        from google.auth.credentials import AnonymousCredentials
        from google.cloud import firestore

        emulator_host = os.environ.get("FIRESTORE_EMULATOR_HOST")
        if emulator_host:
            db = firestore.Client(project=project_id, credentials=AnonymousCredentials())
        else:
            db = firestore.Client(project=project_id)

        # Write IPS
        db.collection("ips").document(ips_doc_id).set(ips_data)
        print(f"  ✓ Written IPS document: ips/{ips_doc_id}")

        # Write Holdings
        db.collection("holdings").document(user_id).set(holdings_data)
        print(f"  ✓ Written Holdings document: holdings/{user_id}")

        # Write Liabilities
        db.collection("liabilities").document(user_id).set(liabilities_data)
        print(f"  ✓ Written Liabilities document: liabilities/{user_id}")

        # Write Spending Report
        db.collection("spending_reports").document(user_id).set(spending_report_data)
        print(f"  ✓ Written Spending Report document: spending_reports/{user_id}")

        # Write Drift Report
        db.collection("drift_reports").document(user_id).set(drift_report_data)
        print(f"  ✓ Written Drift Report document: drift_reports/{user_id}")

    except Exception as e:
        print(f"  ✗ Error seeding Firestore: {e}", file=sys.stderr)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed canonical test fixtures into GCP BigQuery and Firestore.")
    parser.add_argument(
        "--project", default=None, help="GCP project ID (default: gcloud config project or PROJECT_ID env)"
    )
    parser.add_argument("--location", default="us-central1", help="GCP region/location (default: us-central1)")
    parser.add_argument(
        "--dataset", default="portfolio_copilot", help="BigQuery dataset name (default: portfolio_copilot)"
    )
    parser.add_argument(
        "--table", default="checking_transactions", help="BigQuery table name (default: checking_transactions)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate fixtures without uploading to GCP")

    args = parser.parse_args()
    project_id = args.project or get_default_project()

    print("==================================================")
    print("Portfolio Copilot - Seed Test Data Loader")
    print(f"Project ID: {project_id}")
    print(f"Location:   {args.location}")
    print(f"Dry Run:    {args.dry_run}")
    print("==================================================")

    # 1. Validate fixtures
    validate_fixtures()

    # 2. Seed BigQuery
    seed_bigquery(
        project_id=project_id,
        location=args.location,
        dataset_name=args.dataset,
        table_name=args.table,
        dry_run=args.dry_run,
    )

    # 3. Seed Firestore
    seed_firestore(
        project_id=project_id,
        location=args.location,
        dry_run=args.dry_run,
    )

    print("\n✓ Test data seeding finished successfully!")


if __name__ == "__main__":
    main()
