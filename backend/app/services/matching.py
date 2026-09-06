"""The deterministic matching engine.

This module is the reason the product can defend its numbers. Every score here
is computed in plain Python from a profile and an opportunity record. No
language model is invoked, imported or reachable from this file. The model's
only role, later and elsewhere, is to phrase a finished :class:`MatchScore` -
which means a score cannot be argued up by an opportunity page that flatters
itself, cannot drift between two runs on identical inputs, and can be explained
line by line to a user who disagrees with it.

Three rules govern every component:

**Unknown is not false.** If the source did not publish a requirement, or the
profile does not state the matching attribute, the component returns a neutral
score and records an :class:`Uncertainty`. It never scores zero. Scoring zero
would rank an opportunity below one that is genuinely a bad fit, purely for the
sin of having a terse listing - and would quietly hide the best opportunities,
because the best-paying work is frequently the least verbosely advertised.

**Only a demonstrated conflict disqualifies.** A :class:`HardFailure` requires a
HARD requirement *and* a populated profile field *and* an actual conflict
between them. Two out of three produces an uncertainty.

**Every component explains itself.** ``detail`` is a factual sentence built from
the same values that produced the number, so "why 91?" is answerable without
re-running anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.domain.enums import (
    LANGUAGE_ORDER,
    CompensationPeriod,
    Confidence,
    DismissReason,
    IncomePreference,
    LanguageLevel,
    RemoteType,
    RequirementStrength,
    SkillLevel,
)
from app.domain.evidence import freshness_score, utcnow
from app.domain.matching import HardFailure, MatchScore, ScoreComponent, Uncertainty
from app.domain.opportunity import Opportunity
from app.domain.profile import UserProfile, normalise_skill_name
from app.services.skills_graph import related_keys

WEIGHTS_VERSION = "v1"


@dataclass(frozen=True)
class Weights:
    """Component weights. Sum is normalised, so these are relative importances.

    Chosen from what actually determines whether a professional pursues an
    opportunity: can I do it, do I have the time, and is it worth the money.
    Skill fit dominates; freshness and evidence are tie-breakers, not drivers.
    """

    skill_fit: float = 0.24
    experience_fit: float = 0.10
    language_fit: float = 0.10
    location_fit: float = 0.10
    availability_fit: float = 0.12
    eligibility_fit: float = 0.10
    income_goal_fit: float = 0.12
    deadline_fit: float = 0.05
    freshness: float = 0.04
    evidence_confidence: float = 0.03

    def total(self) -> float:
        return (
            self.skill_fit
            + self.experience_fit
            + self.language_fit
            + self.location_fit
            + self.availability_fit
            + self.eligibility_fit
            + self.income_goal_fit
            + self.deadline_fit
            + self.freshness
            + self.evidence_confidence
        )


DEFAULT_WEIGHTS = Weights()

#: How much a component is worth when nothing is known about it. Deliberately
#: above the midpoint: the common case for an under-described listing is that
#: it is fine, and a 0.5 default would systematically bury terse listings.
NEUTRAL = 0.6

_LEVEL_STRENGTH: dict[SkillLevel, float] = {
    SkillLevel.EXPERT: 1.0,
    SkillLevel.ADVANCED: 0.9,
    SkillLevel.INTERMEDIATE: 0.7,
    SkillLevel.BEGINNER: 0.45,
    SkillLevel.UNKNOWN: 0.6,
}


# ============================================================== components


def score_skill_fit(profile: UserProfile, opportunity: Opportunity) -> ScoreComponent:
    """Coverage of the required skills, plus credit for preferred ones.

    A skill the user confirmed counts fully. A skill that was *inferred* from
    their CV and never confirmed counts at a discount, because the product
    promised not to claim qualifications the user has not stood behind - and a
    score built on unconfirmed inferences would quietly break that promise.

    Related skills (from a curated graph, never from a model) count at a further
    discount: "PySpark" is real evidence for a "Spark" requirement, but weaker
    evidence than "Spark".
    """
    required = [normalise_skill_name(s) for s in opportunity.required_skills]
    preferred = [normalise_skill_name(s) for s in opportunity.preferred_skills]
    if not required and not preferred:
        return ScoreComponent(
            name="skill_fit",
            score=NEUTRAL,
            weight=0.0,  # weight applied by caller; placeholder replaced below
            detail="The source does not list required skills.",
            was_unknown=True,
        )

    owned: dict[str, float] = {}
    for skill in profile.professional.skills:
        strength = _LEVEL_STRENGTH[skill.level]
        if skill.is_inferred and not skill.confirmed:
            strength *= 0.6
        owned[skill.key] = max(owned.get(skill.key, 0.0), strength)

    expanded: dict[str, float] = dict(owned)
    for key, strength in owned.items():
        for neighbour in related_keys(key):
            expanded.setdefault(neighbour, strength * 0.5)

    def coverage(keys: list[str]) -> tuple[float, int, int]:
        """Returns (mean strength, direct matches, partial matches)."""
        if not keys:
            return 0.0, 0, 0
        hits = [expanded.get(key, 0.0) for key in keys]
        direct = sum(1 for key in keys if key in owned)
        partial = sum(1 for key, h in zip(keys, hits, strict=True) if h > 0 and key not in owned)
        return sum(hits) / len(keys), direct, partial

    required_score, required_direct, required_partial = coverage(required)
    preferred_score, preferred_direct, preferred_partial = coverage(preferred)

    if required:
        # Preferred skills can lift a score but never rescue a failed core fit,
        # hence the capped bonus rather than a straight average.
        score = min(1.0, required_score + 0.15 * preferred_score)
        detail = f"{required_direct} of {len(required)} required skills matched directly"
        if required_partial:
            # Stated explicitly, because "2 of 2 matched" next to a score of 73%
            # reads as a bug rather than as partial credit - and an unexplained
            # number is the one thing this engine is built to avoid.
            detail += f", {required_partial} through a related skill"
        if preferred:
            detail += f"; {preferred_direct + preferred_partial} of {len(preferred)} preferred"
        detail += "."
    else:
        score = preferred_score
        matched = preferred_direct + preferred_partial
        detail = f"{matched} of {len(preferred)} preferred skills matched."

    unconfirmed = [s for s in profile.professional.skills if s.is_inferred and not s.confirmed]
    if unconfirmed and score < 1.0:
        detail += (
            f" {len(unconfirmed)} inferred skill(s) counted at reduced weight "
            "until you confirm them."
        )

    return ScoreComponent(
        name="skill_fit", score=round(score, 4), weight=0.0, detail=detail, was_unknown=False
    )


def score_experience_fit(profile: UserProfile, opportunity: Opportunity) -> ScoreComponent:
    """Whether stated experience sits in the published band."""
    years = profile.professional.years_experience
    low, high = opportunity.experience_min_years, opportunity.experience_max_years

    if low is None and high is None:
        return ScoreComponent(
            name="experience_fit",
            score=NEUTRAL,
            weight=0.0,
            detail="The source does not state an experience requirement.",
            was_unknown=True,
        )
    if years is None:
        return ScoreComponent(
            name="experience_fit",
            score=NEUTRAL,
            weight=0.0,
            detail="Your profile does not state years of experience.",
            was_unknown=True,
        )

    if low is not None and years < low:
        # Graduated rather than binary: one year short of a five-year ask is a
        # conversation; four years short is not.
        shortfall = (low - years) / max(low, 1.0)
        score = max(0.0, 1.0 - shortfall * 1.5)
        detail = f"{years:g} years against a stated minimum of {low:g}."
    elif high is not None and years > high:
        # Over-qualification is a mild signal, not a disqualification. Plenty of
        # senior people take a well-paid short engagement below their level.
        score = 0.85
        detail = f"{years:g} years against a stated maximum of {high:g}."
    else:
        score = 1.0
        detail = f"{years:g} years meets the stated requirement."

    return ScoreComponent(
        name="experience_fit", score=round(score, 4), weight=0.0, detail=detail
    )


def score_language_fit(profile: UserProfile, opportunity: Opportunity) -> ScoreComponent:
    """Whether stated language levels reach the published minimum."""
    requirements = opportunity.required_languages
    if not requirements:
        return ScoreComponent(
            name="language_fit",
            score=NEUTRAL,
            weight=0.0,
            detail="The source does not state a language requirement.",
            was_unknown=True,
        )

    scores: list[float] = []
    notes: list[str] = []
    unknown = False
    for requirement in requirements:
        have = profile.professional.language_level(requirement.code)
        need = requirement.minimum
        if need is LanguageLevel.UNKNOWN:
            scores.append(NEUTRAL)
            unknown = True
            notes.append(f"{requirement.code.upper()} required at an unstated level")
            continue
        if have is LanguageLevel.UNKNOWN:
            scores.append(NEUTRAL)
            unknown = True
            notes.append(f"your {requirement.code.upper()} level is not in your profile")
            continue
        gap = LANGUAGE_ORDER[have] - LANGUAGE_ORDER[need]
        scores.append(1.0 if gap >= 0 else max(0.0, 1.0 + gap * 0.35))
        notes.append(f"{requirement.code.upper()} {have.value} against {need.value}")

    return ScoreComponent(
        name="language_fit",
        score=round(sum(scores) / len(scores), 4),
        weight=0.0,
        detail="; ".join(notes) + ".",
        was_unknown=unknown,
    )


def score_location_fit(profile: UserProfile, opportunity: Opportunity) -> ScoreComponent:
    """Remote arrangement and geography against the user's stated preference."""
    remote = opportunity.remote_type
    preference = profile.time.remote_preference

    if remote is RemoteType.REMOTE:
        return ScoreComponent(
            name="location_fit", score=1.0, weight=0.0, detail="Remote."
        )
    if remote is RemoteType.UNKNOWN:
        return ScoreComponent(
            name="location_fit",
            score=NEUTRAL,
            weight=0.0,
            detail="The source does not state whether this is remote or onsite.",
            was_unknown=True,
        )

    same_country = (
        opportunity.country is None
        or profile.general.country is None
        or opportunity.country.upper() == profile.general.country.upper()
    )
    same_city = bool(
        opportunity.city
        and profile.general.city
        and opportunity.city.strip().lower() == profile.general.city.strip().lower()
    )

    if remote is RemoteType.HYBRID:
        base = 0.9 if same_city else (0.6 if same_country else 0.25)
        detail = f"Hybrid in {opportunity.city or opportunity.country or 'an unstated location'}."
    else:
        base = 1.0 if same_city else (0.45 if same_country else 0.1)
        detail = f"Onsite in {opportunity.city or opportunity.country or 'an unstated location'}."

    # Reached only for HYBRID and ONSITE, so a stated preference for remote
    # always applies here.
    if preference is RemoteType.REMOTE:
        base *= 0.6
        detail += " You prefer remote work."

    return ScoreComponent(
        name="location_fit", score=round(min(1.0, base), 4), weight=0.0, detail=detail
    )


