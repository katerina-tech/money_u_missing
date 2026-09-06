"""Graph state and the dependency bundle nodes receive.

State is a plain TypedDict of data. Nodes receive ``(state, deps)`` and return a
partial update - no node holds a service, opens a database session, or reaches
for a global. That is what makes the pipeline testable one node at a time and
what lets the whole discovery path run against
:class:`~app.llm.testing.ScriptedProvider` with no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from sqlalchemy.orm import Session

from app.domain.enums import Intent
from app.domain.matching import BestNextMove, RankedOpportunity
from app.domain.opportunity import Opportunity, OpportunityCandidate
from app.domain.profile import UserProfile
from app.llm.base import LLMProvider
from app.security.guard import InjectionGuard
from app.services.legal_facts import LegalFactRepository
from app.sources.base import SearchPlan
from app.sources.registry import SourceRegistry


@dataclass
class Deps:
    """Everything a node might need, injected once when the graph is built."""

    session: Session
    provider: LLMProvider
    guard: InjectionGuard
    registry: SourceRegistry
    facts: LegalFactRepository
    #: Present so nodes can record analytics without importing a session factory.
    user_id: str | None = None


class DiscoveryState(TypedDict, total=False):
    """What flows through the discovery graph.

    Every stage's output is kept rather than overwritten, so the API can report
    what happened at each step - how many candidates were considered, how many
    were blocked and why. A discovery run that returns three results has to be
    able to account for the other forty, or the user reasonably concludes the
    product simply did not find much.
    """

    profile: UserProfile
    intent: Intent

    plan: SearchPlan
    candidates: list[OpportunityCandidate]
    opportunities: list[Opportunity]
    ranked: list[RankedOpportunity]
    best_next_move: BestNextMove | None

    # --- run diagnostics, surfaced to the user
    sources_queried: int
    sources_failed: list[str]
    live_search_used: bool
    considered: int
    blocked_unsafe: int
    blocked_injection: int
    extraction_failures: int
    duplicates_removed: int
    stale_removed: int
    rejected: list[tuple[str, str]]
    notices: list[str]

    error: str | None
    extra: dict[str, Any]


def initial_state(profile: UserProfile) -> DiscoveryState:
    return DiscoveryState(
        profile=profile,
        intent=Intent.OPPORTUNITY_DISCOVERY,
        candidates=[],
        opportunities=[],
        ranked=[],
        best_next_move=None,
        sources_queried=0,
        sources_failed=[],
        live_search_used=False,
        considered=0,
        blocked_unsafe=0,
        blocked_injection=0,
        extraction_failures=0,
        duplicates_removed=0,
        stale_removed=0,
        rejected=[],
        notices=[],
        error=None,
        extra={},
    )
