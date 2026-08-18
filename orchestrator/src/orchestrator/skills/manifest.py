"""Self-describing skill manifests (ADR-0022, Phase 1).

Each skill ships a machine-readable manifest — carried in the ``manifest:``
block of its ``SKILL.md`` front-matter — declaring the artifacts it
``requires`` / ``produces``, whether it may run in parallel, and any
structural compliance trigger. **Structure** (a skill's dependencies) lives
here, with the skill; **policy** (intent-based routing) lives with the
planner. Keeping dependencies with the skill is what lets the catalog grow
without editing the orchestrator. See
``docs/adr/0022-intent-driven-skill-planning.md`` and
``docs/design/intent-driven-skill-planning.md``.

Phase 1 is schema + loader + validation only — there is **no behaviour
change**. Nothing here is wired into planning yet; the deterministic
resolver/scheduler that consumes these manifests lands in Phase 2.

Open question #1 in the design doc (manifest home: front-matter vs a sibling
``manifest.json``) is resolved here in favour of ``SKILL.md`` front-matter, to
keep a single source of truth per skill.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Iterable, Optional

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from ._skill_metadata import _clean_skill_name, _find_skill_md, _parse_frontmatter


class SkillManifestError(RuntimeError):
    """Raised when a skill manifest cannot be loaded, parsed, or validated."""


class Artifact(str, Enum):
    """The shared vocabulary that links skills together.

    Artifacts are the currency of the dependency graph: a skill's
    ``produces`` set is another skill's ``requires`` set. This is the initial
    set drawn from the existing skill contracts and preloaders (design §2).
    """

    SPENDING_REPORT = "spending_report"
    ACTIVE_IPS = "active_ips"
    DRIFT_REPORT = "drift_report"
    HOLDINGS = "holdings"
    RESEARCH_QUESTION = "research_question"
    RESEARCH_BRIEFS = "research_briefs"
    PROPOSED_ACTION = "proposed_action"
    REVIEWER_VERDICT = "reviewer_verdict"
    HITL_DECISION = "hitl_decision"
    EXECUTION_RESULT = "execution_result"


# Artifacts that enter the graph from outside the skill set — preloaded facts
# or prompt-derived inputs that no skill *produces*. Every ``requires`` entry
# must be either produced by some skill or listed here, otherwise the
# dependency is unsatisfiable. `active_ips` is deliberately *not* here: it has
# a real producer (`goals-onboarding`), and the resolver's already-satisfied
# skip (Phase 2) handles the common case where it is preloaded from Firestore.
PRELOADED_ARTIFACTS: frozenset[Artifact] = frozenset(
    {
        Artifact.HOLDINGS,
        Artifact.RESEARCH_QUESTION,
    }
)


_MANDATORY_IF_RE = re.compile(r"^\s*(?P<artifact>[a-z_]+)\s+(?P<predicate>exists)\s*$")


class MandatoryIf(BaseModel):
    """A structural compliance trigger of the form ``<artifact> exists``.

    This is how a skill declares "run me whenever this artifact is present,
    regardless of intent" — e.g. the reviewer re-enters the plan whenever a
    ``proposed_action`` has been drafted. Phase 2 evaluates it against the
    selected/available artifacts via :meth:`satisfied`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact: Artifact
    predicate: str = "exists"

    @field_validator("predicate")
    @classmethod
    def _only_exists(cls, v: str) -> str:
        if v != "exists":
            raise ValueError(f"unsupported mandatory_if predicate {v!r}; only 'exists' is supported")
        return v

    def satisfied(self, available: Iterable[str]) -> bool:
        """True when the trigger artifact is present (Phase 2 evaluation hook)."""
        return self.artifact.value in {str(a) for a in available}

    def __str__(self) -> str:
        return f"{self.artifact.value} {self.predicate}"