def score_availability_fit(profile: UserProfile, opportunity: Opportunity) -> ScoreComponent:
    """Whether the published time commitment fits the hours the user has."""
    available = profile.time.hours_per_week
    low, high = opportunity.estimated_hours_min, opportunity.estimated_hours_max

    if low is None and high is None:
        return ScoreComponent(
            name="availability_fit",
            score=NEUTRAL,
            weight=0.0,
            detail="The source does not state a time commitment.",
            was_unknown=True,
        )
    if available is None:
        return ScoreComponent(
            name="availability_fit",
            score=NEUTRAL,
            weight=0.0,
            detail="Your profile does not state weekly availability.",
            was_unknown=True,
        )

    needed = low if low is not None else high
    assert needed is not None
    if needed <= available:
        headroom = (available - needed) / max(available, 1.0)
        # A tiny commitment against large availability is fine but not better
        # than a well-matched one, so the bonus is small and capped.
        score = min(1.0, 0.9 + 0.1 * headroom)
        detail = f"Needs about {needed:g}h/week; you have {available:g}h."
    else:
        overrun = (needed - available) / max(available, 1.0)
        score = max(0.0, 1.0 - overrun)
        detail = f"Needs about {needed:g}h/week, more than the {available:g}h you have."

    return ScoreComponent(
        name="availability_fit", score=round(score, 4), weight=0.0, detail=detail
    )


