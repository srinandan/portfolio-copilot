import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from google.adk import Context
from google.adk.workflow import node

from ...contracts.audit_log import Actor, ActorType, AuditLogEntry, EventType
from ...data.firestore import FirestoreClient
from ...logger import get_logger
from .logic import calculate_drift

logger = get_logger(__name__)


def _load_skill_version() -> str:
    """Reads metadata.version from skills/portfolio-analysis/SKILL.md frontmatter."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        candidate = parent / "skills" / "portfolio-analysis" / "SKILL.md"
        if candidate.exists():
            content = candidate.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    parsed = yaml.safe_load(parts[1])
                    if isinstance(parsed, dict) and "metadata" in parsed and "version" in parsed["metadata"]:
                        return str(parsed["metadata"]["version"])
            raise RuntimeError(f"No metadata.version found in frontmatter of {candidate}")
    raise RuntimeError("Could not find skills/portfolio-analysis/SKILL.md")


SKILL_VERSION = _load_skill_version()


@node(name="portfolio_analysis_skill", rerun_on_resume=True)
async def portfolio_analysis_skill(ctx: Context, node_input: Any):
    """Skill for analyzing portfolio drift against the active IPS."""
    user_id = node_input.get("user_id") if isinstance(node_input, dict) else None
    if not user_id:
        raise ValueError("user_id is required")

    firestore_client = FirestoreClient()
    now = datetime.now(timezone.utc)

    # 1. Audit log: Skill invoked
    try:
        firestore_client.append_audit_log(
            AuditLogEntry(
                log_id=str(uuid.uuid4()),
                event_type=EventType.SKILL_INVOKED,
                timestamp=now,
                actor=Actor(
                    type=ActorType.AGENT,
                    skill_name="private-portfolio-analysis",
                    skill_version=SKILL_VERSION,
                ),
                detail=f"Portfolio analysis skill invoked for user {user_id}",
            )
        )
    except Exception as e:
        logger.warning(f"Failed to append audit log for skill invocation: {e}")

    try:
        ips = firestore_client.get_active_ips_by_user(user_id)
        if not ips:
            logger.info(f"No active IPS found for user {user_id}; declining portfolio analysis.")
            try:
                firestore_client.append_audit_log(
                    AuditLogEntry(
                        log_id=str(uuid.uuid4()),
                        event_type=EventType.SKILL_INVOCATION_FAILED,
                        timestamp=datetime.now(timezone.utc),
                        actor=Actor(
                            type=ActorType.AGENT,
                            skill_name="private-portfolio-analysis",
                            skill_version=SKILL_VERSION,
                        ),
                        detail=f"Portfolio analysis declined: No active IPS found for user {user_id}",
                    )
                )
            except Exception as audit_err:
                logger.warning(f"Failed to append audit log: {audit_err}")

            yield {
                "status": "declined",
                "message": "No active Investment Policy Statement (IPS) found for the user. Please complete goals onboarding first.",
            }
            return

        holdings = firestore_client.get_holdings(user_id)
        if not holdings:
            logger.info(f"No holdings found for user {user_id}; declining portfolio analysis.")
            try:
                firestore_client.append_audit_log(
                    AuditLogEntry(
                        log_id=str(uuid.uuid4()),
                        event_type=EventType.SKILL_INVOCATION_FAILED,
                        timestamp=datetime.now(timezone.utc),
                        actor=Actor(
                            type=ActorType.AGENT,
                            skill_name="private-portfolio-analysis",
                            skill_version=SKILL_VERSION,
                        ),
                        detail=f"Portfolio analysis declined: No holdings found for user {user_id}",
                    )
                )
            except Exception as audit_err:
                logger.warning(f"Failed to append audit log: {audit_err}")

            yield {
                "status": "declined",
                "message": f"No holdings found for user {user_id}.",
            }
            return

        drift_report = calculate_drift(holdings, ips)

        yield {
            "status": "completed",
            "drift_report": drift_report.model_dump(),
        }
    except Exception as e:
        logger.error(f"Portfolio analysis skill failed: {e}")
        try:
            firestore_client.append_audit_log(
                AuditLogEntry(
                    log_id=str(uuid.uuid4()),
                    event_type=EventType.SKILL_INVOCATION_FAILED,
                    timestamp=datetime.now(timezone.utc),
                    actor=Actor(
                        type=ActorType.AGENT,
                        skill_name="private-portfolio-analysis",
                        skill_version=SKILL_VERSION,
                    ),
                    detail=f"Portfolio analysis failed with error: {e}",
                )
            )
        except Exception as audit_err:
            logger.warning(f"Failed to append audit log on failure: {audit_err}")
        raise
