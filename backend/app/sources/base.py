"""The OpportunitySource contract.

Every way an opportunity can enter the system implements this interface, and
the discovery pipeline knows nothing else about where records come from. Adding
a source is writing one class and registering it; it is not touching the
pipeline, the matcher or the API.

Sources return :class:`~app.domain.opportunity.OpportunityCandidate` - raw,
untrusted material - never a finished :class:`~app.domain.opportunity.Opportunity`.
That gap is where injection screening, extraction into a closed schema, safety
classification and validation happen. A source that could return a finished
Opportunity would be a source that could bypass all of them.

What is deliberately absent: there is no scraper base class, no login support,
no cookie handling. See docs/DATA_PROVENANCE.md for what that rules out and why.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.enums import IncomeStreamCategory, SearchIntent, SourceType
from app.domain.evidence import utcnow
from app.logging_config import Event, log_event

logger = logging.getLogger(__name__)


@dataclass
class SearchQuery:
    """One query, with the intent that produced it."""

    text: str
    intent: SearchIntent
    #: Where the results are expected to be relevant. Not a filter the source
    #: must honour - a hint it may use if it can.
    region: str | None = "DE"
    language: str | None = None


@dataclass
class SearchPlan:
    """The output of the planner: what to look for, and the hard constraints.

    Constraints here are the user's, not the source's. A source that cannot
    honour them returns what it can and the deterministic matcher applies them
    afterwards - which is the only place they are actually enforced.
    """

    queries: list[SearchQuery] = field(default_factory=list)
    categories: list[IncomeStreamCategory] = field(default_factory=list)
    countries: list[str] = field(default_factory=lambda: ["DE"])
    languages: list[str] = field(default_factory=lambda: ["de", "en"])
    max_hours_per_week: float | None = None
    remote_only: bool = False
    #: Free-text summary shown to the user so the search is inspectable, not
    #: a black box that returns whatever it returns.
    rationale: str = ""

    def limited(self, max_queries: int) -> SearchPlan:
        return SearchPlan(
            queries=self.queries[:max_queries],
            categories=self.categories,
            countries=self.countries,
            languages=self.languages,
            max_hours_per_week=self.max_hours_per_week,
            remote_only=self.remote_only,
            rationale=self.rationale,
        )


@dataclass
class SourceHealth:
    source_id: str
    ok: bool
    checked_at: datetime = field(default_factory=utcnow)
    detail: str = ""


@dataclass
class SourceResult:
    """What one source returned, including how it failed if it did.

    A partial failure is reported rather than swallowed: the UI says "live
    search is unavailable, showing verified cached opportunities" only because
    the pipeline can tell the difference between "no results" and "did not run".
    """

    source_id: str
    candidates: list[Any] = field(default_factory=list)
    ok: bool = True
    error: str | None = None
    queries_run: int = 0


class OpportunitySource(ABC):
    """A place opportunities come from."""

    #: Stable identifier, used as the primary key in ``opportunity_sources``.
    id: str = "abstract"
    name: str = "Abstract source"
    source_type: SourceType = SourceType.CURATED
    #: Recorded when the source is registered: the terms or licence under which
    #: we access it. Written down so the answer to "are you allowed to do that?"
    #: is in the code, not in someone's memory.
    access_basis: str = "unspecified"

    @abstractmethod
    def search(self, plan: SearchPlan) -> SourceResult:
        """Return candidates for this plan. Must not raise."""

    def fetch_details(self, reference: str) -> str | None:
        """Retrieve the full text behind a candidate, when the source supports it.

        Returns ``None`` when it does not - a search API's snippet may be all
        there is, and pretending otherwise would mean fabricating detail.
        """
        return None

    @abstractmethod
    def health_check(self) -> SourceHealth:
        """Whether this source is usable right now. Must not raise."""

    # ------------------------------------------------------------- helpers
    def _failed(self, error: Exception | str, queries_run: int = 0) -> SourceResult:
        message = str(error)
        log_event(
            logger,
            Event.SOURCE_FAILED,
            "source failed",
            level=logging.WARNING,
            source_id=self.id,
            error=message[:300],
        )
        return SourceResult(
            source_id=self.id, candidates=[], ok=False, error=message, queries_run=queries_run
        )

    def _succeeded(self, candidates: list[Any], queries_run: int) -> SourceResult:
        log_event(
            logger,
            Event.SOURCE_QUERIED,
            "source returned candidates",
            source_id=self.id,
            candidate_count=len(candidates),
            queries_run=queries_run,
        )
        return SourceResult(
            source_id=self.id, candidates=candidates, ok=True, queries_run=queries_run
        )
