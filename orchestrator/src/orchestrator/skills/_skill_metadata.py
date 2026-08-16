"""Shared helpers to extract skill metadata from SKILL.md YAML frontmatter and body."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


class SkillMetadataError(RuntimeError):
    """Raised when required skill metadata (version or approval scope) cannot be found at startup."""

    pass


@dataclass(frozen=True)
class SkillMetadata:
    """Bundle of everything the orchestrator needs to trace an audit event
    back to a specific skill file at a specific version."""

    skill_dir_name: str  # e.g. "goals-onboarding"
    version: str  # from metadata.version — e.g. "0.2.0"
    approval_scope: Optional[str]  # from top-level approval_scope line — may be None if missing


def _clean_skill_name(name: str) -> str:
    """Strip any path prefix or 'private-' prefix to get the canonical skill directory name."""
    short = name.split("/")[-1] if "/" in name else name
    if short.startswith("private-"):
        return short[len("private-") :]
    return short


def _find_skill_md(skill_dir_name: str) -> Optional[Path]:
    """Finds SKILL.md for a given skill directory name across development, package, and container layouts."""
    short_name = _clean_skill_name(skill_dir_name)

    # 1. If explicit SKILLS_DIR is provided in environment, strictly check that directory only
    if "SKILLS_DIR" in os.environ:
        candidate = Path(os.environ["SKILLS_DIR"]) / short_name / "SKILL.md"
        if candidate.exists():
            return candidate
        return None

    # 2. Check inside Python package directory (if SKILL.md files are bundled inside orchestrator/skills/<name>/SKILL.md)
    pkg_dir = Path(__file__).resolve().parent
    for candidate_dir in [pkg_dir / short_name, pkg_dir / "skills" / short_name]:
        candidate = candidate_dir / "SKILL.md"
        if candidate.exists():
            return candidate

    # 3. Walk up ancestors for dev/repo layout (<parent>/skills/<name>/SKILL.md)
    for parent in [pkg_dir] + list(pkg_dir.parents):
        candidate = parent / "skills" / short_name / "SKILL.md"
        if candidate.exists():
            return candidate

    # 4. Check importlib.resources for installed wheel/package resources
    try:
        import importlib.resources

        ref = importlib.resources.files("orchestrator.skills").joinpath(short_name, "SKILL.md")
        if hasattr(ref, "is_file") and ref.is_file():
            if hasattr(ref, "as_posix"):
                p = Path(ref.as_posix())
                if p.exists():
                    return p
    except Exception:
        pass

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
    metadata = frontmatter.get("metadata", {}) if isinstance(frontmatter.get("metadata"), dict) else {}
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


def verify_all_skills_metadata(skill_names: Optional[list[str]] = None) -> None:
    """Verifies that SKILL.md files can be found and read for all registered skills when local files or SKILLS_DIR is configured.

    If no local SKILL.md files are present and SKILLS_DIR is not set, skills are resolved dynamically from Agent Registry at runtime.
    """
    if skill_names is None:
        from ..planner import PIPELINE_SKILL_ORDER

        skill_names = PIPELINE_SKILL_ORDER

    missing: list[str] = []
    found_any = False
    for name in skill_names:
        clean = _clean_skill_name(name)
        path = _find_skill_md(clean)
        if path is None:
            missing.append(clean)
        else:
            found_any = True
            try:
                read_skill_version(clean)
                read_skill_approval_scope(clean)
            except Exception as e:
                raise SkillMetadataError(f"Failed reading SKILL.md metadata for {clean}: {e}") from e

    # If SKILLS_DIR was explicitly set, or if some skills were found locally but others were missing, enforce completeness
    if missing and ("SKILLS_DIR" in os.environ or found_any):
        unique_missing = sorted(set(missing))
        raise SkillMetadataError(
            f"Startup verification failed: could not locate SKILL.md for skill(s): {', '.join(unique_missing)}. "
            "Ensure SKILL.md files are bundled with the deployment or SKILLS_DIR is set."
        )
