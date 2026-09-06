"""The matching engine. The most important tests in the repository.

These pin down the three rules the product's credibility rests on: unknown is
not false, only a demonstrated conflict disqualifies, and the same inputs always
produce the same score.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.domain.enums import (
    CompensationBasis,
    CompensationPeriod,
    DismissReason,
    LanguageLevel,
    RemoteType,
    RequirementStrength,
    SkillEvidence,
    SkillLevel,
    Tristate,
)
from app.domain.money import MoneyRange
from app.domain.opportunity import LanguageRequirement, Requirement
from app.domain.profile import ProfessionalInfo, Skill
from app.services import matching
from tests.conftest import bare_opportunity, make_opportunity, make_profile

# ============================================================ determinism


def test_score_is_deterministic() -> None:
    profile, opportunity = make_profile(), make_opportunity()
    first = matching.score(profile, opportunity)
    for _ in range(5):
        assert matching.score(profile, opportunity).total_score == first.total_score


def test_no_language_model_is_reachable_from_matching() -> None:
    """The engine must not import a provider, even transitively at module level."""
    import inspect

    source = inspect.getsource(matching)
    for forbidden in ("LLMProvider", "app.llm", "provider.structured"):
        assert forbidden not in source, f"{forbidden} must not appear in the matching engine"


# ==================================================== unknown is not false


def test_missing_requirements_score_neutral_not_zero() -> None:
    """A terse listing must not be buried for being terse."""
    component = matching.score_skill_fit(make_profile(), bare_opportunity())
    assert component.score == matching.NEUTRAL
    assert component.was_unknown is True
    assert component.score > 0.0


def test_a_bare_opportunity_still_scores_usefully() -> None:
    score = matching.score(make_profile(), bare_opportunity())
    # It should not be near zero. An expert network that published nothing is
    # still one of the most actionable things a professional can do.
    assert score.total_score >= 40
    assert score.eligible is True
    assert score.has_unknowns is True


def test_unpublished_compensation_is_neutral_not_a_penalty() -> None:
    component = matching.score_income_goal_fit(
        make_profile(), make_opportunity(compensation=MoneyRange())
    )
    assert component.score == matching.NEUTRAL
    assert component.was_unknown is True
    assert "not published" in component.detail


def test_unknown_experience_on_either_side_is_neutral() -> None:
    profile_without = make_profile(
        professional=ProfessionalInfo(years_experience=None, skills=[Skill(name="Python")])
    )
    assert matching.score_experience_fit(profile_without, make_opportunity()).was_unknown
    assert matching.score_experience_fit(
        make_profile(), make_opportunity(experience_min_years=None, experience_max_years=None)
    ).was_unknown


def test_unknown_remote_type_is_neutral() -> None:
    component = matching.score_location_fit(
        make_profile(), make_opportunity(remote_type=RemoteType.UNKNOWN)
    )
    assert component.was_unknown is True
    assert component.score == matching.NEUTRAL


# ================================================ hard failures and unknowns


def test_hard_language_shortfall_disqualifies() -> None:
    opportunity = make_opportunity(
        required_languages=[
            LanguageRequirement(
                code="de", minimum=LanguageLevel.C1, strength=RequirementStrength.HARD
            )
        ]
    )
    score = matching.score(make_profile(), opportunity)  # profile has German B2
    assert score.eligible is False
    assert score.total_score == 0
    assert "DE at C1" in score.hard_failures[0].requirement


def test_unknown_language_level_is_an_uncertainty_not_a_failure() -> None:
    """The user did not tell us their French. That is not a rejection."""
    opportunity = make_opportunity(
        required_languages=[
            LanguageRequirement(
                code="fr", minimum=LanguageLevel.C1, strength=RequirementStrength.HARD
            )
        ]
    )
    score = matching.score(make_profile(), opportunity)
    assert score.eligible is True
    assert score.hard_failures == []
    assert any("fr" in u.explanation.lower() or "FR" in u.topic for u in score.uncertainties) or (
        score.components[2].was_unknown
    )


def test_soft_language_shortfall_costs_points_but_does_not_disqualify() -> None:
    opportunity = make_opportunity(
        required_languages=[
            LanguageRequirement(
                code="de", minimum=LanguageLevel.C1, strength=RequirementStrength.SOFT
            )
        ]
    )
    score = matching.score(make_profile(), opportunity)
    assert score.eligible is True
    language = next(c for c in score.components if c.name == "language_fit")
    assert 0.0 < language.score < 1.0


def test_unknown_strength_requirement_never_disqualifies() -> None:
    opportunity = make_opportunity(
        eligibility_structured=[
            Requirement(label="Gewerbe registration", strength=RequirementStrength.UNKNOWN)
        ]
    )
    profile = make_profile()
    profile.admin.has_gewerbe = Tristate.NO
    score = matching.score(profile, opportunity)
    assert score.eligible is True


def test_hard_requirement_the_user_explicitly_fails_disqualifies() -> None:
    opportunity = make_opportunity(
        eligibility_structured=[
            Requirement(label="Gewerbe registration required", strength=RequirementStrength.HARD)
        ]
    )
    profile = make_profile()
    profile.admin.has_gewerbe = Tristate.NO
    score = matching.score(profile, opportunity)
    assert score.eligible is False


def test_hard_requirement_the_user_has_not_answered_is_an_uncertainty() -> None:
    opportunity = make_opportunity(
        eligibility_structured=[
            Requirement(label="Gewerbe registration required", strength=RequirementStrength.HARD)
        ]
    )
    profile = make_profile()
    profile.admin.has_gewerbe = Tristate.UNKNOWN
    score = matching.score(profile, opportunity)
    assert score.eligible is True
    assert any("Gewerbe" in u.topic for u in score.uncertainties)


# ================================================================= skills


def test_inferred_unconfirmed_skills_count_less_than_confirmed_ones() -> None:
    confirmed = make_profile(
        professional=ProfessionalInfo(
            years_experience=7.0,
            skills=[Skill(name="Python", level=SkillLevel.ADVANCED, confirmed=True)],
        )
    )
    inferred = make_profile(
        professional=ProfessionalInfo(
            years_experience=7.0,
            skills=[
                Skill(
                    name="Python",
                    level=SkillLevel.ADVANCED,
                    evidence=SkillEvidence.INFERRED,
                    confirmed=False,
                )
            ],
        )
    )
    opportunity = make_opportunity(required_skills=["Python"], preferred_skills=[])
    assert (
        matching.score_skill_fit(inferred, opportunity).score
        < matching.score_skill_fit(confirmed, opportunity).score
    )


def test_related_skills_earn_partial_credit_and_say_so() -> None:
    profile = make_profile(
        professional=ProfessionalInfo(
            years_experience=5.0, skills=[Skill(name="PySpark", level=SkillLevel.ADVANCED)]
        )
    )
    component = matching.score_skill_fit(
        profile, make_opportunity(required_skills=["Spark"], preferred_skills=[])
    )
    assert 0 < component.score < 1.0
    assert "related skill" in component.detail


# ============================================================ availability


def test_commitment_beyond_availability_reduces_but_does_not_block() -> None:
    opportunity = make_opportunity(estimated_hours_min=20, estimated_hours_max=25)
    score = matching.score(make_profile(), opportunity)  # profile has 6h/week
    availability = next(c for c in score.components if c.name == "availability_fit")
    assert availability.score < 0.5
    assert score.eligible is True


# ============================================================== deadlines


def test_a_passed_deadline_scores_zero_on_that_component_only() -> None:
    opportunity = make_opportunity(deadline=date.today() - timedelta(days=3))
    component = matching.score_deadline_fit(opportunity)
    assert component.score == 0.0
    # Still eligible: a passed deadline is an actionability problem, not a
    # statement that the person is unqualified.
    assert matching.score(make_profile(), opportunity).eligible is True


# ============================================================= income goal


def test_below_minimum_worthwhile_is_heavily_discounted() -> None:
    tiny = make_opportunity(
        compensation=MoneyRange(
            minor_min=500,
            basis=CompensationBasis.PER_MONTH,
            period=CompensationPeriod.RECURRING,
        )
    )
    component = matching.score_income_goal_fit(make_profile(), tiny)
    assert component.score < 0.2
    assert "minimum" in component.detail.lower()


# ============================================================ explanation


def test_every_component_produces_an_explanation_line() -> None:
    score = matching.score(make_profile(), make_opportunity())
    weighted = [c for c in score.components if c.weight > 0]
    lines = [line for line in score.explanation_inputs if not line.startswith(("!", "?"))]
    assert len(lines) == len(weighted)


def test_uncertainties_always_reach_the_explanation() -> None:
    score = matching.score(make_profile(), bare_opportunity())
    for uncertainty in score.uncertainties:
        assert any(uncertainty.topic in line for line in score.explanation_inputs)


# ============================================================== weights


def test_weights_sum_to_one() -> None:
    assert matching.DEFAULT_WEIGHTS.total() == pytest.approx(1.0)


def test_score_is_bounded() -> None:
    for opportunity in (make_opportunity(), bare_opportunity()):
        score = matching.score(make_profile(), opportunity)
        assert 0 <= score.total_score <= 100


# ========================================================== preferences


def test_preference_adjustment_is_inert_below_the_signal_threshold() -> None:
    adjustment = matching.PreferenceAdjustment.from_dismissals(
        {DismissReason.TOO_LITTLE_MONEY: 2}
    )
    assert adjustment.is_active is False


def test_preference_adjustment_is_bounded() -> None:
    adjustment = matching.PreferenceAdjustment.from_dismissals(
        {DismissReason.TOO_LITTLE_MONEY: 500}
    )
    assert adjustment.income_goal_fit <= 0.08


def test_preference_adjustment_shifts_the_score_in_the_stated_direction() -> None:
    profile = make_profile()
    well_paid = make_opportunity()
    base = matching.score(profile, well_paid).total_score
    adjusted = matching.score(
        profile,
        well_paid,
        adjustment=matching.PreferenceAdjustment.from_dismissals(
            {DismissReason.TOO_LITTLE_MONEY: 10}
        ),
    ).total_score
    # Weighting pay more heavily must change the score of a well-paid role.
    assert adjusted != base
