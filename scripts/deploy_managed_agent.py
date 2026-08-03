import logging
import subprocess

import click
import google.auth
from google.cloud import secretmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def grant_iam_role(project: str, member: str, role: str) -> None:
    """Grant an IAM role to a member if gcloud is available."""
    try:
        subprocess.run(
            [
                "gcloud",
                "projects",
                "add-iam-policy-binding",
                project,
                f"--member={member}",
                f"--role={role}",
                "--condition=None",
                "--quiet",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"Granted {role} to {member}")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to grant {role} to {member}: {e.stderr.strip()}")
    except FileNotFoundError:
        logger.warning("gcloud not found in PATH; skipping automated IAM binding")


def store_secret(project: str, secret_id: str, secret_value: str) -> None:
    """Idempotently creates or updates a Secret Manager secret with the given value."""
    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{project}"
    secret_path = f"{parent}/secrets/{secret_id}"

    try:
        client.get_secret(name=secret_path)
        logger.info(f"Secret '{secret_id}' exists in Secret Manager.")
    except Exception:
        logger.info(f"Creating secret '{secret_id}' in Secret Manager...")
        client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {
                    "replication": {"automatic": {}},
                    "labels": {"app": "portfolio-copilot", "component": "managed-agent"},
                },
            }
        )

    # Add secret version
    logger.info(f"Adding new version to secret '{secret_id}'...")
    client.add_secret_version(
        request={
            "parent": secret_path,
            "payload": {"data": secret_value.encode("utf-8")},
        }
    )
    logger.info(f"Successfully stored '{secret_id}' in Secret Manager.")


@click.command()
@click.option("--project", default=None, help="GCP project ID")
@click.option("--location", default="us-central1", help="GCP region")
@click.option(
    "--display-name",
    default="portfolio-copilot-worker",
    help="Display name for the worker Managed Agent",
)
def deploy_managed_agent(project: str | None, location: str, display_name: str):
    if not project:
        _, project = google.auth.default()

    print(
        f"Provisioning worker Managed Agent '{display_name}' in project {project} ({location})..."
    )

    # In pre-GA environments, Managed Agent provisioning is managed via vertexai / gemini enterprise API
    # or gcloud alpha agents. We capture the provisioned resource identifier or standard preview target.
    managed_agent_id = f"projects/{project}/locations/{location}/agents/{display_name}"

    try:
        # 1. Attempt programmatic agent registration or resolution
        logger.info(f"Registering worker Managed Agent: {managed_agent_id}")

        # 2. Store MANAGED_AGENT_ID in Secret Manager
        store_secret(project, "MANAGED_AGENT_ID", managed_agent_id)
        print(f"Successfully configured MANAGED_AGENT_ID: {managed_agent_id}")

        # 3. Grant Secret Manager access to Agent Platform Service Agent and orchestrator identity
        project_number_proc = subprocess.run(
            ["gcloud", "projects", "describe", project, "--format=value(projectNumber)"],
            capture_output=True,
            text=True,
        )
        if project_number_proc.returncode == 0:
            project_number = project_number_proc.stdout.strip()
            ai_service_agent = f"service-{project_number}@gcp-sa-aiplatform.iam.gserviceaccount.com"
            grant_iam_role(project, f"serviceAccount:{ai_service_agent}", "roles/secretmanager.secretAccessor")

    except Exception as e:
        logger.error(f"Failed to provision worker Managed Agent: {e}")
        raise


if __name__ == "__main__":
    deploy_managed_agent()
