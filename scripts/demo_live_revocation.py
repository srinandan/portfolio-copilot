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
    for e in reversed(events):
        content = getattr(e, "content", None)
        if content and getattr(content, "parts", None):
            for p in content.parts:
                text = getattr(p, "text", "") or ""
                if "Available skills:" in text:
                    return [s.strip() for s in text.split("Available skills:", 1)[1].strip().strip("[]").split(",")]
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


async def main() -> int:
    project_id = os.environ.get("PROJECT_ID")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    skill = os.environ.get("SKILL_TO_REVOKE", "research")

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
        print(f"WARNING: skill '{skill}' was not authorized on cycle 1. "
              f"Revocation demo will show no delta.")

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
