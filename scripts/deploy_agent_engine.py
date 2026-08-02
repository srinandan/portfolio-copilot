import logging
import subprocess
import click
import google.auth
import vertexai
from vertexai import types

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


@click.command()
@click.option("--project", default=None, help="GCP project ID")
@click.option("--location", default="us-central1", help="GCP region")
@click.option(
    "--display-name",
    default="portfolio-copilot-agent",
    help="Display name for the agent engine",
)
def deploy_agent_engine(project: str | None, location: str, display_name: str):
    if not project:
        _, project = google.auth.default()

    print(
        f"Deploying placeholder Agent Engine '{display_name}' with Agent Identity to {project} in {location}..."
    )

    vertexai.init(project=project, location=location)

    client = vertexai.Client(
        project=project,
        location=location,
        http_options=dict(api_version="v1beta1"),
    )

    class PlaceholderAgent:
        def set_up(self):
            pass

        def query(self, input: str) -> str:
            return "Placeholder Agent Engine response"

    try:
        agent = PlaceholderAgent()

        # Deploy Reasoning Engine with Agent Identity
        remote_app = client.agent_engines.create(
            agent=agent,
            config={
                "display_name": display_name,
                "identity_type": types.IdentityType.AGENT_IDENTITY,
            },
        )
        print(
            f"Successfully deployed placeholder Agent Engine: {remote_app.resource_name}"
        )

        effective_identity = getattr(
            getattr(getattr(remote_app, "api_resource", None), "spec", None),
            "effective_identity",
            None,
        )

        if effective_identity:
            print(f"Effective Identity: {effective_identity}")
            principal = (
                effective_identity
                if effective_identity.startswith("principal://")
                else f"principal://{effective_identity}"
            )

            # Grant required least-privilege IAM roles to the orchestrator's Agent Identity
            print(f"Configuring IAM bindings for Agent Identity ({principal})...")
            roles = [
                "roles/datastore.user",  # Firestore: IPS, holdings, liabilities
                "roles/bigquery.dataViewer",  # BigQuery: spending analysis
                "roles/secretmanager.secretAccessor",  # Secret Manager: Alpaca API key
            ]
            for role in roles:
                grant_iam_role(project, principal, role)

    except Exception as e:
        print(f"Failed to deploy Agent Engine: {e}")


if __name__ == "__main__":
    deploy_agent_engine()
