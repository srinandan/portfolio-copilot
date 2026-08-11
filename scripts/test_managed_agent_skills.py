"""Benchmark and test script for Portfolio Copilot Managed Agent skills.

Tests each of the 6 skills against the deployed Managed Agent (portfolio-copilot-worker)
using Service Account impersonation to verify end-to-end execution, measure turn duration,
and validate typed output responses.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

import google.auth
from google.auth import impersonated_credentials
from google.auth.transport.requests import Request
from google import genai
from google.genai import types

# Add orchestrator src to Python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT_DIR, "orchestrator", "src"))

from orchestrator.contracts.drift_report import DriftReport
from orchestrator.contracts.goals_onboarding import GoalsOnboardingResult
from orchestrator.contracts.proposed_action import ProposedAction
from orchestrator.contracts.research_brief import ResearchBrief
from orchestrator.contracts.reviewer_verdict import ReviewerVerdict
from orchestrator.contracts.spending_analysis import SpendingReport
from orchestrator.managed_agents.dispatcher import (
    OUTPUT_SCHEMA_BY_SKILL,
    _extract_json_from_text,
    get_skill_tools,
    resolve_skill_instructions,
)
from orchestrator.registry_client import AgentRegistryClient

DEFAULT_PROJECT = "srinandans-next25-demo"
DEFAULT_IMPERSONATE_SA = "portfolio-copilot-frontend-sa@srinandans-next25-demo.iam.gserviceaccount.com"
DEFAULT_AGENT_ID = "portfolio-copilot-worker"

SKILL_TEST_PAYLOADS: Dict[str, Dict[str, Any]] = {
    "goals-onboarding": {
        "user_id": "usr_default",
        "trigger": "initial",
        "user_message": "I want to retire in 15 years with moderate risk tolerance and need $50,000 liquid reserve.",
    },
    "spending-analysis": {
        "user_id": "usr_default",
        "query_intent": "anomaly_check",
        "window_months": 3,
        "preloaded": {
            "total_income_usd": 15000.0,
            "total_outflow_usd": 8500.0,
            "savings_rate": 0.433,
            "reserve_months": 6.2,
            "category_breakdown": [
                {"category": "groceries", "amount_usd": 1200.0, "percentage": 14.1},
                {"category": "dining", "amount_usd": 800.0, "percentage": 9.4},
                {"category": "housing", "amount_usd": 3500.0, "percentage": 41.2},
            ],
            "anomalies": [
                {
                    "category": "dining",
                    "current_spend_usd": 800.0,
                    "trailing_avg_usd": 450.0,
                    "description": "Dining spend was 78% above 3-month trailing average.",
                }
            ],
        },
    },
    "portfolio-analysis": {
        "user_id": "usr_default",
        "preloaded": {
            "current_holdings": {
                "equity_usd": 65000.0,
                "fixed_income_usd": 15000.0,
                "cash_usd": 20000.0,
                "total_usd": 100000.0,
                "asset_allocations": [
                    {"asset_class": "US_EQUITY", "current_weight": 0.65, "target_weight": 0.50},
                    {"asset_class": "FIXED_INCOME", "current_weight": 0.15, "target_weight": 0.30},
                    {"asset_class": "CASH", "current_weight": 0.20, "target_weight": 0.20},
                ],
            },
            "target_allocation": {"US_EQUITY": 0.50, "FIXED_INCOME": 0.30, "CASH": 0.20},
            "ips": {"risk_tolerance": "moderate", "time_horizon_years": 15},
        },
    },
    "research": {
        "user_id": "usr_default",
        "ticker": "BND",
        "query": "Total Bond Market ETF expense ratio, yield, and suitability for rebalancing fixed income.",
    },
    "action-drafting": {
        "user_id": "usr_default",
        "drift_summary": "US Equity overweighted by 15% ($15,000), Fixed Income underweighted by 15% ($15,000).",
        "recommended_trades": [
            {"action": "SELL", "symbol": "VTI", "amount_usd": 15000.0, "reason": "Trim equity overweight"},
            {"action": "BUY", "symbol": "BND", "amount_usd": 15000.0, "reason": "Bring fixed income to target 30%"},
        ],
    },
    "reviewer": {
        "user_id": "usr_default",
        "proposed_action": {
            "action_id": "act_test_1",
            "user_id": "usr_default",
            "action_type": "REBALANCE",
            "description": "Sell $15,000 VTI, Buy $15,000 BND to restore target allocation.",
            "trades": [
                {"action": "SELL", "symbol": "VTI", "amount_usd": 15000.0},
                {"action": "BUY", "symbol": "BND", "amount_usd": 15000.0},
            ],
        },
        "ips_constraints": {
            "max_single_trade_usd": 50000.0,
            "prohibited_symbols": [],
            "approval_required_above_usd": 10000.0,
        },
    },
}


def get_impersonated_client(
    project_id: str,
    impersonate_sa: Optional[str] = None,
) -> genai.Client:
    """Creates a Google GenAI client using impersonated service account credentials."""
    source_credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    if impersonate_sa:
        print(f"[*] Impersonating service account: {impersonate_sa}")
        creds = impersonated_credentials.Credentials(
            source_credentials=source_credentials,
            target_principal=impersonate_sa,
            target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
            lifetime=3600,
        )
    else:
        creds = source_credentials

    return genai.Client(
        credentials=creds,
        project=project_id,
        location="global",
        vertexai=True,
    )


async def test_single_skill(
    client: genai.Client,
    agent_id: str,
    skill_short_name: str,
    payload: Dict[str, Any],
    project_id: str,
) -> Dict[str, Any]:
    """Tests a single skill turn against the Managed Agent and records timing."""
    print(f"\n=======================================================")
    print(f"Testing Skill: private-{skill_short_name}")
    print(f"=======================================================")

    # 1. Fetch Skill Instructions from Registry
    start_instr_time = time.time()
    try:
        async with AgentRegistryClient(project_id=project_id, location="global") as reg_client:
            instructions = await reg_client.get_skill_content(skill_short_name)
        instr_duration = time.time() - start_instr_time
        print(f"[+] Retrieved SKILL.md from registry in {instr_duration:.2f}s ({len(instructions)} bytes)")
    except Exception as e:
        print(f"[!] Registry fetch failed ({e}); reading local SKILL.md fallback")
        local_path = os.path.join(ROOT_DIR, "skills", skill_short_name, "SKILL.md")
        if os.path.exists(local_path):
            with open(local_path, "r", encoding="utf-8") as f:
                instructions = f.read()
        else:
            instructions = f"You are a helpful assistant for {skill_short_name}."
        instr_duration = 0.0

    # 2. Prepare payload
    input_text = json.dumps(payload, indent=2)
    schema = OUTPUT_SCHEMA_BY_SKILL.get(f"private-{skill_short_name}")
    schema_name = schema.__name__ if schema else "None"

    print(f"[*] Dispatching to agent '{agent_id}' (schema={schema_name})...")
    start_turn_time = time.time()
    first_event_time = None
    event_count = 0
    collected_text = []

    try:
        stream = await client.aio.interactions.create(
            agent=agent_id,
            input=input_text,
            environment={"type": "remote"},
            background=True,
            stream=True,
        )

        async for event in stream:
            event_count += 1
            if first_event_time is None:
                first_event_time = time.time() - start_turn_time
                print(f"  [>] First event received after {first_event_time:.2f}s (type: {event.event_type})")

            if hasattr(event, "step") and event.step:
                if hasattr(event.step, "content") and event.step.content:
                    for part in getattr(event.step.content, "parts", []):
                        if hasattr(part, "text") and part.text:
                            collected_text.append(part.text)

        total_turn_duration = time.time() - start_turn_time
        print(f"[+] Interaction completed in {total_turn_duration:.2f}s ({event_count} events)")

        # 3. Output validation
        full_text = "".join(collected_text).strip()
        parsed_json = _extract_json_from_text(full_text)
        validated = False
        if schema and parsed_json:
            try:
                schema.model_validate(parsed_json)
                validated = True
            except Exception:
                validated = False

        status = "SUCCESS" if event_count > 0 else "NO_EVENTS"
        return {
            "skill": f"private-{skill_short_name}",
            "schema": schema_name,
            "status": status,
            "ttft_seconds": round(first_event_time or 0.0, 2),
            "turn_seconds": round(total_turn_duration, 2),
            "events": event_count,
            "validated_schema": validated,
            "response_snippet": (full_text[:120] + "...") if len(full_text) > 120 else full_text,
        }
    except Exception as e:
        total_turn_duration = time.time() - start_turn_time
        print(f"[!] Interaction failed with error: {e}")
        return {
            "skill": f"private-{skill_short_name}",
            "schema": schema_name,
            "status": f"FAILED: {e}",
            "ttft_seconds": round(first_event_time or 0.0, 2),
            "turn_seconds": round(total_turn_duration, 2),
            "events": event_count,
            "validated_schema": False,
            "response_snippet": str(e),
        }


async def main():
    parser = argparse.ArgumentParser(description="Test Managed Agent Skills")
    parser.add_argument("--project", default=DEFAULT_PROJECT, help="GCP project ID")
    parser.add_argument("--impersonate-sa", default=DEFAULT_IMPERSONATE_SA, help="Service Account to impersonate")
    parser.add_argument("--agent-id", default=DEFAULT_AGENT_ID, help="Managed Agent ID")
    parser.add_argument("--skill", default=None, help="Specific skill short name to test (or all if omitted)")
    args = parser.parse_args()

    client = get_impersonated_client(
        project_id=args.project,
        impersonate_sa=args.impersonate_sa,
    )

    skills_to_test = [args.skill] if args.skill else list(SKILL_TEST_PAYLOADS.keys())
    results: List[Dict[str, Any]] = []

    total_start = time.time()
    for skill_name in skills_to_test:
        payload = SKILL_TEST_PAYLOADS.get(skill_name, {})
        res = await test_single_skill(
            client=client,
            agent_id=args.agent_id,
            skill_short_name=skill_name,
            payload=payload,
            project_id=args.project,
        )
        results.append(res)

    total_elapsed = time.time() - total_start

    print("\n" + "=" * 80)
    print("MANAGED AGENT BENCHMARK & TIMING SUMMARY")
    print("=" * 80)
    header = f"{'Skill Name':<30} | {'Status':<10} | {'TTFT (s)':<10} | {'Turn (s)':<10} | {'Events':<8} | {'Schema OK'}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['skill']:<30} | {r['status']:<10} | {r['ttft_seconds']:<10.2f} | {r['turn_seconds']:<10.2f} | {r['events']:<8} | {r['validated_schema']}"
        )
    print("=" * 80)
    print(f"Total benchmark elapsed time: {total_elapsed:.2f}s for {len(results)} skills.")


if __name__ == "__main__":
    asyncio.run(main())
