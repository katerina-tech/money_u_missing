"""The "money you lose" engine, and the boundaries it must not cross.

The rules that matter here are negative: no finding without a trigger in the
user's own data, no figure without a statute behind it, and nothing inferred
about benefits, children or registration.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.domain.enums import (
    BenefitDisclosure,
    IncomeStreamCategory,
    LegalCategory,
    LegalVerificationStatus,
    RemoteType,
    Tristate,
    WorkStatus,
)
from app.domain.finances import (
    BaselineIncome,
    BaselinePicture,
    ExpenseSummary,
    HouseholdContext,
)
from app.domain.legal import LegalFact
from app.services.leaks import Leak, detect_leaks, summarise_leaks
from tests.conftest import make_profile

NOW = datetime.now(UTC)


def fact(fact_id: str, *, available: bool = True) -> LegalFact:
    return LegalFact(
        id=fact_id,
        jurisdiction="DE",
        category=LegalCategory.INCOME_TAX,
        title=fact_id,
        summary="Something the statute says." if available else "",
        source_name="Gesetze im Internet",
        source_url="https://www.gesetze-im-internet.de/estg/__3.html",
        last_verified_at=NOW,
        verification_status=LegalVerificationStatus.VERIFIED,
        content_available=available,
    )


ALL_FACTS = [
    fact("de_euer_eligibility"),
    fact("de_homeoffice_pauschale"),
    fact("de_uebungsleiterfreibetrag"),
    fact("de_kleinunternehmer_thresholds"),
    fact("de_tax_registration_deadline"),
    fact("de_alg_hours_limit"),
    fact("de_alg_nebeneinkommen_freibetrag"),
    fact("de_kinderfreibetrag"),
]


def run(**overrides: object) -> list[Leak]:
    kwargs: dict[str, object] = {
        "profile": None,
        "baseline": BaselinePicture(),
        "expenses": ExpenseSummary(),
        "household": HouseholdContext(),
        "facts": ALL_FACTS,
    }
    kwargs.update(overrides)
    return detect_leaks(**kwargs)  # type: ignore[arg-type]


def ids(leaks: list[Leak]) -> set[str]:
    return {leak.id for leak in leaks}


# ---------------------------------------------------------- nothing known


def test_an_empty_account_produces_no_findings_about_the_law() -> None:
    """Nothing entered means nothing to say. No filler, no generic tips."""
    assert run() == []


def test_findings_are_deterministic() -> None:
    profile = make_profile()
    first = run(profile=profile, earned_total_minor=50_000)
    second = run(profile=profile, earned_total_minor=50_000)
    assert [leak.id for leak in first] == [leak.id for leak in second]


def test_no_language_model_is_reachable_from_this_module() -> None:
    """Same guard the matching engine has, for the same reason."""
    import app.services.leaks as module

    text = Path(module.__file__ or "").read_text(encoding="utf-8")
    for forbidden in ("from app.llm", "import anthropic", "LLMProvider"):
        assert forbidden not in text


# ------------------------------------------------------------- triggering


def test_income_without_any_recorded_cost_is_raised() -> None:
    leaks = run(
        baseline=BaselinePicture(entries=[BaselineIncome(label="Job", amount_minor=200_000)])
    )
    assert "no_costs_recorded" in ids(leaks)


def test_recorded_costs_remove_that_finding() -> None:
    leaks = run(
        baseline=BaselinePicture(entries=[BaselineIncome(label="Job", amount_minor=200_000)]),
        expenses=ExpenseSummary(count=3, total_minor=10_000, disclaimer="x"),
    )
    assert "no_costs_recorded" not in ids(leaks)


def test_working_from_home_raises_the_allowance_with_the_statutes_ceiling() -> None:
    profile = make_profile()
    profile.time.remote_preference = RemoteType.REMOTE
    leaks = run(profile=profile, earned_total_minor=10_000)

    home = next(leak for leak in leaks if leak.id == "home_working_allowance")
    # 1,260 EUR is what the statute prints - not what this user gets.
    assert home.stated_amount_minor == 126_000
    assert "for a Finanzamt to say" in (home.amount_note or "")


def test_teaching_work_raises_the_uebungsleiter_question_as_a_question() -> None:
    leaks = run(engaged_categories=frozenset({IncomeStreamCategory.TEACHING}))
    teaching = next(leak for leak in leaks if leak.id == "uebungsleiter_allowance")
    assert teaching.stated_amount_minor == 330_000
    # The condition is about the organisation, and the finding says so rather
    # than implying the allowance applies.
    assert "cannot see it" in teaching.why_this_applies
    assert teaching.what_to_check.endswith("?")


def test_consulting_does_not_raise_the_teaching_finding() -> None:
    leaks = run(engaged_categories=frozenset({IncomeStreamCategory.CONSULTING}))
    assert "uebungsleiter_allowance" not in ids(leaks)


# ------------------------------------------------- disclosure, never guessed


def test_benefits_are_only_raised_on_explicit_disclosure() -> None:
    profile = make_profile()
    profile.admin.receives_employment_benefits = BenefitDisclosure.YES
    assert "benefit_limits" in ids(run(profile=profile))

    profile.admin.receives_employment_benefits = BenefitDisclosure.NO
    assert "benefit_limits" not in ids(run(profile=profile))


def test_an_undisclosed_benefit_status_produces_a_prompt_not_an_assumption() -> None:
    profile = make_profile()
    profile.admin.receives_employment_benefits = BenefitDisclosure.UNKNOWN
    prompt = next(leak for leak in run(profile=profile) if leak.id == "benefit_status_unknown")
    # It asks the user, and cites nothing, because there is nothing to cite.
    assert prompt.fact_ids == []
    assert prompt.stated_amount_minor is None


def test_children_are_only_raised_on_explicit_disclosure() -> None:
    assert "child_allowances" not in ids(run())
    assert "child_allowances" in ids(run(household=HouseholdContext(has_children=Tristate.YES)))


def test_an_employed_person_earning_on_the_side_is_asked_about_their_contract() -> None:
    profile = make_profile()
    profile.work_status = WorkStatus.EMPLOYEE
    profile.admin.knows_employer_nebentaetigkeit_rules = Tristate.UNKNOWN
    assert "employer_rules_unchecked" in ids(run(profile=profile, earned_total_minor=45_000))


def test_having_checked_the_contract_removes_that_finding() -> None:
    profile = make_profile()
    profile.work_status = WorkStatus.EMPLOYEE
    profile.admin.knows_employer_nebentaetigkeit_rules = Tristate.YES
    assert "employer_rules_unchecked" not in ids(run(profile=profile, earned_total_minor=45_000))


# ------------------------------------------------------ the corpus is honest


def test_an_unavailable_fact_removes_the_figure_but_keeps_the_question() -> None:
    """The designed degradation, and the most important test in this file."""
    profile = make_profile()
    profile.time.remote_preference = RemoteType.REMOTE
    without = [f for f in ALL_FACTS if f.id != "de_homeoffice_pauschale"]
    without.append(fact("de_homeoffice_pauschale", available=False))

    home = next(
        leak
        for leak in run(profile=profile, earned_total_minor=10_000, facts=without)
        if leak.id == "home_working_allowance"
    )
    assert home.stated_amount_minor is None
    assert home.fact_ids == []
    # The question is still worth asking, and costs nothing to state.
    assert "Tagespauschale" in home.what_to_check


def test_no_finding_ever_claims_a_saving() -> None:
    profile = make_profile()
    profile.time.remote_preference = RemoteType.REMOTE
    profile.admin.has_gewerbe = Tristate.YES
    profile.admin.receives_employment_benefits = BenefitDisclosure.YES

    leaks = run(
        profile=profile,
        household=HouseholdContext(has_children=Tristate.YES),
        engaged_categories=frozenset({IncomeStreamCategory.TEACHING}),
        earned_total_minor=90_000,
    )
    assert leaks
    prose = " ".join(f"{leak.why_this_applies} {leak.what_to_check} {leak.amount_note or ''}" for leak in leaks)
    for forbidden in ("you will save", "you will receive", "you are entitled to", "refund of"):
        assert forbidden not in prose.lower()


def test_the_summary_counts_findings_and_never_totals_money() -> None:
    leaks = run(household=HouseholdContext(has_children=Tristate.YES))
    summary = summarise_leaks(leaks)
    assert summary["total"] == len(leaks)
    assert "total_minor" not in summary
    assert "saving_minor" not in summary
