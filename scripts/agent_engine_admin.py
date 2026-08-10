"""Admin/troubleshooting CLI for Agent Runtime (fka Agent Engine).

This is the tool to reach for when inspecting or operating on deployed
Agent Engines. The `gcloud ai reasoning-engines`, `gcloud ai-platform`,
and `gcloud agent-registry` command groups do NOT exist — the only
supported control-plane surface is the Python `vertexai` SDK
(`vertexai.Client(...).agent_engines`), which this CLI wraps.

Subcommands:

    list        List Agent Engines in a project/region.
    describe    Show full metadata for one Agent Engine.
    query       Send a query to an Agent Engine and print the response.
    delete      Delete an Agent Engine by resource name or display name.
    logs        Read recent Cloud Logging entries for one Agent Engine.

`--engine` accepts either the full resource name
(`projects/.../locations/.../reasoningEngines/<id>`) or the deployed
`display_name` (e.g. `portfolio-copilot-agent`), and is resolved to the
resource name via `agent_engines.list`.

Deploy/update lives in `deploy_agent_engine.py` — this file is
read-mostly plus targeted delete.
"""

import json
import logging
import subprocess
from typing import Any

import click
import google.auth
import vertexai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_client(project: str, location: str) -> vertexai.Client:
    return vertexai.Client(
        project=project,
        location=location,
        http_options=dict(api_version="v1beta1"),
    )


def _resolve_project(project: str | None) -> str:
    if project:
        return project
    _, resolved = google.auth.default()
    if not resolved:
        raise click.UsageError(
            "No --project given and google.auth.default() returned no project. "
            "Pass --project=<gcp-project-id> or run `gcloud auth application-default login`."
        )
    return resolved


def _engines_iter(client: vertexai.Client, display_name: str | None = None):
    config: dict[str, Any] = {}
    if display_name:
        config["filter"] = f'display_name="{display_name}"'
    return client.agent_engines.list(config=config or None)


def _resolve_engine(client: vertexai.Client, engine: str):
    """Return an engine object given either a resource name or a display name."""
    if "/reasoningEngines/" in engine:
        for candidate in _engines_iter(client):
            if getattr(candidate.api_resource, "name", None) == engine:
                return candidate
        raise click.ClickException(f"No Agent Engine matches resource name {engine!r}")

    matches = [c for c in _engines_iter(client, display_name=engine)]
    if not matches:
        raise click.ClickException(
            f"No Agent Engine matches display_name={engine!r}. "
            "Run `agent_engine_admin.py list` to see what's deployed."
        )
    if len(matches) > 1:
        names = ", ".join(m.api_resource.name for m in matches)
        raise click.ClickException(
            f"display_name={engine!r} matches multiple engines ({names}). "
            "Pass the full resource name via --engine."
        )
    return matches[0]


def _engine_row(engine) -> dict[str, Any]:
    api = engine.api_resource
    return {
        "name": getattr(api, "name", None),
        "display_name": getattr(api, "display_name", None),
        "create_time": str(getattr(api, "create_time", "")) or None,
        "update_time": str(getattr(api, "update_time", "")) or None,
        "state": str(getattr(api, "state", "")) or None,
    }


@click.group()
def cli() -> None:
    """Inspect and manage Agent Runtime (Agent Engine) deployments."""


def _common_options(fn):
    fn = click.option("--location", default="us-central1", help="GCP region.")(fn)
    fn = click.option("--project", default=None, help="GCP project ID (defaults to ADC).")(fn)
    return fn


@cli.command("list")
@_common_options
@click.option("--display-name", default=None, help="Filter by exact display_name.")
def list_engines(project: str | None, location: str, display_name: str | None) -> None:
    """List Agent Engines in a project/region."""
    project = _resolve_project(project)
    client = _get_client(project, location)
    rows = [_engine_row(e) for e in _engines_iter(client, display_name=display_name)]
    click.echo(json.dumps(rows, indent=2))


@cli.command("describe")
@_common_options
@click.option("--engine", required=True, help="Resource name or display_name.")
def describe_engine(project: str | None, location: str, engine: str) -> None:
    """Show full metadata for one Agent Engine."""
    project = _resolve_project(project)
    client = _get_client(project, location)
    resolved = _resolve_engine(client, engine)
    api = resolved.api_resource
    payload = {
        **_engine_row(resolved),
        "spec": _to_jsonable(getattr(api, "spec", None)),
    }
    click.echo(json.dumps(payload, indent=2, default=str))


@cli.command("query")
@_common_options
@click.option("--engine", required=True, help="Resource name or display_name.")
@click.option("--input", "user_input", required=True, help="Message to send to the agent.")
def query_engine(project: str | None, location: str, engine: str, user_input: str) -> None:
    """Send a synchronous query to an Agent Engine."""
    project = _resolve_project(project)
    client = _get_client(project, location)
    resolved = _resolve_engine(client, engine)
    response = resolved.query(input=user_input)
    click.echo(json.dumps(_to_jsonable(response), indent=2, default=str))


@cli.command("delete")
@_common_options
@click.option("--engine", required=True, help="Resource name or display_name.")
@click.option("--force", is_flag=True, help="Delete without confirmation prompt.")
def delete_engine(project: str | None, location: str, engine: str, force: bool) -> None:
    """Delete an Agent Engine."""
    project = _resolve_project(project)
    client = _get_client(project, location)
    resolved = _resolve_engine(client, engine)
    name = resolved.api_resource.name
    if not force:
        click.confirm(f"Delete Agent Engine {name}?", abort=True)
    client.agent_engines.delete(name=name)
    click.echo(f"Deleted {name}")


@cli.command("logs")
@_common_options
@click.option("--engine", required=True, help="Resource name or display_name.")
@click.option("--limit", default=50, show_default=True, help="Max log entries.")
@click.option("--freshness", default="1h", show_default=True, help="Lookback window (e.g. 30m, 2h, 1d).")
@click.option(
    "--severity",
    default=None,
    help="Minimum severity (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
)
def logs_engine(
    project: str | None,
    location: str,
    engine: str,
    limit: int,
    freshness: str,
    severity: str | None,
) -> None:
    """Stream Cloud Logging entries for one Agent Engine via `gcloud logging read`.

    Cloud Logging IS a real gcloud group — the invalid ones are `gcloud ai
    reasoning-engines` etc. for the control plane. For logs, gcloud is fine.
    """
    project = _resolve_project(project)
    client = _get_client(project, location)
    resolved = _resolve_engine(client, engine)
    engine_id = resolved.api_resource.name.split("/")[-1]

    filter_parts = [
        'resource.type="aiplatform.googleapis.com/ReasoningEngine"',
        f'resource.labels.reasoning_engine_id="{engine_id}"',
        f'resource.labels.location="{location}"',
    ]
    if severity:
        filter_parts.append(f"severity>={severity}")

    cmd = [
        "gcloud",
        "logging",
        "read",
        " AND ".join(filter_parts),
        f"--project={project}",
        f"--limit={limit}",
        f"--freshness={freshness}",
        "--format=json",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError as err:
        raise click.ClickException("gcloud not found in PATH — install Cloud SDK to use `logs`.") from err
    except subprocess.CalledProcessError as err:
        raise click.ClickException(f"gcloud logging read failed: {err.stderr.strip()}") from err
    click.echo(proc.stdout)


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except Exception:
            pass
    if hasattr(value, "to_dict"):
        try:
            return value.to_dict()
        except Exception:
            pass
    return str(value)


if __name__ == "__main__":
    cli()
