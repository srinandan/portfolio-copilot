"""Shared helper to extract skill metadata and versions from SKILL.md frontmatter."""

from pathlib import Path

import yaml


def read_skill_version(skill_dir_name: str) -> str:
    """Reads metadata.version from skills/<skill_dir_name>/SKILL.md YAML frontmatter."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        candidate = parent / "skills" / skill_dir_name / "SKILL.md"
        if candidate.exists():
            content = candidate.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    parsed = yaml.safe_load(parts[1])
                    if isinstance(parsed, dict) and "metadata" in parsed and "version" in parsed["metadata"]:
                        return str(parsed["metadata"]["version"])
            raise RuntimeError(f"No metadata.version found in frontmatter of {candidate}")
    return "0.1.0"
