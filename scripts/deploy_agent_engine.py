"""Deploy or update the orchestrator on Agent Platform Agent Runtime (Agent Engine).

Two modes:

* Container mode (`--container-uri=...`): deploys the container image from
  Artifact Registry as an Agent Engine (per ADR-0008 the orchestrator runs on
  Agent Runtime, not Cloud Run). This is what the CI/CD pipeline uses.
* Placeholder mode (no `--container-uri`): keeps the legacy placeholder-agent
  deploy path so `install/README.md`'s first-time setup still works before a
  container has been built.

Idempotent: if an Agent Engine with the same `--display-name` already exists in
the target project/region, it is updated in place; otherwise a new one is
created. Agent Identity IAM bindings are re-applied on every run so the
effective identity has the roles it needs.
"""

import logging
import subprocess

import click
import google.auth
import vertexai
from vertexai import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


AGENT_IDENTITY_ROLES = [
    "roles/datastore.user",  # Firestore: IPS, holdings, liabilities
    "roles/bigquery.dataViewer",  # BigQuery: spending analysis
    "roles/bigquery.user",  # BigQuery: run query jobs
    "roles/secretmanager.secretAccessor",  # Secret Manager: Alpaca API key & MANAGED_AGENT_ID
    "roles/agentregistry.viewer",  # Agent Registry: list authorized skills
    "roles/aiplatform.user",  # Vertex AI: Managed Agents and Reasoning Engine invocation
    "roles/serviceusage.serviceUsageConsumer",  # Service usage consumer
    "roles/logging.logWriter",  # Cloud Logging
    "roles/monitoring.metricWriter",  # Cloud Monitoring
    "roles/cloudtrace.agent",  # Cloud Trace: emit OpenTelemetry spans
]


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


def _apply_identity_iam(project: str, remote_app) -> None:
    effective_identity = getattr(
        getattr(getattr(remote_app, "api_resource", None), "spec", None),
        "effective_identity",
        None,
    )
    if not effective_identity:
        resource_name = getattr(getattr(remote_app, "api_resource", None), "name", None)
        if resource_name:
            effective_identity = (
                f"principal://agents.global.org-975672035171.system.id.goog/resources/aiplatform/{resource_name}"
            )
        else:
            logger.warning("Agent Engine did not expose an effective_identity or resource name; skipping IAM grants.")
            return

    principal = (
        effective_identity if effective_identity.startswith("principal://") else f"principal://{effective_identity}"
    )
    logger.info(f"Configuring IAM bindings for Agent Identity ({principal})...")
    for role in AGENT_IDENTITY_ROLES:
        grant_iam_role(project, principal, role)


def _find_existing_engine(client: vertexai.Client, display_name: str):
    """Return the first Agent Engine with a matching display_name, or None."""
    try:
        for engine in client.agent_engines.list(config={"filter": f'display_name="{display_name}"'}):
            return engine
    except Exception as e:
        logger.warning(f"agent_engines.list failed: {e}")
    return None


try:
    from vertexai import agentplatform
except ImportError:
    try:
        from google.cloud.aiplatform import agentplatform
    except ImportError:
        agentplatform = None


def _get_client(project: str, location: str):
    """Return an agentplatform.Client if available, falling back to vertexai.Client."""
    if agentplatform is not None and hasattr(agentplatform, "Client"):
        try:
            return agentplatform.Client(project=project, location=location)
        except Exception as e:
            logger.debug(f"agentplatform.Client init failed ({e}); falling back to vertexai.Client")
    return vertexai.Client(
        project=project,
        location=location,
        http_options=dict(api_version="v1beta1"),
    )


