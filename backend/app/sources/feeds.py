"""RSS and Atom feed sources.

Feeds are the best-behaved way to read a third-party site: they are published
*in order to be consumed by machines*, they are small, they are stable, and
consuming one is unambiguously within the publisher's intent. That is why this
is the first real-source implementation rather than a scraper.

Parsing uses ``defusedxml``. A feed is untrusted XML from a third party, and
the stdlib parser is vulnerable to entity-expansion attacks that turn a 2 KB
document into gigabytes of memory. Rejecting that class of input is not
optional when the URL can be user-influenced.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from defusedxml import ElementTree as DefusedET

from app.config import Settings, get_settings
from app.domain.enums import SourceType
from app.domain.opportunity import OpportunityCandidate
from app.security.web import FetchBlockedError, SafeFetcher
from app.sources.base import OpportunitySource, SearchPlan, SourceHealth, SourceResult

logger = logging.getLogger(__name__)

_NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}

MAX_ITEMS_PER_FEED = 40


def _text(element: object, *paths: str) -> str:
    for path in paths:
        found = element.find(path, _NAMESPACES) if hasattr(element, "find") else None
        if found is not None and (found.text or "").strip():
            return str(found.text).strip()
    return ""


def _parse_when(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        value = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class RSSOpportunitySource(OpportunitySource):
    """Reads one publisher's feed.

    Registered once per feed URL, so each publisher has its own health status
    and its own row in ``opportunity_sources`` - one broken feed does not make
    the others look broken.
    """

    source_type = SourceType.RSS

    def __init__(
        self,
        *,
        source_id: str,
        name: str,
        feed_url: str,
        access_basis: str,
        fetcher: SafeFetcher | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.id = source_id
        self.name = name
        self.access_basis = access_basis
        self._feed_url = feed_url
        self._settings = settings or get_settings()
        self._fetcher = fetcher or SafeFetcher(self._settings)

    def search(self, plan: SearchPlan) -> SourceResult:
        try:
            response = self._fetcher.fetch(self._feed_url)
        except FetchBlockedError as error:
            return self._failed(error)

        try:
            root = DefusedET.fromstring(response.text)
        except Exception as error:  # malformed or hostile XML
            return self._failed(f"could not parse feed: {error}")

        entries = root.findall(".//item") or root.findall(".//atom:entry", _NAMESPACES)
        candidates: list[OpportunityCandidate] = []
        for entry in entries[:MAX_ITEMS_PER_FEED]:
            title = _text(entry, "title", "atom:title")
            if not title:
                continue
            link = _text(entry, "link", "atom:link") or self._atom_href(entry)
            body = _text(entry, "content:encoded", "description", "atom:summary", "atom:content")
            if not self._relevant(title, body, plan):
                continue
            candidates.append(
                OpportunityCandidate(
                    source_name=self.name,
                    source_type=self.source_type,
                    url=link or None,
                    title=title,
                    # Feed HTML is untrusted and goes through the guard before
                    # it reaches any prompt.
                    raw_text=f"{title}\n\n{body}",
                    published_at=_parse_when(
                        _text(entry, "pubDate", "atom:updated", "atom:published", "dc:date")
                    ),
                )
            )
        return self._succeeded(candidates, queries_run=1)

    @staticmethod
    def _atom_href(entry: object) -> str:
        link = entry.find("atom:link", _NAMESPACES) if hasattr(entry, "find") else None
        return str(link.get("href", "")) if link is not None else ""

    def _relevant(self, title: str, body: str, plan: SearchPlan) -> bool:
        """Cheap keyword gate, so a busy feed does not flood extraction.

        Feeds carry everything the publisher posts, most of which is not an
        opportunity. Filtering here rather than after extraction is what keeps
        the model bill proportionate to the results.
        """
        if not plan.queries:
            return True
        haystack = f"{title} {body}".lower()
        terms = {
            word
            for query in plan.queries
            for word in query.text.lower().split()
            if len(word) > 4
        }
        return not terms or any(term in haystack for term in terms)

    def fetch_details(self, reference: str) -> str | None:
        try:
            return self._fetcher.fetch(reference).text
        except FetchBlockedError:
            return None

    def health_check(self) -> SourceHealth:
        try:
            self._fetcher.fetch(self._feed_url)
        except FetchBlockedError as error:
            return SourceHealth(source_id=self.id, ok=False, detail=str(error))
        return SourceHealth(source_id=self.id, ok=True)