def score_eligibility_fit(
    profile: UserProfile, opportunity: Opportunity
) -> tuple[ScoreComponent, list[HardFailure], list[Uncertainty]]:
    """Structured requirements. The only component that can disqualify.

    Everything about this function is arranged so that silence never counts
    against the user. A HARD requirement we cannot evaluate becomes an
    uncertainty on the card; only a requirement we can evaluate *and* that
    conflicts produces a failure.
    """
    requirements = opportunity.eligibility_structured
    failures: list[HardFailure] = []
    uncertainties: list[Uncertainty] = []

    if not requirements:
        component = ScoreComponent(
            name="eligibility_fit",
            score=NEUTRAL,
            weight=0.0,
            detail="No structured eligibility conditions were published.",
            was_unknown=True,
        )
        if opportunity.eligibility_text:
            uncertainties.append(
                Uncertainty(
                    topic="Eligibility",
                    explanation=(
                        "The source describes eligibility in prose that we have not "
                        "broken into checkable conditions."
                    ),
                    how_to_resolve="Read the eligibility section on the source page.",
                )
            )
        return component, failures, uncertainties

    satisfied = 0
    evaluable = 0
    for requirement in requirements:
        outcome = _evaluate_requirement(profile, requirement.label)
        if outcome is None:
            if requirement.strength is RequirementStrength.HARD:
                uncertainties.append(
                    Uncertainty(
                        topic=requirement.label,
                        explanation=(
                            f"'{requirement.label}' is stated as a hard requirement, but we "
                            "cannot tell from your profile whether you meet it."
                        ),
                        how_to_resolve="Confirm this against the source before applying.",
                    )
                )
            continue
        evaluable += 1
        if outcome:
            satisfied += 1
        elif requirement.strength is RequirementStrength.HARD:
            failures.append(
                HardFailure(
                    requirement=requirement.label,
                    profile_value=None,
                    explanation=(
                        f"The source states '{requirement.label}' as mandatory, and your "
                        "profile indicates otherwise."
                    ),
                )
            )

    if evaluable == 0:
        return (
            ScoreComponent(
                name="eligibility_fit",
                score=NEUTRAL,
                weight=0.0,
                detail=(
                    f"{len(requirements)} condition(s) published; "
                    "none checkable from your profile."
                ),
                was_unknown=True,
            ),
            failures,
            uncertainties,
        )

    return (
        ScoreComponent(
            name="eligibility_fit",
            score=round(satisfied / evaluable, 4),
            weight=0.0,
            detail=f"{satisfied} of {evaluable} checkable condition(s) met.",
        ),
        failures,
        uncertainties,
    )


