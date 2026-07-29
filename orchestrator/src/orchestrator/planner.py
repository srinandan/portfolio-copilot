import os
from typing import Any
from google.adk import Context
from google.adk.workflow import node, Workflow
# from google.adk.integrations.agent_registry import AgentRegistry

@node(name="get_skills", rerun_on_resume=False)
async def get_skills_from_registry(ctx: Context, node_input: Any):
    """Queries the Agent Registry for available skills.

    This is currently a skeleton implementation demonstrating the
    registry-driven dynamic planning trace.
    """
    project_id = os.environ.get("PROJECT_ID", "dummy-project")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")

    # Example of what this will eventually do (F4 dependency):
    # registry = AgentRegistry(project_id=project_id, location=location)
    # agents_response = registry.list_agents()

    # For now, this is a skeleton showing the planning trace
    print(f"Goal received: {node_input}")
    print(f"Queried registry in {project_id}/{location}")
    return ["research", "action_drafting"]

@node(name="dummy_skill_execution", rerun_on_resume=False)
async def dummy_skill_execution(ctx: Context, node_input: Any):
    """Executes a dummy skill as part of the dynamic plan."""
    print(f"Executing skill: {node_input}")
    return f"{node_input}_completed"

@node(rerun_on_resume=True)
async def root_planner(ctx: Context, node_input: Any):
    """The root dynamic workflow orchestrator."""
    skills = await ctx.run_node(get_skills_from_registry, node_input=node_input)
    print(f"Available skills: {skills}")

    results = []
    for skill in skills:
        result = await ctx.run_node(dummy_skill_execution, node_input=skill)
        results.append(result)

    return results

root_agent = Workflow(
    name="portfolio_copilot_planner",
    description="Dynamic planner for Portfolio Copilot that queries Agent Registry to construct a plan.",
    edges=[("START", root_planner)],
)
