"""Shared helpers to extract skill metadata from SKILL.md YAML frontmatter and body."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass(frozen=True)
class SkillMetadata:
    """Bundle of everything the orchestrator needs to trace an audit event
    back to a specific skill file at a specific version."""

    skill_dir_name: str  # e.g. "goals-onboarding"
    version: str  # from metadata.version — e.g. "0.2.0"
    approval_scope: Optional[str]  # from top-level approval_scope line — may be None if missing


def _find_skill_md(skill_dir_name: str) -> Optional[Path]:
    """Walks up from this file to find <ancestor>/skills/<skill_dir_name>/SKILL.md."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        candidate = parent / "skills" / skill_dir_name / "SKILL.md"
        if candidate.exists():
            return candidate
    return None


def _parse_frontmatter(skill_md_path: Path) -> dict:
    """Extract the YAML frontmatter dict from a SKILL.md file, or empty dict."""
    content = skill_md_path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    parsed = yaml.safe_load(parts[1])
    return parsed if isinstance(parsed, dict) else {}


def _extract_approval_scope(skill_md_path: Path) -> Optional[str]:
    """Reads the 'Approval scope' line from the 'Registry metadata' section.

    Format in SKILL.md:
        - Approval scope: `read:holdings,read:ips`

    Returns the backtick-quoted value, stripped. None if not found.
    """
    content = skill_md_path.read_text(encoding="utf-8")
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- Approval scope:") or stripped.startswith("- Approval Scope:"):
            _, _, rest = stripped.partition(":")
            rest = rest.strip()
            if rest.startswith("`") and rest.endswith("`"):
                return rest[1:-1]
            return rest or None
    return None


def read_skill_version(skill_dir_name: str) -> str:
    """Reads metadata.version from skills/<skill_dir_name>/SKILL.md YAML frontmatter."""
    path = _find_skill_md(skill_dir_name)
    if path is None:
        return "0.1.0"
    frontmatter = _parse_frontmatter(path)
    metadata = (
        frontmatter.get("metadata", {})
        if isinstance(frontmatter.get("metadata"), dict)
        else {}
    )
    version = metadata.get("version")
    if not version:
        raise RuntimeError(f"No metadata.version found in frontmatter of {path}")
    return str(version)


def read_skill_approval_scope(skill_dir_name: str) -> Optional[str]:
    """Reads the '- Approval scope: `...`' line from SKILL.md body.

    Returns the scope string (e.g. 'read:holdings,read:ips') or None if not found.
    """
    path = _find_skill_md(skill_dir_name)
    if path is None:
        return None
    return _extract_approval_scope(path)


def read_skill_metadata(skill_dir_name: str) -> SkillMetadata:
    """Reads version + approval_scope in one shot."""
    return SkillMetadata(
        skill_dir_name=skill_dir_name,
        version=read_skill_version(skill_dir_name),
        approval_scope=read_skill_approval_scope(skill_dir_name),
    )