def _evaluate_requirement(profile: UserProfile, label: str) -> bool | None:
    """Evaluate a free-text requirement, or return ``None`` for "cannot tell".

    Deliberately conservative and small. It recognises a handful of conditions
    that appear verbatim in German listings and that the profile actually
    answers; everything else returns ``None``. A cleverer matcher here would
    produce confident wrong answers about people's eligibility, which is the
    one place in this product where being wrong has a real cost.
    """
    lowered = label.lower()
    if "eu" in lowered and ("work" in lowered or "arbeit" in lowered or "permit" in lowered):
        return None  # Right to work is never inferred; we do not ask for it.
    if "gewerbe" in lowered:
        from app.domain.enums import Tristate

        if profile.admin.has_gewerbe is Tristate.YES:
            return True
        if profile.admin.has_gewerbe is Tristate.NO:
            return False
        return None
    if "freelance" in lowered and ("register" in lowered or "steuer" in lowered):
        from app.domain.enums import Tristate

        if profile.admin.has_freelance_tax_registration is Tristate.YES:
            return True
        if profile.admin.has_freelance_tax_registration is Tristate.NO:
            return False
        return None
    if "germany" in lowered or "deutschland" in lowered or "germany-based" in lowered:
        if profile.general.country:
            return profile.general.country.upper() == "DE"
        return None
    return None


