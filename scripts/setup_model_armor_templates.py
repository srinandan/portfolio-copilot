#!/usr/bin/env python3
"""Google Cloud Model Armor Template Manager for Portfolio Copilot.

Provisions the **layer 2** of our two-layer Model Armor design (ADR-0032):

* **Layer 1 — floor settings** (`model_armor_floor_settings.py`, ADR-0025):
  the broad, project-wide backstop — Responsible AI / abuse, prompt-injection &
  jailbreak, malicious-URI, basic SDP. Applies everywhere.
* **Layer 2 — this template** (per-request, on the sensitive planning path):
  the *specifics*. It uses **advanced SDP**, pointing at a Cloud DLP (Sensitive
  Data Protection) *inspect template* that declares the exact infoTypes we care
  about for a financial app — SSN, credit card, bank routing, IBAN, ITIN — with
  a tunable likelihood threshold. The broad RAI/PI/URI filters are deliberately
  NOT repeated here; the floor owns those.

So this script provisions two things, in order:
  1. a DLP inspect template (the infoType list), then
  2. the regional Model Armor prompt/response templates whose `sdpSettings`
     reference that inspect template via `advancedConfig`.

After running, enable the runtime guardrail with:

    export MODEL_ARMOR_PLUGIN_ENABLED=true
    export MODEL_ARMOR_LOCATION=<location>
    export MODEL_ARMOR_PROMPT_TEMPLATE_ID=<prompt template id>
    export MODEL_ARMOR_RESPONSE_TEMPLATE_ID=<response template id>

Both the Model Armor templates and the DLP inspect template are regional and
must share `<location>`; the plugin talks to ``modelarmor.{location}.rep.googleapis.com``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

import google.auth
import httpx
from google.auth.transport.requests import Request

DEFAULT_LOCATION = "us-central1"
DEFAULT_PROMPT_TEMPLATE_ID = "portfolio-copilot-prompt"
DEFAULT_RESPONSE_TEMPLATE_ID = "portfolio-copilot-response"
DEFAULT_DLP_INSPECT_TEMPLATE_ID = "portfolio-copilot-pii"

# Financial-app PII the layer-2 template inspects for. Tunable via --info-types.
DEFAULT_INFO_TYPES = [
    "US_SOCIAL_SECURITY_NUMBER",
    "CREDIT_CARD_NUMBER",
    "US_BANK_ROUTING_MICR",
    "IBAN_CODE",
    "US_INDIVIDUAL_TAXPAYER_IDENTIFICATION_NUMBER",
]
DEFAULT_MIN_LIKELIHOOD = "POSSIBLE"


def _model_armor_base_url(location: str) -> str:
    return f"https://modelarmor.{location}.rep.googleapis.com/v1"


def _dlp_base_url() -> str:
    # DLP is a global host with the location carried in the resource path.
    return "https://dlp.googleapis.com/v2"


def get_auth_headers() -> Dict[str, str]:
    """Generates bearer authorization headers from Application Default Credentials."""
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    if not creds.valid:
        creds.refresh(Request())
    return {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def get_default_project() -> str:
    """Resolves default GCP project from environment or ADC."""
    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("PROJECT_ID")
    if project:
        return project
    try:
        _, creds_project = google.auth.default()
        if creds_project:
            return creds_project
    except Exception:
        pass
    return ""


# --- Cloud DLP inspect template (the infoType list) --------------------------


def build_dlp_inspect_config(
    info_types: Optional[List[str]] = None,
    min_likelihood: str = DEFAULT_MIN_LIKELIHOOD,
) -> Dict[str, Any]:
    """Builds the DLP inspectConfig declaring which infoTypes to detect."""
    types = info_types or DEFAULT_INFO_TYPES
    return {
        "infoTypes": [{"name": t} for t in types],
        "minLikelihood": min_likelihood.upper(),
        # Never echo the matched value back in findings — we only need the hit.
        "includeQuote": False,
    }


def dlp_inspect_template_name(project_id: str, location: str, template_id: str) -> str:
    return f"projects/{project_id}/locations/{location}/inspectTemplates/{template_id}"


def get_dlp_inspect_template(project_id: str, location: str, template_id: str, timeout: float = 30.0) -> Dict[str, Any]:
    """Fetches a DLP inspect template, or ``{}`` if it does not exist."""
    name = dlp_inspect_template_name(project_id, location, template_id)
    url = f"{_dlp_base_url()}/{name}"
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(url, headers=get_auth_headers())
        if resp.status_code == 404:
            return {}
        resp.raise_for_status()
        return resp.json()


def create_or_update_dlp_inspect_template(
    project_id: str,
    location: str,
    template_id: str,
    info_types: Optional[List[str]] = None,
    min_likelihood: str = DEFAULT_MIN_LIKELIHOOD,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Creates the DLP inspect template, or updates its inspectConfig if present.

    Returns the template resource (its ``name`` is what the Model Armor template
    references via ``sdpSettings.advancedConfig.inspectTemplate``).
    """
    headers = get_auth_headers()
    parent = f"projects/{project_id}/locations/{location}"
    inspect_config = build_dlp_inspect_config(info_types=info_types, min_likelihood=min_likelihood)
    existing = get_dlp_inspect_template(project_id, location, template_id, timeout=timeout)
    with httpx.Client(timeout=timeout) as client:
        if existing:
            url = f"{_dlp_base_url()}/{dlp_inspect_template_name(project_id, location, template_id)}"
            body = {"inspectTemplate": {"inspectConfig": inspect_config}, "updateMask": "inspectConfig"}
            resp = client.patch(url, headers=headers, json=body)
        else:
            url = f"{_dlp_base_url()}/{parent}/inspectTemplates"
            body = {
                "templateId": template_id,
                "inspectTemplate": {
                    "displayName": "Portfolio Copilot financial PII",
                    "inspectConfig": inspect_config,
                },
            }
            resp = client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        return resp.json()


