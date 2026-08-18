"""Skill retrieval — the "Retrieve" stage of the pipeline (ADR-0022, Phase 3b).

Turns the prompt + the authorized skills' manifests into intent-relevant
*candidates* for the planner. Retrieval sits behind a pluggable interface: v1
ships :class:`ListAllRetriever` (every authorized skill is a candidate), and a
semantic implementation slots in behind the same :class:`Retriever` protocol
once the catalog outgrows a single planner context — with no change to callers.

Authorization and disabled-state are already enforced upstream at fetch
(``get_skill_manifest`` only returns manifests for skills the principal may
use), so retrieval works over an already-authorized manifest set.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, runtime_checkable

from ..skills.manifest import SkillManifest


@dataclass(frozen=True)
class SkillCandidate:
    """A retrieval candidate — a skill the prompt might call for.

    Carries the manifest text a selector reasons over: ``summary`` and
    ``applies_when`` are what a semantic retriever embeds and what the LLM prune
    reads. ``id`` is the clean skill name.
    """

    id: str
    summary: str
    applies_when: str


@runtime_checkable
class Retriever(Protocol):
    """Produces candidates for a prompt from the authorized manifest set."""

    def retrieve(self, prompt: str, manifests: Mapping[str, SkillManifest]) -> list[SkillCandidate]: ...


class ListAllRetriever:
    """v1 retrieval: return every authorized skill as a candidate.

    Recall-biased by construction — it never drops a skill, leaving narrowing to
    the planner policy (and, later, a semantic retriever behind this interface).
    """

    def retrieve(self, prompt: str, manifests: Mapping[str, SkillManifest]) -> list[SkillCandidate]:
        return [
            SkillCandidate(id=name, summary=m.summary, applies_when=m.applies_when)
            for name, m in manifests.items()
        ]


# The default retrieval strategy the orchestrator uses today.
DEFAULT_RETRIEVER: Retriever = ListAllRetriever()
