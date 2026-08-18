#!/usr/bin/env python3
"""CLI utility to verify connectivity and tool discovery with BigQuery Remote MCP Server.

Usage:
  python3 scripts/verify_bigquery_mcp.py [--url MCP_URL] [--project PROJECT_ID] [--location LOCATION] [--use-registry]
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

from src.orchestrator.data.bigquery_mcp import (
    DEFAULT_BIGQUERY_MCP_URL,
    BigQueryMCPClient,
    create_bigquery_mcp_toolset,
    get_bigquery_auth_headers,
    get_bigquery_mcp_toolset_from_registry,
    list_available_mcp_tools,
)


async def async_main(args: argparse.Namespace) -> int:
    print(f"Connecting to BigQuery Remote MCP Server at: {args.url}")
    try:
        headers = get_bigquery_auth_headers()
        print("Successfully obtained Google Cloud ADC bearer token for BigQuery Remote MCP.")
    except Exception as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        return 1

    if args.use_registry:
        print(
            f"Resolving BigQuery MCP toolset via Agent Registry (project={args.project}, location={args.location})..."
        )
        toolset = get_bigquery_mcp_toolset_from_registry(
            project_id=args.project,
            location=args.location,
        )
    else:
        print("Constructing direct McpToolset...")
        toolset = create_bigquery_mcp_toolset(url=args.url)

    try:
        print("Discovering tools from BigQuery MCP endpoint...")
        tools = await list_available_mcp_tools(toolset)
        print(f"Discovered {len(tools)} BigQuery MCP tools:")
        for tool_name in sorted(tools):
            print(f"  • {tool_name}")
        await toolset.close()

        if args.project:
            print(f"\nProbing dataset discovery with BigQueryMCPClient for project '{args.project}'...")
            client = BigQueryMCPClient(project=args.project, url=args.url)
            try:
                datasets = client.list_datasets(args.project)
                print(f"Found {len(datasets)} datasets: {[d.get('datasetId', d) for d in datasets]}")

                if args.dataset:
                    print(f"Probing table discovery in dataset '{args.dataset}'...")
                    tables = client.list_tables(dataset_id=args.dataset, project_id=args.project)
                    print(f"Found {len(tables)} tables: {[t.get('tableId', t) for t in tables]}")

                    if args.table:
                        print(f"Inspecting schema for table '{args.dataset}.{args.table}'...")
                        schema = client.get_table_schema(
                            dataset_id=args.dataset, table_id=args.table, project_id=args.project
                        )
                        print(f"Schema metadata: {schema}")
            except Exception as e:
                print(f"BigQueryMCPClient sample queries deferred or failed: {e}")

        print("\nBigQuery Remote MCP Server verification succeeded!")
        return 0
    except Exception as e:
        print(f"Tool discovery failed: {e}", file=sys.stderr)
        try:
            await toolset.close()
        except Exception:
            pass
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Test connection to BigQuery Remote MCP Server.")
    parser.add_argument(
        "--url",
        default=DEFAULT_BIGQUERY_MCP_URL,
        help=f"BigQuery Remote MCP URL (default: {DEFAULT_BIGQUERY_MCP_URL})",
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
    parser.add_argument(
        "--dataset",
        default="portfolio_copilot",
        help="BigQuery dataset to inspect (default: portfolio_copilot)",
    )
    parser.add_argument(
        "--table",
        default="checking_transactions",
        help="BigQuery table to inspect (default: checking_transactions)",
    )
    args = parser.parse_args()

    sys.exit(asyncio.run(async_main(args)))


if __name__ == "__main__":
    main()
