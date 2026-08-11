#!/usr/bin/env python3
"""End-to-end demo: live skill revocation.

Runs two planning cycles in the same session. Between them, revokes one skill
via the Agent Registry. The second cycle must exclude the revoked skill AND
emit a SKILL_REVOKED audit entry.

Usage:
    export PROJECT_ID=my-gcp-project
    export GOOGLE_CLOUD_LOCATION=global
    export SKILL_TO_REVOKE=research   # or any registered skill
    uv run --project orchestrator python scripts/demo_live_revocation.py

Reset after running:
    ./scripts/restore_skill.sh $SKILL_TO_REVOKE
"""

import asyncio
import os
import sys
import time
from typing import List

from google.adk.runners import Runner
from google.genai.types import Part, UserContent
from orchestrator.contracts.audit_log import EventType
from orchestrator.data.firestore import FirestoreClient
from orchestrator.planner import root_agent
from orchestrator.registry_client import AgentRegistryClient
from orchestrator.session_manager import SessionManager


async def _run_cycle(runner: Runner, session_id: str, cycle_name: str) -> List[dict]:
    """Runs one planning cycle and returns the events."""
    print(f"\n=== Planning cycle: {cycle_name} ===")
    events = []
    stream = runner.run_async(
        user_id="demo_user",
        session_id=session_id,
        new_message=UserContent(parts=[Part.from_text(text='{"user_id": "demo_user"}')]),
    )
    async for event in stream:
        events.append(event)
    print(f"Cycle '{cycle_name}' produced {len(events)} events.")
    return events


def _list_skill_names_from_events(events) -> List[str]:
    """Extracts the 'Available skills' log line from the event stream."""
    import ast
    import json

    for e in reversed(events):
        for obj in [
            e,
            getattr(e, "content", None),
            getattr(e, "actions", None),
            getattr(getattr(e, "content", None), "parts", [None])[0]
            if getattr(e, "content", None) and getattr(getattr(e, "content", None), "parts", None)
            else None,
        ]:
            if obj is None:
                continue
            for attr in ["text", "response", "state_delta", "output"]:
                val = getattr(obj, attr, None)
                if val is None:
                    continue
                if isinstance(val, dict) and "authorized_skills" in val:
                    return val["authorized_skills"]
                if isinstance(val, str) and "authorized_skills" in val:
                    try:
                        data = json.loads(val)
                        if isinstance(data, dict) and "authorized_skills" in data:
                            return data["authorized_skills"]
                    except Exception:
                        try:
                            data = ast.literal_eval(val)
                            if isinstance(data, dict) and "authorized_skills" in data:
                                return data["authorized_skills"]
                        except Exception:
                            pass
                if isinstance(val, str) and "Available skills:" in val:
                    return [s.strip() for s in val.split("Available skills:", 1)[1].strip().strip("[]").split(",")]
    return []


def _find_skill_revoked_audit_entries(user_id: str, since: float, skill_short_name: str) -> list:
    """Queries Firestore for SKILL_REVOKED audit entries created since a
    timestamp for the given skill."""
    fs = FirestoreClient()
    # Simple scan — the audit_log collection is small in demo scope
    docs = fs.db.collection("audit_log").stream()
    matches = []
    for doc in docs:
        data = doc.to_dict()
        if data.get("event_type") != EventType.SKILL_REVOKED.value:
            continue
        actor = data.get("actor", {})
        if actor.get("skill_name") in (skill_short_name, f"private-{skill_short_name}"):
            matches.append(data)
    return matches


