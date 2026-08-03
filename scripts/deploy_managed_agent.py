import json
import logging
import subprocess
from typing import Any, Dict, List, Optional

import click
import google.auth
from google.auth.transport.requests import Request

try:
    from google.cloud import secretmanager
except ImportError:
    secretmanager = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_auth_token() -> str:
    """Retrieves Google Cloud default credentials OAuth token."""
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    if not credentials.valid:
        credentials.refresh(Request())
    return credentials.token


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
    if secretmanager is not None:
        try:
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

            logger.info(f"Adding new version to secret '{secret_id}'...")
            client.add_secret_version(
                request={
                    "parent": secret_path,
                    "payload": {"data": secret_value.encode("utf-8")},
                }
            )
            logger.info(f"Successfully stored '{secret_id}' in Secret Manager.")
            return
        except Exception as e:
            logger.warning(f"SecretManager SDK store failed ({e}); trying gcloud fallback...")

    # Fallback to gcloud CLI
    try:
        check_proc = subprocess.run(
            ["gcloud", "secrets", "describe", secret_id, f"--project={project}", "--format=json"],
            capture_output=True,
            text=True,
        )
        if check_proc.returncode != 0:
            logger.info(f"Creating secret '{secret_id}' via gcloud...")
            subprocess.run(
                [
                    "gcloud",
                    "secrets",
                    "create",
                    secret_id,
                    f"--project={project}",
                    "--replication-policy=automatic",
                    "--labels=app=portfolio-copilot,component=managed-agent",
                    "--quiet",
                ],
                check=True,
                capture_output=True,
            )

        logger.info(f"Adding version to secret '{secret_id}' via gcloud...")
        subprocess.run(
            [
                "gcloud",
                "secrets",
                "versions",
                "add",
                secret_id,
                f"--project={project}",
                "--data-file=-",
            ],
            input=secret_value.encode("utf-8"),
            check=True,
            capture_output=True,
        )
        logger.info(f"Successfully stored '{secret_id}' via gcloud secrets.")
    except Exception as e:
        logger.error(f"Failed to store secret '{secret_id}' via gcloud: {e}")
        raise


def find_existing_managed_agent(project: str, location: str, display_name: str) -> Optional[str]:
    """Lists agents in the project/location and returns server-assigned resource ID if matching display_name exists."""
    candidate_commands = [
        ["gcloud", "alpha", "agent-registry", "agents", "list", f"--project={project}", f"--location={location}", "--format=json"],
        ["gcloud", "alpha", "agents", "list", f"--project={project}", f"--location={location}", "--format=json"],
    ]

    for cmd in candidate_commands:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
            agents: List[Dict[str, Any]] = json.loads(proc.stdout)
            for agent in agents:
                if agent.get("displayName") == display_name or agent.get("display_name") == display_name:
                    server_id = agent.get("name")
                    if server_id:
                        logger.info(f"Found existing Managed Agent matching '{display_name}': {server_id}")
                        return server_id
            # If command succeeded but agent wasn't found in the list, return None
            return None
        except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
            continue

    return None


def provision_managed_agent(
    project: str,
    location: str,
    display_name: str,
    allow_placeholder: bool = False,
) -> str:
    """Provisions a worker Managed Agent and returns the server-assigned resource ID.

    1. Checks if an agent with display_name already exists (idempotency).
    2. Creates a new Managed Agent via gcloud agent-registry / agents CLI.
    3. Captures and returns the server-assigned resource ID.
    4. Fails loud if creation fails, unless allow_placeholder=True is explicitly set.
    """
    existing = find_existing_managed_agent(project, location, display_name)
    if existing:
        return existing

    candidate_commands = [
        ["gcloud", "alpha", "agent-registry", "agents", "create", f"--project={project}", f"--location={location}", f"--display-name={display_name}", "--format=json"],
        ["gcloud", "alpha", "agents", "create", f"--project={project}", f"--location={location}", f"--display-name={display_name}", "--format=json"],
    ]

    last_error = None
    for cmd in candidate_commands:
        try:
            logger.info(f"Attempting Managed Agent creation with {' '.join(cmd[:4])}...")
            proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
            agent_data = json.loads(proc.stdout)
            server_id = agent_data.get("name")
            if server_id:
                logger.info(f"Successfully provisioned Managed Agent with server ID: {server_id}")
                return server_id
            raise ValueError(f"Command returned response without 'name' resource field: {agent_data}")
        except Exception as e:
            last_error = e

    if allow_placeholder:
        fallback_id = f"projects/{project}/locations/{location}/agents/{display_name}"
        logger.warning(
            f"Managed Agent provisioning failed ({last_error}), but allow_placeholder is enabled. "
            f"Using placeholder ID: {fallback_id}"
        )
        return fallback_id

    raise RuntimeError(
        f"Failed to provision Managed Agent '{display_name}' in project {project} ({location}): {last_error}. "
        "Verify gcloud authentication and that Agent Registry / Gemini Enterprise Agent Platform API is enabled. "
        "(Use --allow-placeholder for local mock development environments)."
    )


@click.command()
@click.option("--project", default=None, help="GCP project ID")
@click.option("--location", default="us-central1", help="GCP region")
@click.option(
    "--display-name",
    default="portfolio-copilot-worker",
    help="Display name for the worker Managed Agent",
)
@click.option(
    "--allow-placeholder",
    is_flag=True,
    default=False,
    help="Allow fallback to placeholder agent ID if GCP provisioning fails (for local mock/dev)",
)
def deploy_managed_agent(
    project: str | None,
    location: str,
    display_name: str,
    allow_placeholder: bool = False,
):
    if not project:
        _, project = google.auth.default()

    print(
        f"Provisioning worker Managed Agent '{display_name}' in project {project} ({location})..."
    )

    try:
        # 1. Provision or resolve server-assigned agent ID (fails loud by default)
        server_agent_id = provision_managed_agent(
            project,
            location,
            display_name,
            allow_placeholder=allow_placeholder,
        )

        # 2. Store server-assigned MANAGED_AGENT_ID in Secret Manager
        store_secret(project, "MANAGED_AGENT_ID", server_agent_id)
        print(f"Successfully configured MANAGED_AGENT_ID: {server_agent_id}")

        # 3. Grant Secret Manager access to Agent Platform Service Agent and SPIFFE Agent Identity
        project_number_proc = subprocess.run(
            ["gcloud", "projects", "describe", project, "--format=value(projectNumber)"],
            capture_output=True,
            text=True,
        )
        if project_number_proc.returncode == 0:
            project_number = project_number_proc.stdout.strip()
            ai_service_agent = f"service-{project_number}@gcp-sa-aiplatform.iam.gserviceaccount.com"
            grant_iam_role(project, f"serviceAccount:{ai_service_agent}", "roles/secretmanager.secretAccessor")
            principal_set = f"principalSet://agents.global.project-{project_number}.system.id.goog/attribute.platformContainer/aiplatform/projects/{project_number}"
            grant_iam_role(project, principal_set, "roles/secretmanager.secretAccessor")

    except Exception as e:
        logger.error(f"Failed to provision worker Managed Agent: {e}")
        raise


if __name__ == "__main__":
    deploy_managed_agent()
