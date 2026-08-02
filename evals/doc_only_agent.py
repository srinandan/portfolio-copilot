"""Documentation-only minimal test agent builder for runtime skills.

Tests the property: Can an agent with nothing but SKILL.md's text answer correctly?
Deliberately stripped down — no tools, no orchestrator plumbing, no database access.
"""

from pathlib import Path
from google.adk.agents import LlmAgent

DEFAULT_MODEL = "gemini-2.5-pro"


def build_doc_only_agent(skill_dir: str | Path, model: str = DEFAULT_MODEL) -> LlmAgent:
    """Builds a stripped-down LlmAgent containing only the skill's SKILL.md instruction.

    Args:
        skill_dir: Path to the skill directory containing SKILL.md.
        model: Model name to use for the doc-only agent.

    Returns:
        An LlmAgent configured with SKILL.md as instruction and no tools.
    """
    skill_path = Path(skill_dir)
    skill_md_file = skill_path / "SKILL.md"
    try:
        if not skill_md_file.is_file():
            raise FileNotFoundError(f"SKILL.md not found in {skill_dir}")
        skill_md = skill_md_file.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError, OSError) as e:
        raise FileNotFoundError(f"SKILL.md not found or unreadable in {skill_dir}: {e}") from e
    skill_name = skill_path.name

    return LlmAgent(
        name=f"doc_only_{skill_name.replace('-', '_')}",
        model=model,
        instruction=skill_md,
        tools=[],  # deliberately none — this tests the documentation alone
    )
