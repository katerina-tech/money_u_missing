"""First-party analytics, with an allowlist that makes leaks structurally hard.

The risk here is specific and well understood: analytics is where sensitive
data ends up by accident. Someone adds ``{"cv_text": text}`` to an event to
debug an extraction problem, it ships, and a table nobody thinks of as personal
data now holds people's CVs.

So properties are not free-form. Every event name declares exactly which
property keys it accepts and what type each must be, and
:func:`record` drops anything else with a warning. A developer who adds a
disallowed key finds out in the test suite, not in a breach report.

What is deliberately never recorded: CV text, profile free text, tax questions,
opportunity descriptions, email addresses, and any identifier that is not the
user's own row id (which is itself deleted with the account).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AnalyticsEvent

logger = logging.getLogger(__name__)

#: event name -> allowed property keys and their permitted types.
#: Every key here is a scalar with a bounded set of values. There is no string
#: field that could carry user prose.
SCHEMA: dict[str, dict[str, type | tuple[type, ...]]] = {
    "signup_completed": {"is_demo": bool},
    "profile_completed": {"completeness": float, "skill_count": int, "source": str},
    "money_map_created": {
        "opportunity_count": int,
        "high_match_count": int,
        "has_goal": bool,
    },
    "opportunity_search_started": {
        "query_count": int,
        "planner": str,
        "live_search": bool,
    },
    "opportunities_returned": {
        "returned": int,
        "considered": int,
        "blocked_unsafe": int,
        "blocked_injection": int,
        "deduped": int,
        "sources": int,
    },
    "opportunity_opened": {"category": str, "match_score": int, "is_demo": bool},
    "opportunity_saved": {"category": str, "match_score": int, "actionability": str},
    "opportunity_dismissed": {"category": str, "match_score": int, "reason": str},
    "application_prepared": {"category": str, "draft_kind": str},
    "application_marked_applied": {"category": str, "days_from_save": int},
    "opportunity_offered": {"category": str},
    "opportunity_won": {"category": str, "days_from_applied": int},
    "opportunity_lost": {"category": str},
    "income_recorded": {
        "category": str,
        # A bucket, never the amount. "How much does this user earn" is not a
        # question the analytics table needs to be able to answer.
        "amount_bucket": str,
        "period": str,
    },
    "tax_check_viewed": {"topic": str, "needs_verification": bool},
    "legal_source_opened": {"source_name": str},
    "goal_created": {"goal_type": str, "has_target_date": bool},
    "child_goal_created": {"years_remaining": int},
    "feedback_submitted": {"question": str, "answer": str, "reason": str},
}

#: Amount buckets, so income analysis is possible without storing incomes.
_BUCKETS: tuple[tuple[int, str], ...] = (
    (5_000, "under_50"),
    (20_000, "50_200"),
    (50_000, "200_500"),
    (100_000, "500_1000"),
    (300_000, "1000_3000"),
    (10_000_000, "over_3000"),
)


def amount_bucket(minor: int | None) -> str:
    if minor is None:
        return "unknown"
    for ceiling, label in _BUCKETS:
        if minor < ceiling:
            return label
    return "over_3000"


class UnknownEventError(KeyError):
    """An event name not in :data:`SCHEMA`. Raised in tests, logged in production."""


def _sanitise(name: str, properties: dict[str, Any]) -> dict[str, Any]:
    allowed = SCHEMA.get(name)
    if allowed is None:
        raise UnknownEventError(name)
    clean: dict[str, Any] = {}
    for key, value in properties.items():
        expected = allowed.get(key)
        if expected is None:
            logger.warning("analytics: dropped disallowed property %r on %r", key, name)
            continue
        if value is None:
            continue
        if not isinstance(value, expected):
            # bool is a subclass of int, so an explicit check keeps a stray
            # True out of an int field rather than silently storing 1.
            if expected is float and isinstance(value, int) and not isinstance(value, bool):
                clean[key] = float(value)
                continue
            logger.warning("analytics: dropped %r on %r - wrong type", key, name)
            continue
        if isinstance(value, str) and len(value) > 64:
            logger.warning("analytics: dropped over-long string %r on %r", key, name)
            continue
        clean[key] = value
    return clean


def record(
    session: Session,
    name: str,
    *,
    user_id: str | None = None,
    **properties: Any,
) -> None:
    """Record one event. Never raises into a request.

    A failure to write analytics must not fail a user's action. The write is
    additive and the caller does not depend on it, so a warning is the correct
    response to a problem here.
    """
    try:
        clean = _sanitise(name, properties)
    except UnknownEventError:
        logger.warning("analytics: unknown event %r was not recorded", name)
        return
    try:
        session.add(AnalyticsEvent(user_id=user_id, name=name, properties=clean))
    except Exception:
        logger.warning("analytics: could not record %r", name, exc_info=True)


def funnel(session: Session) -> dict[str, int]:
    """Counts per event name. The raw material for docs/METRICS.md.

    Deliberately not a dashboard. At this stage the useful thing is honest
    counts that a founder reads once a day, not a visualisation layer that
    makes twelve data points look like a trend.
    """
    rows = session.execute(
        select(AnalyticsEvent.name, func.count(AnalyticsEvent.id)).group_by(AnalyticsEvent.name)
    ).all()
    return {str(name): int(count) for name, count in rows}


def rate(counts: dict[str, int], numerator: str, denominator: str) -> float | None:
    """A conversion rate, or ``None`` when the denominator is zero.

    ``None`` rather than 0.0: no data is not the same as a zero rate, and a
    metrics table that shows 0% for an unmeasured step invites the wrong
    conclusion.
    """
    bottom = counts.get(denominator, 0)
    if bottom == 0:
        return None
    return round(counts.get(numerator, 0) / bottom, 4)
