"""Concrete search providers: Tavily, Brave and Serper.

Three implementations rather than one, because a single implementation behind
an interface proves nothing about whether the interface is right. Each is about
forty lines - the whole point of the abstraction is that a vendor swap is a
configuration change, not a refactor.

None of them is the default. ``MYM_SEARCH_PROVIDER=none`` ships as the default
so the product runs with no accounts and no spend, and the curated + demo
sources carry the experience until someone chooses to enable live search.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from app.search.base import SearchHit, SearchProvider, SearchResponse

logger = logging.getLogger(__name__)


def _parse_date(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    for parse in (
        datetime.fromisoformat,
        lambda s: datetime.strptime(s, "%Y-%m-%d"),
        lambda s: datetime.strptime(s, "%d/%m/%Y"),
    ):
        try:
            value = parse(text)
        except (ValueError, TypeError):
            continue
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return None


class _HttpSearchProvider(SearchProvider):
    """Shared plumbing: one client, uniform error handling, no raising."""

    endpoint: str = ""

    def __init__(self, api_key: str, *, timeout_seconds: float = 20.0) -> None:
        self._key = api_key
        self._timeout = timeout_seconds

    def _post(
        self, payload: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any] | None:
        try:
            response = httpx.post(
                self.endpoint, json=payload, headers=headers, timeout=self._timeout
            )
            response.raise_for_status()
            return dict(response.json())
        except httpx.HTTPError as error:
            logger.warning("%s search failed: %s", self.name, error)
            return None

    def _get(
        self, params: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any] | None:
        try:
            response = httpx.get(
                self.endpoint, params=params, headers=headers, timeout=self._timeout
            )
            response.raise_for_status()
            return dict(response.json())
        except httpx.HTTPError as error:
            logger.warning("%s search failed: %s", self.name, error)
            return None

    def _failure(self) -> SearchResponse:
        return SearchResponse(
            hits=[], ok=False, error=f"{self.name} search is unavailable.", provider=self.name
        )


class TavilySearchProvider(_HttpSearchProvider):
    name = "tavily"
    endpoint = "https://api.tavily.com/search"

    def search(
        self, query: str, *, max_results: int = 10, region: str | None = None
    ) -> SearchResponse:
        body = self._post(
            {
                "api_key": self._key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                # We want documents, not the provider's generated answer.
                "include_answer": False,
                "include_raw_content": False,
            },
            headers={"Content-Type": "application/json"},
        )
        if body is None:
            return self._failure()
        hits = [
            SearchHit(
                url=str(item.get("url", "")),
                title=str(item.get("title", "")),
                snippet=str(item.get("content", "")),
                published_at=_parse_date(item.get("published_date")),
                provider_score=item.get("score"),
            )
            for item in body.get("results", [])
            if item.get("url")
        ]
        return SearchResponse(hits=hits, provider=self.name)

    def health_check(self) -> bool:
        return self.search("test", max_results=1).ok


class BraveSearchProvider(_HttpSearchProvider):
    name = "brave"
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def search(
        self, query: str, *, max_results: int = 10, region: str | None = None
    ) -> SearchResponse:
        params: dict[str, object] = {"q": query, "count": min(max_results, 20)}
        if region:
            params["country"] = region.upper()
        body = self._get(
            params,
            headers={"Accept": "application/json", "X-Subscription-Token": self._key},
        )
        if body is None:
            return self._failure()
        results = (body.get("web") or {}).get("results", [])
        hits = [
            SearchHit(
                url=str(item.get("url", "")),
                title=str(item.get("title", "")),
                snippet=str(item.get("description", "")),
                published_at=_parse_date(item.get("page_age") or item.get("age")),
            )
            for item in results
            if item.get("url")
        ]
        return SearchResponse(hits=hits, provider=self.name)

    def health_check(self) -> bool:
        return self.search("test", max_results=1).ok


class SerperSearchProvider(_HttpSearchProvider):
    name = "serper"
    endpoint = "https://google.serper.dev/search"

    def search(
        self, query: str, *, max_results: int = 10, region: str | None = None
    ) -> SearchResponse:
        payload: dict[str, object] = {"q": query, "num": min(max_results, 20)}
        if region:
            payload["gl"] = region.lower()
        body = self._post(
            payload, headers={"X-API-KEY": self._key, "Content-Type": "application/json"}
        )
        if body is None:
            return self._failure()
        hits = [
            SearchHit(
                url=str(item.get("link", "")),
                title=str(item.get("title", "")),
                snippet=str(item.get("snippet", "")),
                published_at=_parse_date(item.get("date")),
            )
            for item in body.get("organic", [])
            if item.get("link")
        ]
        return SearchResponse(hits=hits, provider=self.name)

    def health_check(self) -> bool:
        return self.search("test", max_results=1).ok


class StubSearchProvider(SearchProvider):
    """Returns canned hits. Used by tests and the offline demo."""

    name = "stub"

    def __init__(self, hits: list[SearchHit] | None = None, *, ok: bool = True) -> None:
        self._hits = hits or []
        self._ok = ok
        self.queries: list[str] = []

    def search(
        self, query: str, *, max_results: int = 10, region: str | None = None
    ) -> SearchResponse:
        self.queries.append(query)
        if not self._ok:
            return SearchResponse(hits=[], ok=False, error="stub failure", provider=self.name)
        return SearchResponse(hits=self._hits[:max_results], provider=self.name)

    def health_check(self) -> bool:
        return self._ok
