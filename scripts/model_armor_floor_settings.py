#!/usr/bin/env python3
"""Google Cloud Model Armor Floor Settings Manager for Portfolio Copilot.

Configures project-wide Model Armor Floor Settings for Responsible AI (RAI),
Prompt Injection / Jailbreak prevention, Sensitive Data Protection (SDP),
Malicious URI filtering, and MCP tool traffic sanitization.
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

MODEL_ARMOR_BASE_URL = "https://modelarmor.googleapis.com/v1"


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


def get_floor_setting(project_id: str, timeout: float = 30.0) -> Dict[str, Any]:
    """Fetches the active Model Armor floor setting for a given project."""
    url = f"{MODEL_ARMOR_BASE_URL}/projects/{project_id}/locations/global/floorSetting"
    headers = get_auth_headers()
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code == 404:
            return {}
        resp.raise_for_status()
        return resp.json()


def build_floor_setting_payload(
    enable_enforcement: bool = True,
    enforcement_mode: str = "INSPECT_ONLY",
    enable_cloud_logging: bool = True,
    multi_language: bool = True,
    rai_confidence: str = "HIGH",
    pi_confidence: str = "MEDIUM_AND_ABOVE",
) -> Dict[str, Any]:
    """Constructs the canonical Model Armor floor setting specification for Portfolio Copilot."""
    is_inspect_only = enforcement_mode.upper() == "INSPECT_ONLY"
    return {
        "enableFloorSettingEnforcement": enable_enforcement,
        "integratedServices": [
            "AI_PLATFORM",
            "GOOGLE_MCP_SERVER",
        ],
        "aiPlatformFloorSetting": {
            "inspectOnly": is_inspect_only,
            "enableCloudLogging": enable_cloud_logging,
        },
        "googleMcpServerFloorSetting": {
            "inspectOnly": is_inspect_only,
            "enableCloudLogging": enable_cloud_logging,
        },
        "floorSettingMetadata": {
            "multiLanguageDetection": {
                "enableMultiLanguageDetection": multi_language,
            }
        },
        "filterConfig": {
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
        },
    }


def update_floor_setting(
    project_id: str,
    enable_enforcement: bool = True,
    enforcement_mode: str = "INSPECT_ONLY",
    enable_cloud_logging: bool = True,
    multi_language: bool = True,
    rai_confidence: str = "HIGH",
    pi_confidence: str = "MEDIUM_AND_ABOVE",
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Updates the Model Armor floor setting for a given project."""
    url = f"{MODEL_ARMOR_BASE_URL}/projects/{project_id}/locations/global/floorSetting"
    headers = get_auth_headers()
    payload = build_floor_setting_payload(
        enable_enforcement=enable_enforcement,
        enforcement_mode=enforcement_mode,
        enable_cloud_logging=enable_cloud_logging,
        multi_language=multi_language,
        rai_confidence=rai_confidence,
        pi_confidence=pi_confidence,
    )
    update_mask = (
        "enableFloorSettingEnforcement,"
        "integratedServices,"
        "aiPlatformFloorSetting,"
        "googleMcpServerFloorSetting,"
        "floorSettingMetadata,"
        "filterConfig"
    )
    params = {"updateMask": update_mask}

    with httpx.Client(timeout=timeout) as client:
        resp = client.patch(url, headers=headers, params=params, json=payload)
        resp.raise_for_status()
        return resp.json()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Configure or inspect Google Cloud Model Armor Floor Settings.")
    parser.add_argument(
        "--project",
        "-p",
        default="",
        help="GCP Project ID. Defaults to GOOGLE_CLOUD_PROJECT or active ADC project.",
    )
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Describe active floor setting without making modifications.",
    )
    parser.add_argument(
        "--enable",
        dest="enable_enforcement",
        action="store_true",
        default=True,
        help="Enable floor setting enforcement (default: True).",
    )
    parser.add_argument(
        "--disable",
        dest="enable_enforcement",
        action="store_false",
        help="Disable floor setting enforcement.",
    )
    parser.add_argument(
        "--mode",
        choices=["INSPECT_ONLY", "INSPECT_AND_BLOCK"],
        default="INSPECT_ONLY",
        help="Enforcement mode for integrated services (default: INSPECT_ONLY).",
    )
    parser.add_argument(
        "--no-cloud-logging",
        dest="cloud_logging",
        action="store_false",
        default=True,
        help="Disable Cloud Logging for Model Armor sanitization results.",
    )
    parser.add_argument(
        "--no-multi-language",
        dest="multi_language",
        action="store_false",
        default=True,
        help="Disable multi-language detection.",
    )
    parser.add_argument(
        "--rai-confidence",
        choices=["HIGH", "MEDIUM_AND_ABOVE", "LOW_AND_ABOVE"],
        default="HIGH",
        help="Confidence threshold for RAI filters (default: HIGH).",
    )
    parser.add_argument(
        "--pi-confidence",
        choices=["HIGH", "MEDIUM_AND_ABOVE", "LOW_AND_ABOVE"],
        default="MEDIUM_AND_ABOVE",
        help="Confidence threshold for Prompt Injection / Jailbreak filter (default: MEDIUM_AND_ABOVE).",
    )

    args = parser.parse_args(argv)
    project_id = args.project or get_default_project()
    if not project_id:
        print("Error: Project ID must be specified via --project or GOOGLE_CLOUD_PROJECT.", file=sys.stderr)
        return 1

    try:
        if args.describe:
            setting = get_floor_setting(project_id)
            print(json.dumps(setting, indent=2))
            return 0

        print(
            f"Applying Model Armor floor settings to project: {project_id} (enforcement={args.enable_enforcement}, mode={args.mode})..."
        )
        updated = update_floor_setting(
            project_id=project_id,
            enable_enforcement=args.enable_enforcement,
            enforcement_mode=args.mode,
            enable_cloud_logging=args.cloud_logging,
            multi_language=args.multi_language,
            rai_confidence=args.rai_confidence,
            pi_confidence=args.pi_confidence,
        )
        print(f"Successfully configured Model Armor floor settings for {project_id}:")
        print(json.dumps(updated, indent=2))
        return 0
    except Exception as e:
        print(f"Error managing Model Armor floor settings: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