def score_income_goal_fit(profile: UserProfile, opportunity: Opportunity) -> ScoreComponent:
    """How far the published compensation goes towards the user's monthly goal.

    Unpublished compensation scores neutral, never zero. Most grants,
    fellowships and expert networks do not publish a figure up front, and
    ranking them last would remove precisely the categories the product exists
    to surface.
    """
    goal = profile.income.desired_additional_monthly_minor
    compensation = opportunity.compensation

    if not compensation.known:
        return ScoreComponent(
            name="income_goal_fit",
            score=NEUTRAL,
            weight=0.0,
            detail="Compensation is not published, so this cannot be measured against your goal.",
            was_unknown=True,
        )
    if goal is None:
        return ScoreComponent(
            name="income_goal_fit",
            score=NEUTRAL,
            weight=0.0,
            detail="You have not set a monthly income goal.",
            was_unknown=True,
        )

    minimum = profile.income.minimum_worthwhile_minor
    amount = compensation.conservative_minor
    assert amount is not None

    monthly = compensation.monthly_equivalent_minor(profile.time.hours_per_week)
    if monthly is None:
        # A one-off amount cannot be compared to a monthly goal. Measure it
        # against the goal as a single month's worth, and say so.
        ratio = amount / goal if goal else 0.0
        score = min(1.0, 0.4 + 0.6 * min(1.0, ratio))
        detail = (
            f"A one-off or irregular amount worth about {amount / 100:,.0f} "
            f"{compensation.currency}, which is not directly comparable to a monthly goal."
        )
    else:
        ratio = monthly / goal if goal else 0.0
        score = min(1.0, ratio)
        detail = (
            f"About {monthly / 100:,.0f} {compensation.currency}/month against your "
            f"{goal / 100:,.0f} goal."
        )

    if minimum is not None and amount < minimum:
        score *= 0.4
        detail += " Below the minimum you said is worth your time."

    if profile.income.preference is IncomePreference.RECURRING:
        if compensation.period is CompensationPeriod.RECURRING:
            score = min(1.0, score * 1.1)
        elif compensation.period is CompensationPeriod.ONE_TIME:
            score *= 0.85
            detail += " You prefer recurring income."
    elif (
        profile.income.preference is IncomePreference.ONE_TIME
        and compensation.period is CompensationPeriod.ONE_TIME
    ):
        score = min(1.0, score * 1.1)

    return ScoreComponent(
        name="income_goal_fit", score=round(min(1.0, score), 4), weight=0.0, detail=detail
    )


def score_deadline_fit(opportunity: Opportunity, *, today: date | None = None) -> ScoreComponent:
    """Whether there is enough time left to prepare a decent application."""
    today = today or date.today()
    if opportunity.deadline is None:
        return ScoreComponent(
            name="deadline_fit",
            score=NEUTRAL,
            weight=0.0,
            detail="No deadline is published; this may be ongoing.",
            was_unknown=True,
        )
    days = (opportunity.deadline - today).days
    if days < 0:
        return ScoreComponent(
            name="deadline_fit",
            score=0.0,
            weight=0.0,
            detail=f"The published deadline passed {abs(days)} day(s) ago.",
        )
    if days <= 3:
        score, note = 0.35, "very little time to prepare"
    elif days <= 14:
        score, note = 0.85, "enough time to prepare"
    elif days <= 90:
        score, note = 1.0, "comfortable time to prepare"
    else:
        score, note = 0.8, "a long way off"
    return ScoreComponent(
        name="deadline_fit",
        score=score,
        weight=0.0,
        detail=f"{days} day(s) until the deadline - {note}.",
    )


def score_freshness(opportunity: Opportunity, *, now: datetime | None = None) -> ScoreComponent:
    value = freshness_score(opportunity.source, now=now)
    age = opportunity.source.age_days(now=now)
    return ScoreComponent(
        name="freshness",
        score=value,
        weight=0.0,
        detail=f"Retrieved or last verified {age} day(s) ago.",
    )


