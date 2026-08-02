"""Evaluates all runtime skills, validates their EvalSets, and generates a structured Markdown report."""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from google.adk.evaluation.eval_set import EvalSet
from evals.doc_only_agent import build_doc_only_agent


def evaluate_skills(skills_dir: Path) -> List[Dict[str, Any]]:
    """Evaluates all skills in the skills directory.

    Args:
        skills_dir: Directory containing skill subdirectories.

    Returns:
        List of skill report dictionaries.
    """
    reports = []
    skill_dirs = sorted([d for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])

    for skill_path in skill_dirs:
        skill_name = skill_path.name
        skill_md = skill_path / "SKILL.md"
        evalset_files = list(skill_path.glob("*.evalset.json"))

        report: Dict[str, Any] = {
            "name": skill_name,
            "path": str(skill_path),
            "has_skill_md": skill_md.exists(),
            "skill_md_chars": 0,
            "has_evalset": len(evalset_files) > 0,
            "evalset_file": evalset_files[0].name if evalset_files else None,
            "case_count": 0,
            "cases": [],
            "status": "PASS",
            "errors": [],
        }

        # Validate SKILL.md
        if not skill_md.exists():
            report["status"] = "FAIL"
            report["errors"].append("Missing SKILL.md")
        else:
            doc_text = skill_md.read_text(encoding="utf-8")
            report["skill_md_chars"] = len(doc_text)
            if len(doc_text.strip()) == 0:
                report["status"] = "FAIL"
                report["errors"].append("SKILL.md is empty")

        # Validate EvalSet JSON
        if not evalset_files:
            report["status"] = "FAIL"
            report["errors"].append("Missing *.evalset.json")
        else:
            try:
                evalset_text = evalset_files[0].read_text(encoding="utf-8")
                evalset = EvalSet.model_validate_json(evalset_text)
                report["case_count"] = len(evalset.eval_cases)

                for c in evalset.eval_cases:
                    prompt = ""
                    expected = ""
                    if c.conversation and len(c.conversation) > 0:
                        inv = c.conversation[0]
                        if inv.user_content and inv.user_content.parts:
                            prompt = inv.user_content.parts[0].text or ""
                        if inv.final_response and inv.final_response.parts:
                            expected = inv.final_response.parts[0].text or ""

                    report["cases"].append({
                        "id": c.eval_id,
                        "description": getattr(c, "description", ""),
                        "prompt": prompt,
                        "expected": expected,
                    })

                if report["case_count"] == 0:
                    report["status"] = "FAIL"
                    report["errors"].append("EvalSet contains 0 test cases")
            except Exception as e:
                report["status"] = "FAIL"
                report["errors"].append(f"Invalid EvalSet JSON: {e}")

        # Validate doc-only agent construction
        if report["has_skill_md"]:
            try:
                agent = build_doc_only_agent(skill_path)
                if not agent.instruction:
                    report["status"] = "FAIL"
                    report["errors"].append("Doc-only agent instruction is empty")
            except Exception as e:
                report["status"] = "FAIL"
                report["errors"].append(f"Doc-only agent build error: {e}")

        reports.append(report)

    return reports


def generate_markdown_report(reports: List[Dict[str, Any]]) -> str:
    """Generates GitHub-flavored markdown report from evaluation results."""
    total_skills = len(reports)
    passed_skills = sum(1 for r in reports if r["status"] == "PASS")
    total_cases = sum(r["case_count"] for r in reports)

    md = []
    md.append("# 🎯 Skill Evaluation & Validation Report\n")
    md.append(f"**Total Skills:** {total_skills} | **Passed:** {passed_skills}/{total_skills} | **Total Eval Cases:** {total_cases}\n")

    # Summary table
    md.append("## Summary\n")
    md.append("| Skill | Status | Cases | Doc Size | EvalSet File |")
    md.append("|---|:---:|:---:|:---:|---|")
    for r in reports:
        status_badge = "✅ PASS" if r["status"] == "PASS" else "❌ FAIL"
        doc_size = f"{r['skill_md_chars']:,} chars" if r["has_skill_md"] else "N/A"
        eval_file = r["evalset_file"] or "None"
        md.append(f"| `{r['name']}` | {status_badge} | {r['case_count']} | {doc_size} | `{eval_file}` |")

    # Details per skill
    md.append("\n## Detailed Skill Evaluation Suites\n")
    for r in reports:
        md.append(f"### `{r['name']}`\n")
        if r["errors"]:
            md.append("**Errors:**\n")
            for err in r["errors"]:
                md.append(f"- ⚠️ {err}")
            md.append("")

        if r["cases"]:
            md.append("<details><summary><b>View " + str(len(r["cases"])) + " Test Cases</b></summary>\n")
            md.append("| Test Case ID | Prompt Scenario | Ground Truth Expectation |")
            md.append("|---|---|---|")
            for c in r["cases"]:
                prompt_snippet = c["prompt"].replace("\n", " ")
                if len(prompt_snippet) > 80:
                    prompt_snippet = prompt_snippet[:77] + "..."
                expected_snippet = c["expected"].replace("\n", " ")
                if len(expected_snippet) > 100:
                    expected_snippet = expected_snippet[:97] + "..."
                md.append(f"| `{c['id']}` | {prompt_snippet} | {expected_snippet} |")
            md.append("\n</details>\n")

    return "\n".join(md)


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    skills_dir = repo_root / "skills"

    reports = evaluate_skills(skills_dir)
    md_report = generate_markdown_report(reports)

    print(md_report)

    # If running in GitHub Actions, append to GITHUB_STEP_SUMMARY
    step_summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary_file:
        with open(step_summary_file, "a", encoding="utf-8") as f:
            f.write(md_report + "\n")
        print(f"\nWritten evaluation report to $GITHUB_STEP_SUMMARY ({step_summary_file})")

    # Exit non-zero if any skill failed
    any_failed = any(r["status"] != "PASS" for r in reports)
    if any_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
