"""Search-API and public-API sources.

:class:`SearchAPIOpportunitySource` is the widest net the product casts and the
one that most needs discipline. A search provider returns web pages, not
opportunities. Turning one into the other is: fetch the page through
:class:`~app.security.web.SafeFetcher` (SSRF-checked, robots-respecting,
size-capped), strip it to text, screen it for injection, and hand it to
extraction against a closed schema. Every one of those steps can reject, and
rejection is the normal case rather than an error.

The snippet a search provider returns is deliberately *not* treated as
sufficient. A snippet is a fragment chosen to look relevant, and building an
opportunity record from one would mean publishing an organisation, a deadline
and possibly a compensation figure on the strength of forty words of ranked
marketing text.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.config import Settings, get_settings
from app.domain.enums import SourceType
from app.domain.opportunity import OpportunityCandidate
from app.search.base import SearchProvider
from app.security.web import FetchBlockedError, SafeFetcher
from app.sources.base import OpportunitySource, SearchPlan, SourceHealth, SourceResult

logger = logging.getLogger(__name__)

#: Hosts we will not fetch even if a search engine ranks them. These are sites
#: whose terms prohibit automated access, or where the useful content sits
#: behind a login. Listing them is cheaper and more honest than discovering it
#: at request time.
BLOCKED_HOSTS = frozenset(
    {
        "linkedin.com", "www.linkedin.com", "de.linkedin.com",
        "facebook.com", "www.facebook.com",
        "instagram.com", "www.instagram.com",
        "x.com", "twitter.com",
        "indeed.com", "de.indeed.com",
        "glassdoor.com", "www.glassdoor.de",
        "xing.com", "www.xing.com",
    }
)

MAX_PAGES_PER_RUN = 12
MAX_TEXT_CHARS = 24_000

_SCRIPT_STYLE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"[ \t\r\f\v]+")


def html_to_text(html: str) -> str:
    """Strip HTML to readable text.

    A deliberately small implementation rather than a parsing dependency: this
    runs on untrusted input, and the only thing needed downstream is the words.
    Scripts and styles are removed first, so their contents cannot survive tag
    stripping and end up in a prompt.
    """
    text = _SCRIPT_STYLE.sub(" ", html)
    text = re.sub(r"<br\s*/?>|</(p|div|li|h[1-6]|tr)>", "\n", text, flags=re.IGNORECASE)
    text = _TAG.sub(" ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    text = _WHITESPACE.sub(" ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()[:MAX_TEXT_CHARS]


def _host_of(url: str) -> str:
    from urllib.parse import urlsplit

    return (urlsplit(url).hostname or "").lower()


class SearchAPIOpportunitySource(OpportunitySource):
    """Discovers pages via a search provider, then reads them properly."""

    id = "search_api"
    name = "Web search"
    source_type = SourceType.SEARCH_API
    access_basis = (
        "Public pages discovered through a licensed search API and fetched with "
        "robots.txt respected, rate limiting and size caps. No login, no paywall "
        "circumvention, no site whose terms prohibit automated access."
    )

    def __init__(
        self,
        provider: SearchProvider,
        *,
        fetcher: SafeFetcher | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._provider = provider
        self._settings = settings or get_settings()
        self._fetcher = fetcher or SafeFetcher(self._settings)
        self.name = f"Web search ({provider.name})"

    def search(self, plan: SearchPlan) -> SourceResult:
        if not self._provider.available:
            return self._failed("No web search provider is configured.")

        seen: set[str] = set()
        candidates: list[OpportunityCandidate] = []
        queries = plan.queries[: self._settings.search_max_queries_per_run]
        fetched = 0

        for query in queries:
            response = self._provider.search(
                query.text,
                max_results=self._settings.search_max_results_per_query,
                region=query.region,
            )
            if not response.ok:
                continue
            for hit in response.hits:
                if fetched >= MAX_PAGES_PER_RUN:
                    break
                host = _host_of(hit.url)
                if not host or host in BLOCKED_HOSTS or hit.url in seen:
                    continue
                if any(host.endswith("." + blocked) for blocked in BLOCKED_HOSTS):
                    continue
                seen.add(hit.url)

                try:
                    page = self._fetcher.fetch(hit.url)
                except FetchBlockedError as error:
                    logger.info("skipped %s: %s", host, error.reason)
                    continue
                fetched += 1

                text = html_to_text(page.text)
                if len(text) < 200:
                    # A page with almost no text is a redirect, a JS shell or a
                    # consent wall. There is nothing to extract from it, and
                    # guessing from the snippet is exactly what we do not do.
                    continue
                candidates.append(
                    OpportunityCandidate(
                        source_name=host,
                        source_type=self.source_type,
                        url=page.final_url,
                        title=hit.title or text[:120],
                        raw_text=text,
                        published_at=hit.published_at,
                        structured={"search_snippet": hit.snippet[:500]},
                    )
                )
            if fetched >= MAX_PAGES_PER_RUN:
                break

        return self._succeeded(candidates, queries_run=len(queries))

    def fetch_details(self, reference: str) -> str | None:
        try:
            return html_to_text(self._fetcher.fetch(reference).text)
        except FetchBlockedError:
            return None

    def health_check(self) -> SourceHealth:
        ok = self._provider.available and self._provider.health_check()
        return SourceHealth(
            source_id=self.id,
            ok=ok,
            detail="" if ok else "search provider unavailable",
        )


class PublicAPIOpportunitySource(OpportunitySource):
    """A documented public JSON API.

    Kept as a thin, configurable adapter rather than one class per API: the
    shape is always "GET a JSON endpoint, walk a list, map a few fields", and a
    field map expressed as data is easier to review than five near-identical
    classes. Registering one is filling in :class:`FieldMap`.
    """

    source_type = SourceType.PUBLIC_API

    def __init__(
        self,
        *,
        source_id: str,
        name: str,
        endpoint: str,
        access_basis: str,
        items_path: str,
        title_field: str,
        url_field: str,
        text_fields: tuple[str, ...],
        query_param: str | None = None,
        fetcher: SafeFetcher | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.id = source_id
        self.name = name
        self.access_basis = access_basis
        self._endpoint = endpoint
        self._items_path = items_path
        self._title_field = title_field
        self._url_field = url_field
        self._text_fields = text_fields
        self._query_param = query_param
        self._settings = settings or get_settings()
        self._fetcher = fetcher or SafeFetcher(self._settings)

    def _walk(self, payload: object) -> list[dict[str, Any]]:
        node: Any = payload
        for part in filter(None, self._items_path.split(".")):
            if isinstance(node, dict):
                node = node.get(part)
            else:
                return []
        return [item for item in (node or []) if isinstance(item, dict)]

    def search(self, plan: SearchPlan) -> SourceResult:
        import json
        from urllib.parse import urlencode

        url = self._endpoint
        if self._query_param and plan.queries:
            joiner = "&" if "?" in url else "?"
            url = f"{url}{joiner}{urlencode({self._query_param: plan.queries[0].text})}"

        try:
            response = self._fetcher.fetch(url)
            payload = json.loads(response.text)
        except (FetchBlockedError, json.JSONDecodeError, ValueError) as error:
            return self._failed(error)

        candidates: list[OpportunityCandidate] = []
        for item in self._walk(payload)[:MAX_PAGES_PER_RUN * 4]:
            title = str(item.get(self._title_field, "")).strip()
            if not title:
                continue
            body = "\n".join(
                str(item.get(field, "")) for field in self._text_fields if item.get(field)
            )
            candidates.append(
                OpportunityCandidate(
                    source_name=self.name,
                    source_type=self.source_type,
                    url=item.get(self._url_field) or None,
                    title=title,
                    raw_text=f"{title}\n\n{body}",
                )
            )
        return self._succeeded(candidates, queries_run=1)

    def health_check(self) -> SourceHealth:
        try:
            self._fetcher.fetch(self._endpoint)
        except FetchBlockedError as error:
            return SourceHealth(source_id=self.id, ok=False, detail=str(error))
        return SourceHealth(source_id=self.id, ok=True)