def score_evidence_confidence(opportunity: Opportunity) -> ScoreComponent:
    mapping = {
        Confidence.VERIFIED: 1.0,
        Confidence.SOURCE_BACKED: 0.85,
        Confidence.EXTRACTED: 0.6,
        Confidence.UNVERIFIED: 0.4,
        Confidence.UNKNOWN: 0.3,
    }
    value = mapping[opportunity.evidence_confidence]
    if opportunity.is_demo:
        # A demo record evidences nothing about the world, and saying "evidence
        # is unknown" reads as a defect rather than as the point.
        detail = "This is demo data, so it evidences nothing about a real opportunity."
    else:
        detail = f"Evidence for this record is {opportunity.evidence_confidence.value.lower()}."
    return ScoreComponent(
        name="evidence_confidence",
        score=value,
        weight=0.0,
        detail=detail,
        was_unknown=opportunity.evidence_confidence is Confidence.UNKNOWN,
    )


# ================================================================ preferences


@dataclass(frozen=True)
class PreferenceAdjustment:
    """Explicit, inspectable weight changes learned from dismissals.

    Not a trained model. Each dismiss reason maps to one named weight nudge,
    the adjustment is bounded, and the user can see and reset it. Opaque
    self-training on someone's income choices would be both a product risk and
    an ethical one; this is legible enough to argue with.
    """

    skill_fit: float = 0.0
    availability_fit: float = 0.0
    income_goal_fit: float = 0.0
    location_fit: float = 0.0
    eligibility_fit: float = 0.0
    deadline_fit: float = 0.0

    @classmethod
    def from_dismissals(
        cls, reasons: dict[DismissReason, int], *, max_shift: float = 0.08
    ) -> PreferenceAdjustment:
        total = sum(reasons.values())
        if total < 3:
            # Below three signals this is noise, not a preference.
            return cls()

        def share(reason: DismissReason) -> float:
            return min(max_shift, max_shift * (reasons.get(reason, 0) / total) * 3)

        return cls(
            income_goal_fit=share(DismissReason.TOO_LITTLE_MONEY),
            availability_fit=share(DismissReason.TOO_MUCH_TIME),
            skill_fit=share(DismissReason.NOT_QUALIFIED),
            location_fit=share(DismissReason.LOCATION),
            eligibility_fit=share(DismissReason.ADMIN_BURDEN),
            deadline_fit=share(DismissReason.DEADLINE),
        )

    def apply(self, weights: Weights) -> Weights:
        return Weights(
            skill_fit=weights.skill_fit + self.skill_fit,
            experience_fit=weights.experience_fit,
            language_fit=weights.language_fit,
            location_fit=weights.location_fit + self.location_fit,
            availability_fit=weights.availability_fit + self.availability_fit,
            eligibility_fit=weights.eligibility_fit + self.eligibility_fit,
            income_goal_fit=weights.income_goal_fit + self.income_goal_fit,
            deadline_fit=weights.deadline_fit + self.deadline_fit,
            freshness=weights.freshness,
            evidence_confidence=weights.evidence_confidence,
        )

    @property
    def is_active(self) -> bool:
        return any(
            v > 0
            for v in (
                self.skill_fit,
                self.availability_fit,
                self.income_goal_fit,
                self.location_fit,
                self.eligibility_fit,
                self.deadline_fit,
            )
        )


# ==================================================================== scoring