class SkillManifest(BaseModel):
    """Machine-readable metadata shipped with a skill (design §2).

    ``extra="forbid"`` catches typos in the front-matter block (e.g.
    ``require:`` for ``requires:``) at load time rather than silently dropping
    a dependency.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Short skill id (no `private-` prefix); matches the skill directory name
    # and the registry `private-<id>`.
    id: str
    # One-liner; the primary text embedded for semantic retrieval (Phase 3).
    summary: str
    # Natural-language intent trigger used by the planner (and search).
    applies_when: str
    # Inputs that must exist; drive prerequisite resolution (Phase 2).
    requires: tuple[Artifact, ...] = ()
    # Inputs consumed if available; do NOT pull in prerequisites.
    optional: tuple[Artifact, ...] = ()
    # Outputs; the other half of the dependency graph.
    produces: tuple[Artifact, ...] = ()
    # Whether this skill may share a schedule layer with same-layer peers.
    parallelizable: bool
    # Structural compliance trigger, or None. Accepts the string form
    # "<artifact> exists" in front-matter and parses it into a MandatoryIf.
    mandatory_if: Optional[MandatoryIf] = None
    # Marks the cold-start floor skill (design §4.2 / open question #4).
    # Unused in Phase 1; every current manifest leaves this false.
    default: bool = False

    @field_validator("mandatory_if", mode="before")
    @classmethod
    def _parse_mandatory_if(cls, v):
        if v is None or isinstance(v, (MandatoryIf, dict)):
            return v
        if isinstance(v, str):
            m = _MANDATORY_IF_RE.match(v)
            if not m:
                raise ValueError(f"mandatory_if must be '<artifact> exists', got {v!r}")
            return {"artifact": m.group("artifact"), "predicate": m.group("predicate")}
        raise ValueError(f"mandatory_if must be a string or null, got {type(v).__name__}")

    @model_validator(mode="after")
    def _no_self_dependency(self) -> "SkillManifest":
        overlap = set(self.requires) & set(self.produces)
        if overlap:
            names = ", ".join(sorted(a.value for a in overlap))
            raise ValueError(f"skill {self.id!r} both requires and produces: {names}")
        return self


# The six skills that ship with the orchestrator today (design §3). Used as
# the default set for validation and the documented-DAG test.
DEFAULT_MANIFEST_SKILLS: tuple[str, ...] = (
    "spending-analysis",
    "goals-onboarding",
    "portfolio-analysis",
    "research",
    "action-drafting",
    "reviewer",
)


def load_manifest(skill_dir_name: str) -> SkillManifest:
    """Loads and validates the manifest from a skill's ``SKILL.md`` front-matter.

    Raises :class:`SkillManifestError` if the SKILL.md cannot be located, has
    no ``manifest:`` block, or the block fails schema validation.
    """
    clean = _clean_skill_name(skill_dir_name)
    path = _find_skill_md(clean)
    if path is None:
        raise SkillManifestError(f"Could not locate SKILL.md for skill {clean!r}")

    frontmatter = _parse_frontmatter(path)
    raw = frontmatter.get("manifest")
    if raw is None:
        raise SkillManifestError(f"SKILL.md for {clean!r} has no 'manifest:' front-matter block ({path})")
    if not isinstance(raw, dict):
        raise SkillManifestError(f"'manifest:' block for {clean!r} must be a mapping, got {type(raw).__name__} ({path})")

    try:
        manifest = SkillManifest.model_validate(raw)
    except ValidationError as e:
        raise SkillManifestError(f"Invalid manifest for {clean!r} ({path}): {e}") from e

    if manifest.id != clean:
        raise SkillManifestError(
            f"manifest id {manifest.id!r} does not match skill directory {clean!r} ({path})"
        )
    return manifest


def load_all_manifests(skill_names: Optional[Iterable[str]] = None) -> dict[str, SkillManifest]:
    """Loads manifests for the given skills (default: the six shipped skills).

    Keyed by clean skill name (no ``private-`` prefix).
    """
    names = list(skill_names) if skill_names is not None else list(DEFAULT_MANIFEST_SKILLS)
    manifests: dict[str, SkillManifest] = {}
    for name in names:
        clean = _clean_skill_name(name)
        manifests[clean] = load_manifest(clean)
    return manifests


def producer_of(artifact: Artifact, manifests: dict[str, SkillManifest]) -> Optional[str]:
    """Returns the clean skill name that produces ``artifact``, or None.

    If more than one skill produces it, the first in iteration order is
    returned; :func:`validate_manifest_graph` rejects ambiguous producers.
    """
    for name, m in manifests.items():
        if artifact in m.produces:
            return name
    return None


def validate_manifest_graph(manifests: dict[str, SkillManifest]) -> None:
    """Validates the requires/produces graph across a set of manifests.

    Enforces the invariants the design relies on:
      * every produced artifact has exactly one producer (no ambiguity);
      * every ``requires`` artifact is either produced by some skill or is a
        recognized preloaded/external input (:data:`PRELOADED_ARTIFACTS`);
      * every ``mandatory_if`` trigger references a produced artifact.

    Individual artifacts are already constrained to the :class:`Artifact`
    vocabulary by field validation; this checks the *relationships* between
    skills. Raises :class:`SkillManifestError` on the first violation.
    """
    # 1. Unique producers.
    producers: dict[Artifact, str] = {}
    for name, m in manifests.items():
        for artifact in m.produces:
            if artifact in producers:
                raise SkillManifestError(
                    f"artifact {artifact.value!r} is produced by both {producers[artifact]!r} and {name!r}"
                )
            producers[artifact] = name

    produced = set(producers.keys())
    satisfiable = produced | PRELOADED_ARTIFACTS

    # 2. Every required artifact is satisfiable.
    for name, m in manifests.items():
        for artifact in m.requires:
            if artifact not in satisfiable:
                raise SkillManifestError(
                    f"skill {name!r} requires {artifact.value!r}, which no skill produces "
                    f"and is not a recognized preloaded artifact"
                )

    # 3. Every mandatory_if trigger references something a skill produces.
    for name, m in manifests.items():
        if m.mandatory_if is not None and m.mandatory_if.artifact not in produced:
            raise SkillManifestError(
                f"skill {name!r} has mandatory_if on {m.mandatory_if.artifact.value!r}, "
                f"which no skill produces"
            )


def verify_all_manifests(skill_names: Optional[Iterable[str]] = None) -> None:
    """Startup guard: load and graph-validate all skill manifests.

    Mirrors ``verify_all_skills_metadata``: when no local ``SKILL.md`` files
    are present and ``SKILLS_DIR`` is unset (registry-only deployments),
    manifests are resolved at runtime, so verification is skipped. When local
    skill files exist, every listed skill must carry a valid manifest and the
    graph must be consistent.

    Raises :class:`SkillManifestError` on the first problem.
    """
    names = list(skill_names) if skill_names is not None else list(DEFAULT_MANIFEST_SKILLS)

    if not any(_find_skill_md(_clean_skill_name(n)) is not None for n in names):
        # No bundled skill files — registry mode; nothing to verify locally.
        return

    manifests = load_all_manifests(names)
    validate_manifest_graph(manifests)
