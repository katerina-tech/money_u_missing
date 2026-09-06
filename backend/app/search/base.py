"""The SearchProvider contract.

Web search is a commodity with several interchangeable vendors and no reason to
be married to one. The interface below is the intersection of what Tavily,
Brave and Serper all offer - a query in, ranked results with a URL, title and
snippet out - which is everything the discovery pipeline actually needs.

Absent from the interface on purpose: anything vendor-specific. No provider's
"answer" or "summary" field is used, because a search engine's generated
summary is exactly the kind of unattributable text this product must not turn
into an opportunity record.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SearchHit:
    """One result. Deliberately thin."""

    url: str
    title: str
    snippet: str
    published_at: datetime | None = None
    #: The provider's own relevance figure, where it gives one. Never used in
    #: the match score - it ranks web pages, not opportunities for this person.
    provider_score: float | None = None


@dataclass
class SearchResponse:
    hits: list[SearchHit] = field(default_factory=list)
    ok: bool = True
    error: str | None = None
    provider: str = ""


class SearchProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def search(
        self, query: str, *, max_results: int = 10, region: str | None = None
    ) -> SearchResponse:
        """Run one query. Must not raise - failures come back on the response."""

    @abstractmethod
    def health_check(self) -> bool: ...

    @property
    def available(self) -> bool:
        return True


class NullSearchProvider(SearchProvider):
    """No search configured. The supported default, not an error state.

    Returns an explicit failure rather than an empty result set, so the UI can
    say "live search is unavailable, showing verified cached opportunities"
    instead of implying the web contained nothing.
    """

    name = "none"

    def search(
        self, query: str, *, max_results: int = 10, region: str | None = None
    ) -> SearchResponse:
        return SearchResponse(
            hits=[],
            ok=False,
            error="No web search provider is configured.",
            provider=self.name,
        )

    def health_check(self) -> bool:
        return False

    @property
    def available(self) -> bool:
        return False
