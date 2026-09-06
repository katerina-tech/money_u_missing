"""Safe outbound HTTP: SSRF prevention, robots, rate limiting, caching, caps.

Every fetch of third-party content goes through :class:`SafeFetcher`. There is
no other outbound HTTP client for retrieved content anywhere in the codebase,
which is what makes these guarantees checkable rather than aspirational.

What it guarantees:

* **No SSRF.** URLs are validated by scheme and, critically, *every resolved
  address* is checked against private, loopback, link-local and reserved
  ranges - before connecting. A DNS name that resolves to 169.254.169.254 is
  rejected the same as the literal address, and redirects are followed
  manually so each hop is re-validated rather than trusted.
* **Robots is respected** when configured, cached per host.
* **Rate limited per host**, so a discovery run cannot hammer one server.
* **Bounded**: timeout, response size ceiling enforced while streaming, and a
  content-type allowlist - so a 4 GB video behind a listing URL cannot be
  pulled into memory.
* **Cached**, so a re-run within the TTL costs the origin nothing.

What it does NOT do, on purpose: no login, no cookie jar, no CAPTCHA solving,
no paywall circumvention, no private APIs. See docs/DATA_PROVENANCE.md.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.config import Settings, get_settings
from app.logging_config import Event, log_event

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = frozenset({"http", "https"})

#: Only textual formats. A listing is a document; anything else is either not
#: what we were promised or not something we should be downloading.
ALLOWED_CONTENT_TYPES = (
    "text/html",
    "text/plain",
    "application/xhtml+xml",
    "application/xml",
    "text/xml",
    "application/rss+xml",
    "application/atom+xml",
    "application/json",
)

MAX_REDIRECTS = 4


class FetchBlockedError(RuntimeError):
    """The request was refused by our own policy, before or during the fetch."""

    def __init__(self, message: str, *, reason: str, url: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason
        self.url = url


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content_type: str
    text: str
    from_cache: bool = False
    fetched_at: float = field(default_factory=time.time)


# ------------------------------------------------------------------ URL safety


def _is_public_address(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_url(raw: str, *, resolve: bool = True) -> str:
    """Return the URL if it is safe to fetch, else raise :class:`FetchBlockedError`.

    ``resolve=True`` performs DNS resolution and checks every returned address.
    That is the step that stops the classic SSRF: a hostname the attacker
    controls, pointing at a metadata endpoint or an internal service. Checking
    only the literal host would pass it.
    """
    try:
        parts = urlsplit(raw.strip())
    except ValueError as error:
        raise FetchBlockedError("Malformed URL.", reason="malformed", url=raw) from error

    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise FetchBlockedError(
            f"Only http and https are allowed, got '{parts.scheme}'.",
            reason="scheme",
            url=raw,
        )
    host = parts.hostname
    if not host:
        raise FetchBlockedError("URL has no host.", reason="no_host", url=raw)
    if host.lower() in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        raise FetchBlockedError("Refusing to fetch a loopback host.", reason="loopback", url=raw)
    if parts.port is not None and parts.port not in {80, 443, 8080, 8443}:
        raise FetchBlockedError(
            f"Refusing to fetch a non-web port ({parts.port}).", reason="port", url=raw
        )

    if not resolve:
        return raw

    try:
        infos = socket.getaddrinfo(host, parts.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as error:
        raise FetchBlockedError("Host could not be resolved.", reason="dns", url=raw) from error

    # sockaddr is (host, port) for IPv4 and (host, port, flowinfo, scopeid)
    # for IPv6; the host element is a string in both cases.
    addresses = {str(info[4][0]) for info in infos}
    if not addresses:
        raise FetchBlockedError("Host resolved to no addresses.", reason="dns", url=raw)
    for address in addresses:
        if not _is_public_address(address):
            # Log the reason but not the address: it is attacker-controlled and
            # there is no need to echo internal topology into logs.
            log_event(
                logger,
                Event.FETCH_BLOCKED,
                "URL resolved to a non-public address",
                level=logging.WARNING,
                reason="private_address",
                host=host,
            )
            raise FetchBlockedError(
                "That host resolves to a non-public address.",
                reason="private_address",
                url=raw,
            )
    return raw


# ------------------------------------------------------------- rate limiting


class HostThrottle:
    """A minimum interval between requests to the same host.

    Politeness, not a security control: it keeps one discovery run from looking
    like a denial-of-service attempt to a small organisation's web server.
    """

    def __init__(self, min_interval_seconds: float) -> None:
        self._min = min_interval_seconds
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> None:
        with self._lock:
            last = self._last.get(host, 0.0)
            delay = self._min - (time.monotonic() - last)
            self._last[host] = time.monotonic() + max(0.0, delay)
        if delay > 0:
            time.sleep(delay)


# -------------------------------------------------------------------- robots


_MISSING: RobotFileParser | None = RobotFileParser()


class RobotsCache:
    """Per-host robots.txt, fetched once and cached.

    A host whose robots.txt cannot be fetched is treated as *allowing* the
    request. That is the convention the standard describes; failing closed on a
    transient 500 would silently blank the product's discovery results.
    """

    def __init__(self, user_agent: str, timeout: float) -> None:
        self._agent = user_agent
        self._timeout = timeout
        self._cache: dict[str, RobotFileParser | None] = {}
        self._lock = threading.Lock()

    def allows(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        with self._lock:
            cached = self._cache.get(origin, _MISSING)
        if cached is _MISSING:
            parser = self._load(origin)
            with self._lock:
                self._cache[origin] = parser
        else:
            parser = cached
        if parser is None:
            return True
        return bool(parser.can_fetch(self._agent, url))

    def _load(self, origin: str) -> RobotFileParser | None:
        try:
            response = httpx.get(
                urljoin(origin, "/robots.txt"),
                timeout=self._timeout,
                headers={"User-Agent": self._agent},
                follow_redirects=True,
            )
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser


# -------------------------------------------------------------------- caching


@dataclass
class _CacheEntry:
    result: FetchResult
    expires_at: float


class ResponseCache:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._entries: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, url: str) -> FetchResult | None:
        with self._lock:
            entry = self._entries.get(url)
            if entry is None:
                return None
            if entry.expires_at < time.time():
                del self._entries[url]
                return None
        return FetchResult(**{**entry.result.__dict__, "from_cache": True})

    def put(self, url: str, result: FetchResult) -> None:
        with self._lock:
            self._entries[url] = _CacheEntry(result, time.time() + self._ttl)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


# ------------------------------------------------------------------- fetcher


class SafeFetcher:
    """The only way third-party content enters this system."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._throttle = HostThrottle(self._settings.fetch_min_interval_seconds)
        self._robots = RobotsCache(
            self._settings.fetch_user_agent, self._settings.fetch_timeout_seconds
        )
        self._cache = ResponseCache(self._settings.fetch_cache_ttl_seconds)

    def fetch(self, url: str, *, use_cache: bool = True) -> FetchResult:
        """Fetch one document, or raise :class:`FetchBlockedError`."""
        if use_cache:
            cached = self._cache.get(url)
            if cached is not None:
                return cached

        current = validate_url(url)
        if self._settings.respect_robots_txt and not self._robots.allows(current):
            log_event(
                logger,
                Event.FETCH_BLOCKED,
                "robots.txt disallows this path",
                level=logging.INFO,
                reason="robots",
                host=urlsplit(current).hostname,
            )
            raise FetchBlockedError(
                "This site's robots.txt asks us not to fetch that page.",
                reason="robots",
                url=url,
            )

        headers = {
            "User-Agent": self._settings.fetch_user_agent,
            "Accept": ", ".join(ALLOWED_CONTENT_TYPES) + ";q=0.9,*/*;q=0.1",
            "Accept-Language": "de,en;q=0.8",
        }

        # follow_redirects is off so each hop is re-validated. A redirect to
        # http://169.254.169.254/ is the whole point of the attack, and httpx
        # would follow it happily.
        with httpx.Client(
            timeout=self._settings.fetch_timeout_seconds,
            follow_redirects=False,
            headers=headers,
        ) as client:
            for hop in range(MAX_REDIRECTS + 1):
                self._throttle.wait(urlsplit(current).hostname or "")
                try:
                    with client.stream("GET", current) as response:
                        if response.is_redirect:
                            location = response.headers.get("location")
                            if not location:
                                raise FetchBlockedError(
                                    "Redirect without a destination.",
                                    reason="bad_redirect",
                                    url=current,
                                )
                            if hop == MAX_REDIRECTS:
                                raise FetchBlockedError(
                                    "Too many redirects.", reason="redirect_loop", url=url
                                )
                            current = validate_url(urljoin(current, location))
                            continue

                        return self._read(response, original=url, final=current)
                except httpx.HTTPError as error:
                    raise FetchBlockedError(
                        "That page could not be retrieved.", reason="http_error", url=current
                    ) from error

        raise FetchBlockedError("Too many redirects.", reason="redirect_loop", url=url)

    def _read(self, response: httpx.Response, *, original: str, final: str) -> FetchResult:
        if response.status_code >= 400:
            raise FetchBlockedError(
                f"The source returned HTTP {response.status_code}.",
                reason=f"http_{response.status_code}",
                url=final,
            )

        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type and not content_type.startswith(ALLOWED_CONTENT_TYPES):
            raise FetchBlockedError(
                f"Unsupported content type '{content_type}'.",
                reason="content_type",
                url=final,
            )

        declared = response.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > self._settings.fetch_max_bytes:
            raise FetchBlockedError(
                "That document is larger than we will download.",
                reason="too_large",
                url=final,
            )

        # Enforce the ceiling while streaming. Checking only Content-Length
        # would be trivially bypassed by omitting the header.
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > self._settings.fetch_max_bytes:
                raise FetchBlockedError(
                    "That document is larger than we will download.",
                    reason="too_large",
                    url=final,
                )
            chunks.append(chunk)

        text = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
        result = FetchResult(
            url=original,
            final_url=final,
            status_code=response.status_code,
            content_type=content_type,
            text=text,
        )
        self._cache.put(original, result)
        return result

    def clear_cache(self) -> None:
        self._cache.clear()
