"""Evidence wrappers: how the system carries "and here is how we know".

An ordinary model would store ``compensation_min: int | None``. That loses the
one thing this product needs to keep: whether the number came from an
organisation's own page, from a model reading a search snippet, or from nowhere
at all. :class:`Evidenced` keeps the value and its provenance together so a UI
component cannot render a figure without also being handed its confidence, and
so :func:`app.services.money_map.summarise` can exclude weak evidence from
arithmetic without re-deriving where each number came from.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.domain.enums import Confidence, SourceType, TrustLabel

T = TypeVar("T")


def utcnow() -> datetime:
    return datetime.now(UTC)


class SourceRef(BaseModel):
    """A citable origin. Every externally-sourced claim carries one."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Human-readable publisher, e.g. 'Bundesagentur fuer Arbeit'.")
    url: HttpUrl | None = None
    source_type: SourceType
    retrieved_at: datetime = Field(default_factory=utcnow)
    #: When a human or an automated re-check last confirmed the page still says
    #: this. Distinct from ``retrieved_at``: we may hold a year-old fetch that
    #: was re-verified yesterday, or a fresh fetch nobody has reviewed.
    last_verified_at: datetime | None = None

    def age_days(self, *, now: datetime | None = None) -> int:
        reference = self.last_verified_at or self.retrieved_at
        return max(0, ((now or utcnow()) - reference).days)


class Evidenced(BaseModel, Generic[T]):
    """A value plus how we know it.

    ``value is None`` with ``confidence=UNKNOWN`` is the honest default and is
    materially different from a value of zero or false. Nothing in the codebase
    is permitted to collapse the two - see the ``unknown_is_not_false`` tests.
    """

    model_config = ConfigDict(extra="forbid")

    value: T | None = None
    confidence: Confidence = Confidence.UNKNOWN
    source: SourceRef | None = None
    note: str | None = Field(
        default=None,
        description="Why this is unknown or uncertain, shown verbatim in 'What we do not know'.",
    )

    @property
    def known(self) -> bool:
        return self.value is not None and self.confidence is not Confidence.UNKNOWN

    @property
    def trustworthy(self) -> bool:
        """Strong enough to drive money arithmetic or a legal statement."""
        return self.known and self.confidence in {Confidence.VERIFIED, Confidence.SOURCE_BACKED}

    @classmethod
    def unknown(cls, note: str | None = None) -> Evidenced[T]:
        return cls(value=None, confidence=Confidence.UNKNOWN, source=None, note=note)

    @classmethod
    def stated(cls, value: T, source: SourceRef, confidence: Confidence) -> Evidenced[T]:
        return cls(value=value, confidence=confidence, source=source, note=None)


def trust_label(
    *,
    confidence: Confidence,
    is_demo: bool,
    source: SourceRef | None = None,
    max_age_days: int | None = None,
    now: datetime | None = None,
) -> TrustLabel:
    """Collapse confidence, demo status and age into the badge the UI shows.

    Order matters. Demo wins over everything, because a jury seeing a plausible
    card must never have to wonder whether it is a live offer. Staleness wins
    over confidence, because a verified fact about last year's threshold is
    worse than an admission of ignorance.
    """
    if is_demo:
        return TrustLabel.DEMO
    if source is not None and max_age_days is not None and source.age_days(now=now) > max_age_days:
        return TrustLabel.OUTDATED
    return {
        Confidence.VERIFIED: TrustLabel.VERIFIED,
        Confidence.SOURCE_BACKED: TrustLabel.SOURCE_BACKED,
        Confidence.EXTRACTED: TrustLabel.UNVERIFIED,
        Confidence.UNVERIFIED: TrustLabel.UNVERIFIED,
        Confidence.UNKNOWN: TrustLabel.UNKNOWN,
    }[confidence]


def freshness_score(source: SourceRef | None, *, half_life_days: int = 45,
                    now: datetime | None = None) -> float:
    """Recency as a 0-1 factor, halving every ``half_life_days``.

    Exponential rather than a cliff: a 46-day-old listing is not categorically
    worse than a 44-day-old one, but a 200-day-old one genuinely is. No source
    at all scores 0.0 - it cannot be shown to be fresh.
    """
    if source is None:
        return 0.0
    age = source.age_days(now=now)
    decay: float = 0.5 ** (age / half_life_days)
    return round(decay, 4)


def is_stale(source: SourceRef | None, max_age: timedelta, *, now: datetime | None = None) -> bool:
    if source is None:
        return True
    return (now or utcnow()) - (source.last_verified_at or source.retrieved_at) > max_age
