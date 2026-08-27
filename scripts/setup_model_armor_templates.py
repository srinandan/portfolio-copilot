#!/usr/bin/env python3
"""Google Cloud Model Armor Template Manager for Portfolio Copilot.

Creates (or updates) the regional Model Armor *templates* the ADK runtime
guardrail plugin screens against (ADR-0026). This is the per-request layer that
complements the project-wide *floor settings* configured by
``model_armor_floor_settings.py`` (ADR-0025); the filter config here mirrors the
floor settings so both layers enforce the same RAI / PI-jailbreak / SDP /
malicious-URI policy.

The plugin needs at least one template to do anything. After running this, set:

    export MODEL_ARMOR_PLUGIN_ENABLED=true
    export MODEL_ARMOR_LOCATION=<location>
    export MODEL_ARMOR_PROMPT_TEMPLATE_ID=<prompt template id>
    export MODEL_ARMOR_RESPONSE_TEMPLATE_ID=<response template id>

Templates are regional (unlike the global floor settings): the plugin talks to
``modelarmor.{location}.rep.googleapis.com``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional

import google.auth
import httpx
from google.auth.transport.requests import Request

DEFAULT_LOCATION = "us-central1"
DEFAULT_PROMPT_TEMPLATE_ID = "portfolio-copilot-prompt"
DEFAULT_RESPONSE_TEMPLATE_ID = "portfolio-copilot-response"


def _base_url(location: str) -> str:
    return f"https://modelarmor.{location}.rep.googleapis.com/v1"


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


def build_filter_config(
    rai_confidence: str = "HIGH",
    pi_confidence: str = "MEDIUM_AND_ABOVE",
) -> Dict[str, Any]:
    """Constructs the Model Armor template filter config for Portfolio Copilot.

    Mirrors ``model_armor_floor_settings.build_floor_setting_payload`` so the
    per-request template and the project floor enforce the same policy.
    """
    return {
        "raiSettings": {
            "raiFilters": [
                {"filterType": "HATE_SPEECH", "confidenceLevel": rai_confidence.upper()},
                {"filterType": "DANGEROUS", "confidenceLevel": rai_confidence.upper()},
                {"filterType": "SEXUALLY_EXPLICIT", "confidenceLevel": rai_confidence.upper()},
                {"filterType": "HARASSMENT", "confidenceLevel": rai_confidence.upper()},
            ]
        },
        "sdpSettings": {
            "basicConfig": {
                "filterEnforcement": "ENABLED",
            }
        },
        "piAndJailbreakFilterSettings": {
            "filterEnforcement": "ENABLED",
            "confidenceLevel": pi_confidence.upper(),
        },
        "maliciousUriFilterSettings": {
            "filterEnforcement": "ENABLED",
        },
    }


def get_template(project_id: str, location: str, template_id: str, timeout: float = 30.0) -> Dict[str, Any]:
    """Fetches a Model Armor template, or ``{}`` if it does not exist."""
    name = f"projects/{project_id}/locations/{location}/templates/{template_id}"
    url = f"{_base_url(location)}/{name}"
    headers = get_auth_headers()
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(url, headers=headers)
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
    """Creates the template, or updates its filter config if it already exists."""
    headers = get_auth_headers()
    parent = f"projects/{project_id}/locations/{location}"
    name = f"{parent}/templates/{template_id}"
    payload = {"filterConfig": filter_config}

    existing = get_template(project_id, location, template_id, timeout=timeout)
    with httpx.Client(timeout=timeout) as client:
        if existing:
            url = f"{_base_url(location)}/{name}"
            resp = client.patch(url, headers=headers, params={"updateMask": "filterConfig"}, json=payload)
        else:
            url = f"{_base_url(location)}/{parent}/templates"
            resp = client.post(url, headers=headers, params={"templateId": template_id}, json=payload)
        resp.raise_for_status()
        return resp.json()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create or inspect Google Cloud Model Armor templates.")
    parser.add_argument("--project", "-p", default="", help="GCP Project ID. Defaults to GOOGLE_CLOUD_PROJECT/ADC.")
    parser.add_argument("--location", "-l", default=DEFAULT_LOCATION, help=f"Region (default: {DEFAULT_LOCATION}).")
    parser.add_argument("--prompt-template-id", default=DEFAULT_PROMPT_TEMPLATE_ID, help="Prompt (input) template id.")
    parser.add_argument(
        "--response-template-id", default=DEFAULT_RESPONSE_TEMPLATE_ID, help="Response (output) template id."
    )
    parser.add_argument("--describe", action="store_true", help="Describe templates without modifying them.")
    parser.add_argument("--rai-confidence", choices=["HIGH", "MEDIUM_AND_ABOVE", "LOW_AND_ABOVE"], default="HIGH")
    parser.add_argument(
        "--pi-confidence", choices=["HIGH", "MEDIUM_AND_ABOVE", "LOW_AND_ABOVE"], default="MEDIUM_AND_ABOVE"
    )

    args = parser.parse_args(argv)
    project_id = args.project or get_default_project()
    if not project_id:
        print("Error: Project ID must be specified via --project or GOOGLE_CLOUD_PROJECT.", file=sys.stderr)
        return 1

    template_ids = [args.prompt_template_id, args.response_template_id]
    try:
        if args.describe:
            for tid in template_ids:
                template = get_template(project_id, args.location, tid)
                print(f"--- {tid} ---")
                print(json.dumps(template, indent=2) if template else "(not found)")
            return 0

        filter_config = build_filter_config(rai_confidence=args.rai_confidence, pi_confidence=args.pi_confidence)
        for tid in template_ids:
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
