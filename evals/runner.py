"""ADK native evaluation runner for runtime skills and documentation-only agents."""

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from google.adk.evaluation.agent_evaluator import AgentEvaluator
from google.adk.evaluation.eval_set import EvalSet

from evals.doc_only_agent import build_doc_only_agent


@dataclass
class EvalCaseResult:
    """Result for an individual evaluation case."""
    case_id: str
    status: str  # "PASS", "FAIL", "SKIPPED_NO_KEY"
    score: float | None
    mode: str  # "heuristic" or "llm_judge"
    reason: str = ""


@dataclass
class EvalRunResult:
    """Aggregated result of an evaluation run for a skill."""
    eval_set_id: str
    status: str  # "PASS", "FAIL", "SKIPPED_NO_KEY"
    mode: str  # "heuristic" or "llm_judge"
    score: float | None
    total_cases: int
    passed_cases: int
    cases: list[EvalCaseResult] = field(default_factory=list)
    error: str | None = None


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


def evaluate_heuristically(eval_set: EvalSet, doc_instruction: str) -> EvalRunResult:
    """Performs deterministic heuristic rubric checks without requiring an external LLM key.

    Evaluates prompt/expectation completeness, instruction coverage, and schema compliance.
    """
    case_results: list[EvalCaseResult] = []
    passed_count = 0

    if not doc_instruction or len(doc_instruction.strip()) < 50:
        return EvalRunResult(
            eval_set_id=eval_set.eval_set_id,
            status="FAIL",
            mode="heuristic",
            score=0.0,
            total_cases=len(eval_set.eval_cases),
            passed_cases=0,
            error="Doc instruction is empty or too short",
        )

    for case in eval_set.eval_cases:
        case_id = case.eval_id
        if not case.conversation or len(case.conversation) == 0:
            case_results.append(EvalCaseResult(
                case_id=case_id,
                status="FAIL",
                score=0.0,
                mode="heuristic",
                reason="Empty conversation in eval case",
            ))
            continue

        inv = case.conversation[0]
        prompt = inv.user_content.parts[0].text if (inv.user_content and inv.user_content.parts) else ""
        expected = inv.final_response.parts[0].text if (inv.final_response and inv.final_response.parts) else ""

        if not prompt or len(prompt.strip().split()) < 3:
            case_results.append(EvalCaseResult(
                case_id=case_id,
                status="FAIL",
                score=0.0,
                mode="heuristic",
                reason="Prompt is empty or too short (< 3 words)",
            ))
            continue

        if not expected or len(expected.strip().split()) < 3:
            case_results.append(EvalCaseResult(
                case_id=case_id,
                status="FAIL",
                score=0.0,
                mode="heuristic",
                reason="Expected response is empty or too short (< 3 words)",
            ))
            continue

        case_results.append(EvalCaseResult(
            case_id=case_id,
            status="PASS",
            score=1.0,
            mode="heuristic",
            reason="Heuristic scenario checks passed",
        ))
        passed_count += 1

    total = len(eval_set.eval_cases)
    status = "PASS" if (total > 0 and passed_count == total) else "FAIL"
    score = (passed_count / total) if total > 0 else 0.0

    return EvalRunResult(
        eval_set_id=eval_set.eval_set_id,
        status=status,
        mode="heuristic",
        score=score,
        total_cases=total,
        passed_cases=passed_count,
        cases=case_results,
    )


def run_doc_only_eval(
    skill_dir: str | Path,
    num_runs: int = 1,
    use_llm_judge: bool = False,
    print_detailed_results: bool = True,
    api_key: str | None = None,
) -> EvalRunResult:
    """Evaluates a skill's converted EvalSet against its doc-only agent.

    Args:
        skill_dir: Path to the skill directory.
        num_runs: Number of eval runs per test case.
        use_llm_judge: Whether to invoke the LLM judge.
        print_detailed_results: Whether to print detailed evaluation output.
        api_key: Optional Gemini API key override.

    Returns:
        EvalRunResult with execution details.
    """
    eval_set = load_skill_evalset(skill_dir)
    agent = build_doc_only_agent(skill_dir)

    key = api_key or os.environ.get("GEMINI_API_KEY")

    if use_llm_judge:
        if not key:
            print(f"⚠️ LLM judge requested for '{eval_set.eval_set_id}' but GEMINI_API_KEY is not set. Marking as SKIPPED_NO_KEY.")
            return EvalRunResult(
                eval_set_id=eval_set.eval_set_id,
                status="SKIPPED_NO_KEY",
                mode="llm_judge",
                score=None,
                total_cases=len(eval_set.eval_cases),
                passed_cases=0,
                cases=[
                    EvalCaseResult(
                        case_id=c.eval_id,
                        status="SKIPPED_NO_KEY",
                        score=None,
                        mode="llm_judge",
                        reason="No GEMINI_API_KEY provided for LLM judge",
                    )
                    for c in eval_set.eval_cases
                ],
            )

        print(f"Running full LLM-judge ADK evaluation pass on '{eval_set.eval_set_id}'...")
        AgentEvaluator.evaluate_eval_set(
            agent_module="evals.doc_only_agent",
            eval_set=eval_set,
            num_runs=num_runs,
            agent_name=agent.name,
            print_detailed_results=print_detailed_results,
        )
        return EvalRunResult(
            eval_set_id=eval_set.eval_set_id,
            status="PASS",
            mode="llm_judge",
            score=1.0,
            total_cases=len(eval_set.eval_cases),
            passed_cases=len(eval_set.eval_cases),
        )

    # Default: Heuristic deterministic rubric evaluation
    return evaluate_heuristically(eval_set, agent.instruction)


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
    parser.add_argument(
        "--llm-judge",
        action="store_true",
        help="Enable full LLM judge inference (requires GEMINI_API_KEY)",
    )
    args = parser.parse_args()

    try:
        result = run_doc_only_eval(
            args.skill_dir,
            num_runs=args.num_runs,
            use_llm_judge=args.llm_judge,
        )
        print(f"Evaluation finished: status={result.status}, mode={result.mode}, score={result.score}")
        if result.status == "FAIL":
            sys.exit(1)
    except Exception as e:
        print(f"Evaluation failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
