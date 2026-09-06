"""Search provider selection."""

from __future__ import annotations

from app.config import SearchProviderName, Settings, get_settings
from app.search.base import NullSearchProvider, SearchProvider
from app.search.providers import (
    BraveSearchProvider,
    SerperSearchProvider,
    TavilySearchProvider,
)


def build_search_provider(settings: Settings | None = None) -> SearchProvider:
    """Return the configured provider, or the null one.

    Never raises on a missing key: running without live search is a supported
    configuration, reported through the capability endpoint.
    """
    settings = settings or get_settings()
    if not settings.live_search_available:
        return NullSearchProvider()

    key = settings.search_key.get_secret_value()
    timeout = settings.search_timeout_seconds
    match settings.search_provider:
        case SearchProviderName.TAVILY:
            return TavilySearchProvider(key, timeout_seconds=timeout)
        case SearchProviderName.BRAVE:
            return BraveSearchProvider(key, timeout_seconds=timeout)
        case SearchProviderName.SERPER:
            return SerperSearchProvider(key, timeout_seconds=timeout)
        case _:
            return NullSearchProvider()