def score(
    profile: UserProfile,
    opportunity: Opportunity,
    *,
    weights: Weights | None = None,
    adjustment: PreferenceAdjustment | None = None,
    now: datetime | None = None,
) -> MatchScore:
    """Compute the full match. Pure: same inputs, same output, every time."""
    now = now or utcnow()
    effective = (adjustment or PreferenceAdjustment()).apply(weights or DEFAULT_WEIGHTS)

    eligibility, hard_failures, uncertainties = score_eligibility_fit(profile, opportunity)
    components = [
        (score_skill_fit(profile, opportunity), effective.skill_fit),
        (score_experience_fit(profile, opportunity), effective.experience_fit),
        (score_language_fit(profile, opportunity), effective.language_fit),
        (score_location_fit(profile, opportunity), effective.location_fit),
        (score_availability_fit(profile, opportunity), effective.availability_fit),
        (eligibility, effective.eligibility_fit),
        (score_income_goal_fit(profile, opportunity), effective.income_goal_fit),
        (score_deadline_fit(opportunity, today=now.date()), effective.deadline_fit),
        (score_freshness(opportunity, now=now), effective.freshness),
        (score_evidence_confidence(opportunity), effective.evidence_confidence),
    ]
    weighted = [
        ScoreComponent(
            name=component.name,
            score=component.score,
            weight=weight,
            detail=component.detail,
            was_unknown=component.was_unknown,
        )
        for component, weight in components
    ]

    hard_failures.extend(_language_hard_failures(profile, opportunity))
    uncertainties.extend(_general_uncertainties(opportunity))

    total_weight = sum(c.weight for c in weighted) or 1.0
    raw = sum(c.weighted for c in weighted) / total_weight
    total = 0 if hard_failures else round(raw * 100)

    return MatchScore(
        opportunity_id=opportunity.id,
        total_score=max(0, min(100, total)),
        components=weighted,
        hard_failures=hard_failures,
        uncertainties=uncertainties,
        explanation_inputs=_explanation_inputs(weighted, hard_failures, uncertainties),
        weights_version=WEIGHTS_VERSION,
    )


def _language_hard_failures(
    profile: UserProfile, opportunity: Opportunity
) -> list[HardFailure]:
    """A stated hard language minimum the user demonstrably does not reach.

    Both sides must be known. An unstated level in the profile produces nothing
    here - the uncertainty is already recorded by the component.
    """
    failures: list[HardFailure] = []
    for requirement in opportunity.required_languages:
        if requirement.strength is not RequirementStrength.HARD:
            continue
        have = profile.professional.language_level(requirement.code)
        # Both sides must be known before a shortfall can be asserted.
        unknown = LanguageLevel.UNKNOWN in {requirement.minimum, have}
        if not unknown and LANGUAGE_ORDER[have] < LANGUAGE_ORDER[requirement.minimum]:
            failures.append(
                HardFailure(
                    requirement=f"{requirement.code.upper()} at {requirement.minimum.value}",
                    profile_value=have.value,
                    explanation=(
                        f"The source requires {requirement.code.upper()} at "
                        f"{requirement.minimum.value}; your profile states {have.value}."
                    ),
                )
            )
    return failures


def _general_uncertainties(opportunity: Opportunity) -> list[Uncertainty]:
    uncertainties: list[Uncertainty] = []
    if opportunity.compensation.known and not opportunity.compensation_verified:
        uncertainties.append(
            Uncertainty(
                topic="Compensation",
                explanation="A figure appears in the listing but we could not verify it.",
                how_to_resolve="Check the amount on the source page before applying.",
            )
        )
    if not opportunity.compensation.known:
        uncertainties.append(
            Uncertainty(
                topic="Compensation",
                explanation="The source does not publish what this pays.",
                how_to_resolve="Ask the organisation directly, before investing preparation time.",
            )
        )
    unknown_treatment = opportunity.compensation.tax_treatment.value == "UNKNOWN"
    if opportunity.compensation.known and unknown_treatment:
        uncertainties.append(
            Uncertainty(
                topic="Gross or net",
                explanation="The source does not say whether the amount is before or after tax.",
                how_to_resolve="Confirm with the organisation; it changes the figure materially.",
            )
        )
    return uncertainties


def _explanation_inputs(
    components: list[ScoreComponent],
    failures: list[HardFailure],
    uncertainties: list[Uncertainty],
) -> list[str]:
    """The exact sentences the explainer may use. It may rephrase, not extend."""
    lines: list[str] = []
    for component in sorted(components, key=lambda c: c.weighted, reverse=True):
        if component.weight <= 0:
            continue
        marker = "?" if component.was_unknown else ("+" if component.score >= 0.7 else "-")
        lines.append(f"{marker} {component.name}: {component.detail}")
    for failure in failures:
        lines.append(f"! blocked: {failure.explanation}")
    for uncertainty in uncertainties:
        lines.append(f"? {uncertainty.topic}: {uncertainty.explanation}")
    return lines