# --- Model Armor templates (reference the DLP inspect template) --------------


def build_filter_config(inspect_template_name: str) -> Dict[str, Any]:
    """Builds the Model Armor template filter config (layer 2, ADR-0032).

    Advanced SDP only: the template's job is the *specifics* (SSN, card, bank
    routing, ...) via the referenced DLP inspect template. The broad RAI /
    PI-jailbreak / malicious-URI filters are intentionally omitted — the project
    floor settings (ADR-0025) own those, so we don't duplicate them per request.
    """
    return {
        "sdpSettings": {
            "advancedConfig": {
                "inspectTemplate": inspect_template_name,
            }
        },
    }


def get_template(project_id: str, location: str, template_id: str, timeout: float = 30.0) -> Dict[str, Any]:
    """Fetches a Model Armor template, or ``{}`` if it does not exist."""
    name = f"projects/{project_id}/locations/{location}/templates/{template_id}"
    url = f"{_model_armor_base_url(location)}/{name}"
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(url, headers=get_auth_headers())
        if resp.status_code == 404:
            return {}
        resp.raise_for_status()
        return resp.json()


def create_or_update_template(
    project_id: str,
    location: str,
    template_id: str,
    filter_config: Dict[str, Any],
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Creates the Model Armor template, or updates its filter config if present."""
    headers = get_auth_headers()
    parent = f"projects/{project_id}/locations/{location}"
    name = f"{parent}/templates/{template_id}"
    payload = {"filterConfig": filter_config}

    existing = get_template(project_id, location, template_id, timeout=timeout)
    with httpx.Client(timeout=timeout) as client:
        if existing:
            url = f"{_model_armor_base_url(location)}/{name}"
            resp = client.patch(url, headers=headers, params={"updateMask": "filterConfig"}, json=payload)
        else:
            url = f"{_model_armor_base_url(location)}/{parent}/templates"
            resp = client.post(url, headers=headers, params={"templateId": template_id}, json=payload)
        resp.raise_for_status()
        return resp.json()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create or inspect Google Cloud Model Armor templates (advanced SDP).")
    parser.add_argument("--project", "-p", default="", help="GCP Project ID. Defaults to GOOGLE_CLOUD_PROJECT/ADC.")
    parser.add_argument("--location", "-l", default=DEFAULT_LOCATION, help=f"Region (default: {DEFAULT_LOCATION}).")
    parser.add_argument("--prompt-template-id", default=DEFAULT_PROMPT_TEMPLATE_ID, help="Prompt (input) template id.")
    parser.add_argument(
        "--response-template-id", default=DEFAULT_RESPONSE_TEMPLATE_ID, help="Response (output) template id."
    )
    parser.add_argument(
        "--dlp-inspect-template-id", default=DEFAULT_DLP_INSPECT_TEMPLATE_ID, help="DLP inspect template id."
    )
    parser.add_argument(
        "--info-types",
        default=",".join(DEFAULT_INFO_TYPES),
        help="Comma-separated DLP infoTypes for the inspect template.",
    )
    parser.add_argument(
        "--min-likelihood",
        choices=["VERY_UNLIKELY", "UNLIKELY", "POSSIBLE", "LIKELY", "VERY_LIKELY"],
        default=DEFAULT_MIN_LIKELIHOOD,
        help=f"Minimum DLP match likelihood (default: {DEFAULT_MIN_LIKELIHOOD}).",
    )
    parser.add_argument("--describe", action="store_true", help="Describe templates without modifying them.")

    args = parser.parse_args(argv)
    project_id = args.project or get_default_project()
    if not project_id:
        print("Error: Project ID must be specified via --project or GOOGLE_CLOUD_PROJECT.", file=sys.stderr)
        return 1

    ma_template_ids = [args.prompt_template_id, args.response_template_id]
    info_types = [t.strip() for t in args.info_types.split(",") if t.strip()]
    try:
        if args.describe:
            print(f"--- DLP inspect template: {args.dlp_inspect_template_id} ---")
            dlp = get_dlp_inspect_template(project_id, args.location, args.dlp_inspect_template_id)
            print(json.dumps(dlp, indent=2) if dlp else "(not found)")
            for tid in ma_template_ids:
                print(f"--- Model Armor template: {tid} ---")
                template = get_template(project_id, args.location, tid)
                print(json.dumps(template, indent=2) if template else "(not found)")
            return 0

        # 1. Provision the DLP inspect template (the infoType list).
        print(
            f"Configuring DLP inspect template {args.dlp_inspect_template_id} in {project_id}/{args.location} "
            f"(infoTypes={info_types}, minLikelihood={args.min_likelihood})..."
        )
        dlp_result = create_or_update_dlp_inspect_template(
            project_id,
            args.location,
            args.dlp_inspect_template_id,
            info_types=info_types,
            min_likelihood=args.min_likelihood,
        )
        inspect_template = dlp_result.get("name") or dlp_inspect_template_name(
            project_id, args.location, args.dlp_inspect_template_id
        )
        print(f"  -> {inspect_template}")

        # 2. Provision the Model Armor templates referencing it via advanced SDP.
        filter_config = build_filter_config(inspect_template)
        for tid in ma_template_ids:
            print(f"Configuring Model Armor template {tid} in {project_id}/{args.location}...")
            result = create_or_update_template(project_id, args.location, tid, filter_config)
            print(json.dumps(result, indent=2))

        print("\nDone. Enable the runtime guardrail with:")
        print("  export MODEL_ARMOR_PLUGIN_ENABLED=true")
        print(f"  export MODEL_ARMOR_LOCATION={args.location}")
        print(f"  export MODEL_ARMOR_PROMPT_TEMPLATE_ID={args.prompt_template_id}")
        print(f"  export MODEL_ARMOR_RESPONSE_TEMPLATE_ID={args.response_template_id}")
        return 0
    except Exception as e:
        print(f"Error managing Model Armor templates: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
