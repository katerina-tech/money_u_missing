"""Actionability: "is this worth acting on now?"

Separate from the match score on purpose, and deliberately *not* called
"expected net income". A euro figure would imply a financial calculation the
product has not performed and in most cases cannot - the majority of listings
publish no compensation at all, and where they do, the gross/net treatment is
usually unstated. Presenting a modelled income figure as a number would be the
single most dishonest thing this product could do.

So the output is a band with a stated reason. The user reads two independent
signals: *this fits me* (match) and *this is worth my time this week*
(actionability). A perfectly-fitting grant that closed yesterday scores high on
the first and bottom on the second, and one merged number would hide that.
"""

from __future__ import annotations

from datetime import date, datetime

from app.domain.enums import (
    ActionabilityBand,
    Confidence,
    EmploymentType,
    IncomeStreamCategory,
    RemoteType,
    Tristate,
)
from app.domain.evidence import freshness_score, utcnow
from app.domain.matching import Actionability, ActionabilityFactor, MatchScore
from app.domain.opportunity import Opportunity
from app.domain.profile import UserProfile

#: Rough application effort by category, in minutes. Not a promise - a relative
#: ordering used only to compare opportunities against each other. Grants and
#: fellowships genuinely take an order of magnitude longer than joining an
#: expert network, and a ranking that ignores that sends people to the wrong
#: place with their two free hours this week.
EFFORT_MINUTES: dict[IncomeStreamCategory, int] = {
    IncomeStreamCategory.EXPERT_CALL: 15,
    IncomeStreamCategory.PAID_RESEARCH: 15,
    IncomeStreamCategory.USER_RESEARCH: 15,
    IncomeStreamCategory.MENTORING: 25,
    IncomeStreamCategory.TUTORING: 25,
    IncomeStreamCategory.CONSULTING: 45,
    IncomeStreamCategory.FREELANCE_PROJECT: 45,
    IncomeStreamCategory.TEACHING: 60,
    IncomeStreamCategory.WORKSHOP: 60,
    IncomeStreamCategory.SPEAKING: 45,
    IncomeStreamCategory.ADVISORY: 60,
    IncomeStreamCategory.PART_TIME_JOB: 90,
    IncomeStreamCategory.PAID_PROGRAM: 180,
    IncomeStreamCategory.FELLOWSHIP: 300,
    IncomeStreamCategory.FOUNDER_PROGRAM: 300,
    IncomeStreamCategory.COMPETITION: 240,
    IncomeStreamCategory.GRANT: 600,
}
DEFAULT_EFFORT_MINUTES = 60

#: Administrative setup a category typically implies for someone in Germany.
#: Higher means more friction before the first euro arrives.
ADMIN_BURDEN: dict[IncomeStreamCategory, float] = {
    IncomeStreamCategory.PART_TIME_JOB: 0.1,
    IncomeStreamCategory.MINIJOB: 0.15,
    IncomeStreamCategory.EXPERT_CALL: 0.35,
    IncomeStreamCategory.PAID_RESEARCH: 0.3,
    IncomeStreamCategory.TEACHING: 0.4,
    IncomeStreamCategory.CONSULTING: 0.6,
    IncomeStreamCategory.FREELANCE_PROJECT: 0.6,
    IncomeStreamCategory.WORKSHOP: 0.5,
    IncomeStreamCategory.GRANT: 0.7,
    IncomeStreamCategory.FELLOWSHIP: 0.6,
    IncomeStreamCategory.FOUNDER_PROGRAM: 0.7,
}
DEFAULT_ADMIN_BURDEN = 0.45


def _band(score: int, blockers: list[str]) -> ActionabilityBand:
    if blockers:
        return ActionabilityBand.LOW_PRIORITY
    if score >= 75:
        return ActionabilityBand.HIGHLY_ACTIONABLE
    if score >= 55:
        return ActionabilityBand.ACTIONABLE
    if score >= 35:
        return ActionabilityBand.REVIEW_FIRST
    return ActionabilityBand.LOW_PRIORITY


