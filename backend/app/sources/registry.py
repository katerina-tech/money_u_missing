"""Which sources exist, and what we are permitted to take from each.

The registry is the answer to "where did this opportunity come from and were
you allowed to have it?" - a question an accelerator, a publisher or a
regulator can reasonably ask. Every entry records an ``access_basis`` in
prose, and that text is surfaced in the API and in docs/DATA_PROVENANCE.md.

The feed list is deliberately short and conservative. Feeds are included only
where the publisher offers one for exactly this purpose. Where a feed's
availability could not be confirmed at the time of writing, the entry is marked
``NOT YET VERIFIED`` and is disabled by default rather than shipped hopefully -
a source that 404s on every run is worse than one that is honestly absent.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings, get_settings
from app.search.factory import build_search_provider
from app.security.web import SafeFetcher
from app.sources.base import OpportunitySource
from app.sources.feeds import RSSOpportunitySource
from app.sources.local import CuratedOpportunitySource, DemoOpportunitySource
from app.sources.websearch import SearchAPIOpportunitySource


@dataclass(frozen=True)
class FeedRegistration:
    """A publisher feed, and the basis on which we read it."""

    source_id: str
    name: str
    feed_url: str
    access_basis: str
    #: False when the feed's existence or format could not be confirmed while
    #: writing this file. Such entries ship disabled and are listed in the docs
    #: as pending verification rather than presented as working sources.
    verified: bool


#: Candidate feeds. Enabling one is a two-line change plus a note in
#: docs/DATA_PROVENANCE.md recording who checked it and when.
FEEDS: tuple[FeedRegistration, ...] = (
    FeedRegistration(
        source_id="eu_funding_tenders",
        name="EU Funding & Tenders Portal",
        feed_url="https://ec.europa.eu/info/funding-tenders/opportunities/rss/calls.rss",
        access_basis=(
            "Public EU funding portal. Content is published under the "
            "Commission's reuse policy for the express purpose of "
            "redistribution."
        ),
        verified=False,
    ),
    FeedRegistration(
        source_id="bmwk_foerderung",
        name="Bundesministerium fuer Wirtschaft und Klimaschutz - Foerderung",
        feed_url="https://www.bmwk.de/SiteGlobals/BMWI/Forms/Listen/RSSNewsfeed/rss.xml",
        access_basis="Federal ministry public newsfeed.",
        verified=False,
    ),
)


class SourceRegistry:
    """Builds the active source set for a run."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._fetcher = SafeFetcher(self._settings)

    def build(self, *, include_demo: bool | None = None) -> list[OpportunitySource]:
        """The sources to query, in the order their results should be trusted.

        Curated first, then live, then demo. Ordering matters because
        de-duplication keeps the best-evidenced record, and a curated record
        with a human behind it should win over a search result about the same
        listing.
        """
        settings = self._settings
        sources: list[OpportunitySource] = [
            CuratedOpportunitySource(settings.data_dir / "curated_opportunities.json")
        ]

        for feed in FEEDS:
            if not feed.verified:
                continue
            sources.append(
                RSSOpportunitySource(
                    source_id=feed.source_id,
                    name=feed.name,
                    feed_url=feed.feed_url,
                    access_basis=feed.access_basis,
                    fetcher=self._fetcher,
                    settings=settings,
                )
            )

        if settings.live_search_available:
            sources.append(
                SearchAPIOpportunitySource(
                    build_search_provider(settings),
                    fetcher=self._fetcher,
                    settings=settings,
                )
            )

        show_demo = settings.demo_mode_enabled if include_demo is None else include_demo
        if show_demo:
            sources.append(
                DemoOpportunitySource(settings.data_dir / "demo_opportunities.json")
            )
        return sources

    def describe(self) -> list[dict[str, object]]:
        """Provenance for the API and the docs. Includes disabled entries."""
        rows: list[dict[str, object]] = []
        for source in self.build():
            rows.append(
                {
                    "id": source.id,
                    "name": source.name,
                    "type": source.source_type.value,
                    "access_basis": source.access_basis,
                    "enabled": True,
                }
            )
        for feed in FEEDS:
            if feed.verified:
                continue
            rows.append(
                {
                    "id": feed.source_id,
                    "name": feed.name,
                    "type": "RSS",
                    "access_basis": feed.access_basis,
                    "enabled": False,
                    "note": "NOT YET VERIFIED - feed availability unconfirmed; disabled.",
                }
            )
        return rows
