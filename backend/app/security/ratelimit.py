"""Token-bucket rate limiting, and the response headers every request carries.

In-process and therefore per-instance. That is stated plainly rather than
implied: behind two replicas the effective limit is doubled. It is the correct
amount of machinery for a single-container MVP, and the interface is small
enough that swapping in Redis is a constructor change - see docs/ROADMAP.md.

Two buckets, because two costs. Ordinary reads are cheap and get a generous
per-minute allowance; a discovery run spends search-API credits and model
tokens, so it gets its own hourly bucket. Sharing one limit between them would
either throttle browsing or leave the expensive path unprotected.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from fastapi import Request, Response

from app.config import Settings


@dataclass
class Decision:
    allowed: bool
    remaining: int
    retry_after_seconds: int
    limit: int


class TokenBucket:
    """Classic token bucket: a steady refill rate with a burst allowance."""

    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self._capacity = capacity
        self._rate = refill_per_second
        self._state: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def take(self, key: str, cost: float = 1.0) -> Decision:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._state.get(key, (float(self._capacity), now))
            tokens = min(self._capacity, tokens + (now - last) * self._rate)
            if tokens >= cost:
                self._state[key] = (tokens - cost, now)
                return Decision(True, int(tokens - cost), 0, self._capacity)
            self._state[key] = (tokens, now)
            deficit = cost - tokens
            retry_after = int(deficit / self._rate) + 1 if self._rate > 0 else 60
        return Decision(False, 0, retry_after, self._capacity)

    def reset(self) -> None:
        with self._lock:
            self._state.clear()


class RateLimiter:
    """The two buckets the application uses."""

    def __init__(self, settings: Settings) -> None:
        self.general = TokenBucket(
            capacity=settings.rate_limit_per_minute + settings.rate_limit_burst,
            refill_per_second=settings.rate_limit_per_minute / 60.0,
        )
        self.discovery = TokenBucket(
            capacity=settings.discovery_rate_limit_per_hour,
            refill_per_second=settings.discovery_rate_limit_per_hour / 3600.0,
        )

    def reset(self) -> None:
        self.general.reset()
        self.discovery.reset()


def client_key(request: Request, user_id: str | None = None) -> str:
    """Bucket key: the authenticated user when there is one, else the peer address.

    Preferring the user id means one person on a shared office IP is not
    throttled by their colleagues, and a client cannot escape their limit by
    rotating addresses while logged in. ``X-Forwarded-For`` is only consulted
    when a proxy is actually in front of us - trusting it unconditionally would
    let any caller forge their own bucket.
    """
    if user_id:
        return f"user:{user_id}"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and request.headers.get("x-forwarded-proto"):
        return f"ip:{forwarded.split(',')[0].strip()}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


def apply_headers(response: Response, decision: Decision) -> None:
    response.headers["X-RateLimit-Limit"] = str(decision.limit)
    response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
    if not decision.allowed:
        response.headers["Retry-After"] = str(decision.retry_after_seconds)


#: Applied to every response. A JSON API served to a separate frontend origin
#: needs a restrictive CSP of its own: nothing should ever be framing these
#: responses or loading them as a document.
SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
    "Content-Security-Policy": (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    ),
    # Only meaningful over HTTPS; harmless otherwise, and the deployment target
    # terminates TLS.
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}
