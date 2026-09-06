"""The learning loop: explicit preference updates, never opaque training.

The product uses outcome data to improve ranking. It does so by counting the
reasons a user gave for dismissing opportunities and nudging a small number of
named weights - and by nothing else.

This is a deliberate refusal of the more sophisticated option. A model trained
on someone's income decisions would be more powerful and completely
unaccountable: the user could not see why their results changed, could not
disagree with it, and could not reset it. Worse, it would learn from
correlations that should not drive recommendations - a user who dismisses two
onsite roles because of one week of childcare would find the system quietly
deciding they do not want onsite work.

So: bounded adjustments, one per dismiss reason, visible in the API, resettable
in one call, and inert until there are at least three signals.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Application, FeedbackEvent, SavedOpportunity
from app.domain.enums import ApplicationStatus, DismissReason
from app.services.matching import PreferenceAdjustment

logger = logging.getLogger(__name__)

#: Below this many dismissals with reasons, no adjustment is applied at all.
MIN_SIGNALS = 3


def dismiss_reason_counts(session: Session, user_id: str) -> dict[DismissReason, int]:
    rows = session.execute(
        select(SavedOpportunity.dismiss_reason, func.count(SavedOpportunity.id))
        .where(
            SavedOpportunity.user_id == user_id,
            SavedOpportunity.dismiss_reason.isnot(None),
        )
        .group_by(SavedOpportunity.dismiss_reason)
    ).all()
    counts: dict[DismissReason, int] = {}
    for reason, count in rows:
        try:
            counts[DismissReason(reason)] = int(count)
        except ValueError:
            continue
    return counts


def load_preferences(session: Session, user_id: str) -> PreferenceAdjustment:
    """Current weight adjustment for this user. Neutral until enough signal."""
    counts = dismiss_reason_counts(session, user_id)
    if sum(counts.values()) < MIN_SIGNALS:
        return PreferenceAdjustment()
    return PreferenceAdjustment.from_dismissals(counts)


def explain_preferences(session: Session, user_id: str) -> dict[str, object]:
    """What the system has learned, in plain language, for the settings page.

    The user can read this, disagree with it, and clear it. That is the whole
    justification for having a learning loop at all in a product that makes
    consequential recommendations.
    """
    counts = dismiss_reason_counts(session, user_id)
    adjustment = load_preferences(session, user_id)
    total = sum(counts.values())

    # One sentence per active adjustment, phrased so the user can disagree with
    # it. "Pay now counts for more" is a claim they can check against their own
    # behaviour; a weight delta is not.
    wording: list[tuple[float, str]] = [
        (adjustment.income_goal_fit, "paying too little, so pay now counts for more"),
        (adjustment.availability_fit, "taking too much time, so time commitment counts for more"),
        (adjustment.skill_fit, "being a poor skill fit, so skill fit counts for more"),
        (adjustment.location_fit, "their location, so location counts for more"),
        (adjustment.eligibility_fit, "administrative burden, so eligibility counts for more"),
        (adjustment.deadline_fit, "their deadlines, so timing counts for more"),
    ]
    statements = [
        f"You dismiss opportunities for {phrase}." for value, phrase in wording if value
    ]

    return {
        "signals": total,
        "minimum_signals": MIN_SIGNALS,
        "active": adjustment.is_active,
        "reasons": {reason.value: count for reason, count in counts.items()},
        "adjustments": {
            "skill_fit": adjustment.skill_fit,
            "availability_fit": adjustment.availability_fit,
            "income_goal_fit": adjustment.income_goal_fit,
            "location_fit": adjustment.location_fit,
            "eligibility_fit": adjustment.eligibility_fit,
            "deadline_fit": adjustment.deadline_fit,
        },
        "statements": statements
        or ["Not enough feedback yet to adjust your ranking. Nothing has been changed."],
    }


def reset_preferences(session: Session, user_id: str) -> int:
    """Clear the dismiss reasons that drive the adjustment.

    The saved/dismissed rows themselves are kept - the user still does not want
    to see those opportunities again - but the *reasons* are cleared, which is
    what the adjustment reads.
    """
    rows = (
        session.execute(
            select(SavedOpportunity).where(
                SavedOpportunity.user_id == user_id,
                SavedOpportunity.dismiss_reason.isnot(None),
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        row.dismiss_reason = None
    return len(rows)


def outcome_summary(session: Session, user_id: str) -> dict[str, object]:
    """Won/lost counts per category. The seed of a real ranking signal.

    Not yet fed into scoring. With single-digit outcomes per user, category
    win-rate is noise, and pretending otherwise would be the exact failure this
    module avoids elsewhere. It is collected now so that it *can* be used when
    there is enough of it - see docs/ROADMAP.md.
    """
    rows = session.execute(
        select(Application.status, func.count(Application.id))
        .where(Application.user_id == user_id)
        .group_by(Application.status)
    ).all()
    by_status = {str(status): int(count) for status, count in rows}
    won = by_status.get(ApplicationStatus.WON.value, 0)
    decided = won + by_status.get(ApplicationStatus.LOST.value, 0)
    return {
        "by_status": by_status,
        "won": won,
        "decided": decided,
        # None, not 0.0, when nothing has been decided: no data is not a 0% win rate.
        "win_rate": round(won / decided, 4) if decided else None,
        "note": (
            "Outcome data is collected but does not yet influence ranking. "
            "Per-user outcome counts are too small to be a reliable signal."
        ),
    }


def feedback_summary(session: Session) -> dict[str, dict[str, int]]:
    """Aggregated validation responses. The startup's actual evidence."""
    rows = session.execute(
        select(FeedbackEvent.question, FeedbackEvent.answer, func.count(FeedbackEvent.id))
        .group_by(FeedbackEvent.question, FeedbackEvent.answer)
    ).all()
    summary: dict[str, dict[str, int]] = {}
    for question, answer, count in rows:
        summary.setdefault(str(question), {})[str(answer)] = int(count)
    return summary