def assess(
    profile: UserProfile,
    opportunity: Opportunity,
    match: MatchScore,
    *,
    now: datetime | None = None,
) -> Actionability:
    """Compute the actionability band. Deterministic, like matching."""
    now = now or utcnow()
    today = now.date()
    factors: list[ActionabilityFactor] = []
    blockers: list[str] = []

    # --- fit carries in, because acting on a poor fit is rarely worth it
    factors.append(
        ActionabilityFactor(
            name="match",
            score=match.total_score / 100,
            weight=0.28,
            detail=f"Match score {match.total_score}%.",
        )
    )
    if match.hard_failures:
        blockers.append(
            "You do not meet a stated hard requirement: "
            + match.hard_failures[0].requirement
        )

    # --- deadline
    deadline_score, deadline_detail = _deadline(opportunity, today)
    if opportunity.deadline is not None and opportunity.deadline < today:
        blockers.append(f"The deadline passed on {opportunity.deadline.isoformat()}.")
    factors.append(
        ActionabilityFactor(
            name="deadline", score=deadline_score, weight=0.14, detail=deadline_detail
        )
    )

    # --- application effort
    effort = EFFORT_MINUTES.get(opportunity.category, DEFAULT_EFFORT_MINUTES)
    effort_score = max(0.1, min(1.0, 1.0 - (effort - 15) / 600))
    factors.append(
        ActionabilityFactor(
            name="application_effort",
            score=round(effort_score, 4),
            weight=0.14,
            detail=f"Applying to this category typically takes around {effort} minutes.",
        )
    )

    # --- ongoing time commitment against availability
    commitment_score, commitment_detail = _commitment(profile, opportunity)
    factors.append(
        ActionabilityFactor(
            name="time_commitment",
            score=commitment_score,
            weight=0.12,
            detail=commitment_detail,
        )
    )

    # --- how much we actually know
    completeness = _completeness(opportunity)
    factors.append(
        ActionabilityFactor(
            name="data_completeness",
            score=completeness,
            weight=0.10,
            detail=f"{int(completeness * 100)}% of the fields that matter are published.",
        )
    )

    # --- compensation evidence
    if opportunity.compensation_verified:
        comp_score, comp_detail = 1.0, "Compensation is stated by the source."
    elif opportunity.compensation.known:
        comp_score, comp_detail = 0.6, "A figure appears in the listing but is unverified."
    else:
        comp_score, comp_detail = 0.35, "Compensation is not published."
    factors.append(
        ActionabilityFactor(
            name="compensation_evidence", score=comp_score, weight=0.10, detail=comp_detail
        )
    )

    # --- German administrative friction
    admin_score, admin_detail = _admin(profile, opportunity)
    factors.append(
        ActionabilityFactor(
            name="admin_complexity", score=admin_score, weight=0.08, detail=admin_detail
        )
    )

    # --- freshness
    fresh = freshness_score(opportunity.source, now=now)
    factors.append(
        ActionabilityFactor(
            name="freshness",
            score=fresh,
            weight=0.04,
            detail=f"Last seen {opportunity.source.age_days(now=now)} day(s) ago.",
        )
    )

    if not opportunity.is_active:
        blockers.append("This opportunity is marked as no longer active.")

    total_weight = sum(f.weight for f in factors) or 1.0
    raw = sum(f.weighted for f in factors) / total_weight
    numeric = max(0, min(100, round(raw * 100)))
    band = _band(numeric, blockers)

    return Actionability(
        opportunity_id=opportunity.id,
        score=numeric,
        band=band,
        factors=factors,
        headline_reason=_headline(band, factors, blockers),
        blockers=blockers,
    )


def _deadline(opportunity: Opportunity, today: date) -> tuple[float, str]:
    if opportunity.deadline is None:
        # No deadline is genuinely good for actionability - nothing is lost by
        # acting next week - but it also means we cannot confirm it is still
        # open, so it does not score full marks.
        return 0.7, "No deadline published; this may be ongoing, or may have closed."
    days = (opportunity.deadline - today).days
    if days < 0:
        return 0.0, f"The deadline passed {abs(days)} day(s) ago."
    if days <= 7:
        return 1.0, f"Closes in {days} day(s) - acting now matters."
    if days <= 30:
        return 0.9, f"Closes in {days} days."
    return 0.6, f"Closes in {days} days - no urgency yet."


def _commitment(profile: UserProfile, opportunity: Opportunity) -> tuple[float, str]:
    hours = opportunity.estimated_hours_min or opportunity.estimated_hours_max
    available = profile.time.hours_per_week
    if hours is None:
        return 0.6, "The ongoing time commitment is not published."
    if available is None:
        return 0.6, f"About {hours:g}h/week; your availability is not in your profile."
    if hours <= available:
        return 1.0, f"About {hours:g}h/week fits your {available:g}h."
    return (
        max(0.0, 1.0 - (hours - available) / max(available, 1.0)),
        f"About {hours:g}h/week exceeds your {available:g}h.",
    )


def _completeness(opportunity: Opportunity) -> float:
    """Share of the decision-relevant fields the source actually published."""
    present = [
        opportunity.compensation.known,
        opportunity.estimated_hours_min is not None or opportunity.estimated_hours_max is not None,
        opportunity.deadline is not None,
        bool(opportunity.eligibility_structured or opportunity.eligibility_text),
        opportunity.remote_type is not RemoteType.UNKNOWN,
        bool(opportunity.required_skills or opportunity.preferred_skills),
        opportunity.employment_type is not EmploymentType.UNKNOWN,
        opportunity.evidence_confidence
        in {Confidence.VERIFIED, Confidence.SOURCE_BACKED},
    ]
    return round(sum(present) / len(present), 4)


def _admin(profile: UserProfile, opportunity: Opportunity) -> tuple[float, str]:
    """Lower administrative friction scores higher.

    The one place the profile changes this: a user who already has a Gewerbe or
    a freelance tax registration has already paid most of the setup cost, so
    self-employed work is materially more actionable for them. That is read
    only from what they explicitly told us - UNKNOWN gets no adjustment either
    way.
    """
    burden = ADMIN_BURDEN.get(opportunity.category, DEFAULT_ADMIN_BURDEN)
    detail = f"Typical administrative setup for this category is {_burden_word(burden)}."

    already_set_up = (
        profile.admin.has_gewerbe is Tristate.YES
        or profile.admin.has_freelance_tax_registration is Tristate.YES
    )
    if already_set_up and burden >= 0.5:
        burden *= 0.5
        detail += " You have said you are already registered, which removes most of it."
    return round(1.0 - burden, 4), detail


def _burden_word(burden: float) -> str:
    if burden <= 0.2:
        return "minimal"
    if burden <= 0.45:
        return "moderate"
    if burden <= 0.65:
        return "significant"
    return "substantial"


def _headline(
    band: ActionabilityBand, factors: list[ActionabilityFactor], blockers: list[str]
) -> str:
    if blockers:
        return blockers[0]
    strongest = max(factors, key=lambda f: f.weighted)
    weakest = min((f for f in factors if f.weight >= 0.1), key=lambda f: f.score)
    if band in {ActionabilityBand.HIGHLY_ACTIONABLE, ActionabilityBand.ACTIONABLE}:
        return strongest.detail
    return weakest.detail