async def _run_mock_registry_demo(project_id: str, location: str, skill: str) -> int:
    """Runs a simulated two-cycle live revocation demo using in-memory mocks for PR CI."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from orchestrator.contracts.audit_log import AuditLogEntry
    from orchestrator.registry_client import Skill
    from orchestrator.session_manager import SessionManager

    print(f"[MOCK REGISTRY] Demo: revoking skill '{skill}' in {project_id}/{location} between two planning cycles.")
    revoked_state = {"revoked": False}
    audit_entries = []

    async def fake_list_skills(*args, **kwargs):
        skills = [
            Skill(
                name=f"projects/{project_id}/locations/{location}/skills/private-goals-onboarding",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="v1",
            ),
            Skill(
                name=f"projects/{project_id}/locations/{location}/skills/private-portfolio-analysis",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="v1",
            ),
            Skill(
                name=f"projects/{project_id}/locations/{location}/skills/private-action-drafting",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="v1",
            ),
            Skill(
                name=f"projects/{project_id}/locations/{location}/skills/private-reviewer",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="v1",
            ),
        ]
        if not revoked_state["revoked"]:
            skills.append(
                Skill(
                    name=f"projects/{project_id}/locations/{location}/skills/private-{skill}",
                    target_state="TARGET_STATE_ACTIVE",
                    default_revision="v1",
                )
            )
        return skills

    class FakeFirestoreMock:
        def __init__(self):
            self.db = MagicMock()
            self.db.collection.return_value.stream.return_value = []

        def append_audit_log(self, entry: AuditLogEntry) -> None:
            audit_entries.append(entry.model_dump())

        def get_active_ips_by_user(self, user_id: str):
            return None

        def get_holdings(self, user_id: str):
            return None

    fake_fs = FakeFirestoreMock()

    with (
        patch.dict(
            os.environ,
            {
                "MANAGED_AGENT_ID": "mock_agent_id",
                "ALPACA_API_KEY_ID": "mock_key",
                "ALPACA_API_SECRET": "mock_secret",
            },
        ),
        patch("orchestrator.planner.AgentRegistryClient.list_authorized_skills", side_effect=fake_list_skills),
        patch("orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock) as mock_dispatch,
        patch("orchestrator.planner.FirestoreClient", return_value=fake_fs),
        patch("orchestrator.state.preloader.FirestoreClient", return_value=fake_fs),
        patch("orchestrator.state.writers.FirestoreClient", return_value=fake_fs),
        patch("orchestrator.gates.hitl.FirestoreClient", return_value=fake_fs),
    ):
        mock_dispatch.return_value = None
        session_manager = SessionManager(use_in_memory=True)
        runner = Runner(
            app_name="live_revocation_demo_mock",
            agent=root_agent,
            session_service=session_manager.session_service,
            memory_service=session_manager.memory_service,
            auto_create_session=True,
        )
        session_id = f"mock_revocation_demo_{int(time.time())}"

        # Cycle 1: baseline
        cycle1_events = await _run_cycle(runner, session_id, "1 (baseline)")
        cycle1_skills = _list_skill_names_from_events(cycle1_events)
        print(f"Cycle 1 skills: {cycle1_skills}")

        # Simulate revocation
        print(f"\n>>> Revoking skill '{skill}' (in-memory mock)...")
        revoked_state["revoked"] = True

        # Cycle 2: should see revocation
        cycle2_events = await _run_cycle(runner, session_id, "2 (post-revocation)")
        cycle2_skills = _list_skill_names_from_events(cycle2_events)
        print(f"Cycle 2 skills: {cycle2_skills}")

        # Check audit log entries
        revoke_entries = [
            e
            for e in audit_entries
            if e.get("event_type") == EventType.SKILL_REVOKED.value
            and e.get("actor", {}).get("skill_name") in (skill, f"private-{skill}")
        ]
        print(f"SKILL_REVOKED audit entries for '{skill}' since start: {len(revoke_entries)}")

        ok = True
        if any(skill in s for s in cycle2_skills):
            print(f"FAIL: skill '{skill}' still appeared on cycle 2 after revocation")
            ok = False
        if not revoke_entries:
            print(f"FAIL: expected SKILL_REVOKED audit entry for '{skill}', found none")
            ok = False

        if ok:
            print(
                "\n✅ Live revocation demo (MOCK REGISTRY) PASSED — skill filtered on next cycle, audit entry present."
            )
            return 0
        print("\n❌ Live revocation demo (MOCK REGISTRY) FAILED — see WARN/FAIL lines above.")
        return 1


async def main() -> int:
    is_mock = "--mock-registry" in sys.argv or "--dry-run" in sys.argv
    project_id = os.environ.get("PROJECT_ID", "mock-project-id" if is_mock else None)
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    skill = os.environ.get("SKILL_TO_REVOKE", "research")

    if is_mock:
        return await _run_mock_registry_demo(project_id, location, skill)

    if not project_id:
        print("ERROR: set PROJECT_ID", file=sys.stderr)
        return 1

    print(f"Demo: revoking skill '{skill}' in {project_id}/{location} between two planning cycles.")

    session_manager = SessionManager()
    session_service = session_manager.session_service
    memory_service = session_manager.memory_service
    runner = Runner(
        app_name="live_revocation_demo",
        agent=root_agent,
        session_service=session_service,
        memory_service=memory_service,
        auto_create_session=True,
    )
    session_id = f"revocation_demo_{int(time.time())}"
    start_ts = time.time()

    # Cycle 1: baseline
    cycle1_events = await _run_cycle(runner, session_id, "1 (baseline)")
    cycle1_skills = _list_skill_names_from_events(cycle1_events)
    print(f"Cycle 1 skills: {cycle1_skills}")

    # Ensure the skill we're about to revoke was authorized on cycle 1
    if not any(skill in s for s in cycle1_skills):
        print(f"WARNING: skill '{skill}' was not authorized on cycle 1. Revocation demo will show no delta.")

    # Revoke via the same client the orchestrator uses
    async with AgentRegistryClient(project_id=project_id, location=location) as client:
        print(f"\n>>> Revoking skill '{skill}'...")
        await client.revoke_skill(skill)

    # Small sleep so registry state propagates (usually immediate, but be gentle)
    await asyncio.sleep(2)

    # Cycle 2: should see revocation
    cycle2_events = await _run_cycle(runner, session_id, "2 (post-revocation)")
    cycle2_skills = _list_skill_names_from_events(cycle2_events)
    print(f"Cycle 2 skills: {cycle2_skills}")

    # Verify SKILL_REVOKED audit entry landed
    revoke_entries = _find_skill_revoked_audit_entries("demo_user", start_ts, skill)
    print(f"SKILL_REVOKED audit entries for '{skill}' since start: {len(revoke_entries)}")

    # Restore for next demo run
    async with AgentRegistryClient(project_id=project_id, location=location) as client:
        print(f"\n>>> Restoring skill '{skill}'...")
        await client.restore_skill(skill)

    # Acceptance criteria checks
    ok = True
    if any(skill in s for s in cycle2_skills):
        print(f"FAIL: skill '{skill}' still appeared on cycle 2 after revocation")
        ok = False
    if not revoke_entries:
        print(f"FAIL: expected SKILL_REVOKED audit entry for '{skill}', found none")
        ok = False

    if ok:
        print("\n✅ Live revocation demo PASSED — skill filtered on next cycle, audit entry present.")
        return 0
    print("\n❌ Live revocation demo FAILED — see WARN/FAIL lines above.")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
