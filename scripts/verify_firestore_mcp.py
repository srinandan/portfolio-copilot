#!/usr/bin/env python3
"""CLI utility to verify connectivity and tool discovery with Firestore Remote MCP Server.

Usage:
  python3 scripts/verify_firestore_mcp.py [--url MCP_URL] [--project PROJECT_ID] [--location LOCATION]
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add orchestrator to Python path so we can import orchestrator modules
REPO_ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATOR_DIR = REPO_ROOT / "orchestrator"
if str(ORCHESTRATOR_DIR) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_DIR))

from src.orchestrator.data.firestore_mcp import (
    DEFAULT_FIRESTORE_MCP_URL,
    create_firestore_mcp_toolset,
    get_firestore_auth_headers,
    get_firestore_mcp_toolset_from_registry,
    list_available_mcp_tools,
)


async def async_main(args: argparse.Namespace) -> int:
    print(f"Connecting to Firestore Remote MCP Server at: {args.url}")
    try:
        headers = get_firestore_auth_headers()
        print("Successfully obtained Google Cloud ADC bearer token.")
    except Exception as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        return 1

    if args.use_registry:
        print(f"Resolving Firestore MCP toolset via Agent Registry (project={args.project}, location={args.location})...")
        toolset = get_firestore_mcp_toolset_from_registry(
            project_id=args.project,
            location=args.location,
        )
    else:
        print("Constructing direct McpToolset...")
        toolset = create_firestore_mcp_toolset(url=args.url)

    try:
        print("Discovering tools from Firestore MCP endpoint...")
        tools = await list_available_mcp_tools(toolset)
        print(f"Discovered {len(tools)} Firestore MCP tools:")
        for tool_name in sorted(tools):
            print(f"  • {tool_name}")
        await toolset.close()
        print("\nFirestore Remote MCP Server verification succeeded!")
        return 0
    except Exception as e:
        print(f"Tool discovery failed: {e}", file=sys.stderr)
        try:
            await toolset.close()
        except Exception:
            pass
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Test connection to Firestore Remote MCP Server.")
    parser.add_argument(
        "--url",
        default=DEFAULT_FIRESTORE_MCP_URL,
        help=f"Firestore Remote MCP URL (default: {DEFAULT_FIRESTORE_MCP_URL})",
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT"),
        help="Google Cloud project ID",
    )
    parser.add_argument(
        "--location",
        default=os.environ.get("AGENT_REGISTRY_LOCATION", "global"),
        help="Agent Registry location (default: global)",
    )
    parser.add_argument(
        "--use-registry",
        action="store_true",
        help="Attempt resolution through Agent Registry instead of direct McpToolset",
    )
    args = parser.parse_args()

    sys.exit(asyncio.run(async_main(args)))


if __name__ == "__main__":
    main()
