"""ADK native evaluation runner for runtime skills and documentation-only agents."""

import argparse
import sys
from pathlib import Path

from google.adk.evaluation.agent_evaluator import AgentEvaluator
from google.adk.evaluation.eval_set import EvalSet

from evals.doc_only_agent import build_doc_only_agent


def load_skill_evalset(skill_dir: str | Path) -> EvalSet:
    """Loads the .evalset.json file for a given skill directory.

    Args:
        skill_dir: Path to the skill directory (e.g. skills/goals-onboarding).

    Returns:
        The parsed and validated ADK EvalSet object.
    """
    skill_path = Path(skill_dir)
    json_files = list(skill_path.glob("*.evalset.json"))
    if not json_files:
        raise FileNotFoundError(f"No .evalset.json found in {skill_dir}")

    eval_set_path = json_files[0]
    return EvalSet.model_validate_json(eval_set_path.read_text(encoding="utf-8"))


def run_doc_only_eval(
    skill_dir: str | Path,
    num_runs: int = 1,
    print_detailed_results: bool = True,
) -> None:
    """Evaluates a skill's converted EvalSet against its stripped doc-only agent.

    Args:
        skill_dir: Path to the skill directory.
        num_runs: Number of eval runs per test case.
        print_detailed_results: Whether to print detailed evaluation output.
    """
    eval_set = load_skill_evalset(skill_dir)
    print(f"Loaded EvalSet '{eval_set.eval_set_id}' with {len(eval_set.eval_cases)} test cases.")

    # Instantiate the doc-only agent
    agent = build_doc_only_agent(skill_dir)
    print(f"Created doc-only agent '{agent.name}' (tools: {len(agent.tools or [])}, instruction chars: {len(agent.instruction)}).")

    # Evaluate using ADK's AgentEvaluator
    # Note: When evaluating in-memory or via module, AgentEvaluator supports evaluate_eval_set
    print("Running ADK evaluation pass...")
    AgentEvaluator.evaluate_eval_set(
        agent_module="evals.doc_only_agent",
        eval_set=eval_set,
        num_runs=num_runs,
        agent_name=agent.name,
        print_detailed_results=print_detailed_results,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Portfolio Copilot skills via native ADK.")
    parser.add_argument(
        "skill_dir",
        help="Path to the skill directory (e.g. skills/goals-onboarding)",
    )
    parser.add_argument(
        "--num-runs",
        type=int,
        default=1,
        help="Number of evaluation runs per case (default: 1)",
    )
    args = parser.parse_args()

    try:
        run_doc_only_eval(args.skill_dir, num_runs=args.num_runs)
    except Exception as e:
        print(f"Evaluation failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