@click.command()
@click.option("--project", default=None, help="GCP project ID")
@click.option("--location", default="us-central1", help="GCP region")
@click.option(
    "--display-name",
    default="portfolio-copilot-agent",
    help="Display name for the agent engine",
)
@click.option(
    "--container-uri",
    default=None,
    help=(
        "Artifact Registry image URI to deploy as an Agent Runtime container "
        "(e.g. us-central1-docker.pkg.dev/PROJECT/portfolio-copilot/portfolio-copilot-orchestrator:v0.1.0). "
        "When omitted, falls back to the legacy PlaceholderAgent deploy path."
    ),
)
@click.option(
    "--sec-edgar-user-agent",
    default=None,
    help="User-Agent string for SEC EDGAR requests (defaults to SEC_EDGAR_USER_AGENT env var or standard contact)",
)
def deploy_agent_engine(
    project: str | None,
    location: str,
    display_name: str,
    container_uri: str | None,
    sec_edgar_user_agent: str | None = None,
):
    if not project:
        _, project = google.auth.default()

    staging_bucket = f"gs://{project}-portfolio-copilot-staging"
    client = _get_client(project=project, location=location)
    vertexai.init(project=project, location=location, staging_bucket=staging_bucket)

    existing = _find_existing_engine(client, display_name)

    if container_uri:
        print(f"Deploying Agent Engine '{display_name}' from container {container_uri} to {project} in {location}...")
        try:
            sec_user_agent = (
                sec_edgar_user_agent
                or os.environ.get("SEC_EDGAR_USER_AGENT")
                or "PortfolioCopilot/1.0 (portfolio-copilot@google.com)"
            )
            env_vars = {
                "AGENT_ENGINE_ID": "",
                "PROJECT_ID": project,
                "OTEL_EXPORTER_GCP_TRACE_PROJECT_ID": project,
                "AGENT_REGISTRY_LOCATION": "global",
                "GOOGLE_GENAI_USE_ENTERPRISE": "true",
                "GOOGLE_CLOUD_LOCATION": location,
                "GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES": "false",
                "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
                "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
                "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "EVENT_ONLY",
                # Names the orchestrator's spans in Cloud Trace (server.py exports
                # them via the Cloud Trace exporter it configures at startup).
                "OTEL_SERVICE_NAME": "portfolio-copilot-orchestrator",
                "SEC_EDGAR_USER_AGENT": sec_user_agent,
            }
            if existing is not None:
                engine_id = existing.api_resource.name.split("/")[-1]
                env_vars["AGENT_ENGINE_ID"] = engine_id
                config = {
                    "display_name": display_name,
                    "agent_framework": "google-adk",
                    "identity_type": types.IdentityType.AGENT_IDENTITY,
                    "container_spec": {"image_uri": container_uri},
                    "env_vars": env_vars,
                }
                remote_app = client.agent_engines.update(name=existing.api_resource.name, config=config)
                print(f"Updated existing Agent Engine: {remote_app.api_resource.name} (AGENT_ENGINE_ID={engine_id})")
            else:
                initial_config = {
                    "display_name": display_name,
                    "agent_framework": "google-adk",
                    "identity_type": types.IdentityType.AGENT_IDENTITY,
                    "container_spec": {"image_uri": container_uri},
                }
                remote_app = client.agent_engines.create(config=initial_config)
                engine_id = remote_app.api_resource.name.split("/")[-1]
                print(
                    f"Created Agent Engine: {remote_app.api_resource.name}. Updating with AGENT_ENGINE_ID={engine_id}..."
                )
                env_vars["AGENT_ENGINE_ID"] = engine_id
                update_config = {
                    "display_name": display_name,
                    "agent_framework": "google-adk",
                    "identity_type": types.IdentityType.AGENT_IDENTITY,
                    "container_spec": {"image_uri": container_uri},
                    "env_vars": env_vars,
                }
                remote_app = client.agent_engines.update(name=remote_app.api_resource.name, config=update_config)
                print(
                    f"Successfully deployed Agent Engine: {remote_app.api_resource.name} (AGENT_ENGINE_ID={engine_id})"
                )
            _apply_identity_iam(project, remote_app)
        except Exception as e:
            print(f"Failed to deploy Agent Engine: {e}")
            raise
        return

    print(
        f"Deploying placeholder Agent Engine '{display_name}' with Agent Identity "
        f"to {project} in {location} (no --container-uri provided)..."
    )

    class PlaceholderAgent:
        def set_up(self):
            pass

        def query(self, input: str) -> str:
            return "Placeholder Agent Engine response"

    try:
        agent = PlaceholderAgent()
        remote_app = client.agent_engines.create(
            agent=agent,
            config={
                "display_name": display_name,
                "agent_framework": "google-adk",
                "identity_type": types.IdentityType.AGENT_IDENTITY,
                "staging_bucket": staging_bucket,
            },
        )
        print(f"Successfully deployed placeholder Agent Engine: {remote_app.resource_name}")
        _apply_identity_iam(project, remote_app)
    except Exception as e:
        print(f"Failed to deploy Agent Engine: {e}")


if __name__ == "__main__":
    deploy_agent_engine()
