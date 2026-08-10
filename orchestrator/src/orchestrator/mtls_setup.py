"""Automatic mTLS and Workload Identity configuration for Agent Runtime / Cloud Run."""

import json
import os

from .logger import get_logger

logger = get_logger(__name__)

WELL_KNOWN_SPIFFE_CERT = "/var/run/secrets/workload-spiffe-credentials/certificates.pem"
WELL_KNOWN_SPIFFE_KEY = "/var/run/secrets/workload-spiffe-credentials/private_key.pem"
GENERATED_CERT_CONFIG = "/tmp/google_api_certificate_config.json"


def setup_workload_mtls() -> bool:
    """Configures GOOGLE_API_CERTIFICATE_CONFIG if SPIFFE workload credentials exist.

    In Agent Runtime / Cloud Run with Agent Identity, SPIFFE certificates are mounted at
    /var/run/secrets/workload-spiffe-credentials/. google-auth issues certificate-bound
    tokens against these certificates. In order for GCP client libraries (Firestore,
    BigQuery, Agent Registry) to authenticate successfully over mTLS, google-auth requires
    a certificate config JSON file pointed to by GOOGLE_API_CERTIFICATE_CONFIG.

    Returns:
        bool: True if workload mTLS configuration was detected and initialized, False otherwise.
    """
    if not (os.path.exists(WELL_KNOWN_SPIFFE_CERT) and os.path.exists(WELL_KNOWN_SPIFFE_KEY)):
        return False

    existing_config = os.environ.get("GOOGLE_API_CERTIFICATE_CONFIG")
    if existing_config and os.path.exists(existing_config):
        return True

    try:
        config_data = {
            "version": 1,
            "cert_configs": {
                "workload": {
                    "cert_path": WELL_KNOWN_SPIFFE_CERT,
                    "key_path": WELL_KNOWN_SPIFFE_KEY,
                }
            },
        }
        with open(GENERATED_CERT_CONFIG, "w", encoding="utf-8") as f:
            json.dump(config_data, f)
        os.environ["GOOGLE_API_CERTIFICATE_CONFIG"] = GENERATED_CERT_CONFIG
        os.environ["GOOGLE_API_USE_CLIENT_CERTIFICATE"] = "true"
        logger.info("Initialized workload mTLS certificate configuration at %s", GENERATED_CERT_CONFIG)
        return True
    except Exception as e:
        logger.warning("Failed to initialize workload mTLS certificate configuration: %s", e)
        return False
