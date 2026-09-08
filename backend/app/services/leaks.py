"""The second direction: money you lose by not knowing the rules.

The product's first direction finds income a person is not earning. This one
finds money already passing them by - an allowance nobody mentioned, a cost
they never wrote down, a threshold they are about to cross without noticing.
Both are "money you're missing"; only the second needs no new opportunity data,
which is why it can be useful on day one.

**What this is not.** It is not a comparison site for insurance, tariffs or
subscriptions. That is a different product, it needs a § 34d GewO permission to
do properly, and its only proven business model is commission from the provider
being recommended - which this product has committed in writing not to take.
See docs/BUSINESS_MODEL.md.

**Three rules hold every finding honest, and they are the same three that hold
the Germany check honest:**

1. **Every leak cites a stored ``LegalFact``.** A rule whose fact is missing or
   unavailable still fires, but without the figure: the question survives,
   the number does not. Nothing is written from model memory.
2. **A quoted amount is the statute's, never the user's.** ``stated_amount_minor``
   is what the law prints. There is no field for what a person would get,
   because working that out is the regulated act.
3. **Nothing is inferred about a person.** Benefit status, children and tax
   registration come from explicit disclosure or stay unknown, and unknown
   produces a question rather than an assumption.

Deterministic and pure: same inputs, same findings, in the same order. No model
is importable from here, and a test asserts that.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    BenefitDisclosure,
    IncomeStreamCategory,
    RemoteType,
    Tristate,
    WorkStatus,
)
from app.domain.finances import BaselinePicture, ExpenseSummary, HouseholdContext
from app.domain.legal import LegalFact
from app.domain.profile import UserProfile

#: Both of these mean there is an employment contract, and a contract is the
#: thing that may require notification. Missing the combined status would let
#: exactly the people most likely to need the question slip past it.
EMPLOYED_STATUSES: frozenset[WorkStatus] = frozenset(
    {WorkStatus.EMPLOYEE, WorkStatus.EMPLOYEE_AND_SELF_EMPLOYED}
)

#: Categories where the Uebungsleiter question is worth raising at all.
#: Teaching for a university or a charity may qualify; consulting for a
#: company does not, and asking everybody would make the finding noise.
TEACHING_CATEGORIES: frozenset[IncomeStreamCategory] = frozenset(
    {
        IncomeStreamCategory.TEACHING,
        IncomeStreamCategory.TUTORING,
        IncomeStreamCategory.MENTORING,
        IncomeStreamCategory.WORKSHOP,
    }
)


class Leak(BaseModel):
    """One thing worth checking, and why it is being raised for this person."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    #: What in the user's own data triggered this. Stated back to them so the
    #: finding is inspectable rather than mysterious.
    why_this_applies: str
    #: The specific thing to do or ask. Answerable by someone with authority to
    #: answer it - never "consult a professional".
    what_to_check: str
    #: Ids of the facts backing this. Empty when the corpus could not support
    #: the figure, in which case the finding carries no amount.
    fact_ids: list[str] = Field(default_factory=list)
    #: An amount **the statute prints**, in integer cents. Never an estimate of
    #: what this user would receive or save.
    stated_amount_minor: int | None = None
    amount_note: str | None = None


def _available(facts: list[LegalFact], fact_id: str) -> LegalFact | None:
    for fact in facts:
        if fact.id == fact_id and fact.content_available and fact.summary:
            return fact
    return None


def detect_leaks(
    *,
    profile: UserProfile | None,
    baseline: BaselinePicture,
    expenses: ExpenseSummary,
    household: HouseholdContext,
    engaged_categories: frozenset[IncomeStreamCategory] = frozenset(),
    earned_total_minor: int = 0,
    facts: list[LegalFact],
) -> list[Leak]:
    """Everything worth checking, given what this person has actually told us.

    Order is fixed and meaningful: findings that depend on something the user
    has already done come before general ones, because a finding about your own
    records is more credible than a finding about your category.
    """
    found: list[Leak] = []
    admin = profile.admin if profile else None
    earning = earned_total_minor > 0 or bool(baseline.entries)

    # ------------------------------------------------ costs never recorded
    if earning and expenses.count == 0:
        fact = _available(facts, "de_euer_eligibility")
        found.append(
            Leak(
                id="no_costs_recorded",
                title="You have income recorded but no costs",
                why_this_applies=(
                    "Earning usually costs something - equipment, travel, software, a fee. "
                    "You have not recorded any, so nothing here can be totalled."
                ),
                what_to_check=(
                    "Which of the things you already pay for are connected to this work? "
                    "Record them, then ask your Finanzamt which of them it accepts."
                ),
                fact_ids=[fact.id] if fact else [],
            )
        )

    # ------------------------------------------------------ working at home
    works_at_home = bool(
        profile
        and profile.time.remote_preference in {RemoteType.REMOTE, RemoteType.HYBRID}
    )
    if earning and works_at_home:
        fact = _available(facts, "de_homeoffice_pauschale")
        found.append(
            Leak(
                id="home_working_allowance",
                title="You work from home, at least part of the time",
                why_this_applies=(
                    "Your profile says you work remotely or in a hybrid arrangement, and "
                    "there are two separate allowances for that - which do not both apply."
                ),
                what_to_check=(
                    "Does the Tagespauschale per day at home apply to me, or is my study "
                    "the centre of my activity so that the Jahrespauschale applies "
                    "instead? What would I need to show for either?"
                ),
                fact_ids=[fact.id] if fact else [],
                stated_amount_minor=126_000 if fact else None,
                amount_note=(
                    "1,260 EUR is the annual ceiling the statute prints for both routes. "
                    "Whether any of it applies in your case is for a Finanzamt to say."
                )
                if fact
                else None,
            )
        )

    # ------------------------------------------ teaching for a public body
    if engaged_categories & TEACHING_CATEGORIES:
        fact = _available(facts, "de_uebungsleiterfreibetrag")
        found.append(
            Leak(
                id="uebungsleiter_allowance",
                title="You are pursuing teaching or training work",
                why_this_applies=(
                    "Teaching, training and mentoring can fall under the "
                    "Uebungsleiterfreibetrag - but only when the work serves charitable "
                    "or public purposes and is done for a qualifying body. Whether yours "
                    "does is a question about the organisation, not about you, and this "
                    "product cannot see it."
                ),
                what_to_check=(
                    "Is this organisation a public-law body or a recognised non-profit, "
                    "and would this engagement fall under § 3 Nr. 26 EStG?"
                ),
                fact_ids=[fact.id] if fact else [],
                stated_amount_minor=330_000 if fact else None,
                amount_note=(
                    "3,300 EUR a year is the ceiling in the statute, and it applies only "
                    "if the conditions above are met."
                )
                if fact
                else None,
            )
        )

    # ---------------------------------------------- self-employed and VAT
    self_employed = bool(
        admin
        and (
            admin.has_gewerbe is Tristate.YES
            or admin.has_freelance_tax_registration is Tristate.YES
        )
    )
    if self_employed:
        fact = _available(facts, "de_kleinunternehmer_thresholds")
        found.append(
            Leak(
                id="kleinunternehmer_threshold",
                title="You are registered, so the VAT thresholds apply to you",
                why_this_applies=(
                    "You have told us you are registered for a Gewerbe or as a "
                    "freelancer. The Kleinunternehmerregelung turns on turnover "
                    "thresholds, and crossing one changes what you must charge."
                ),
                what_to_check=(
                    "What was my turnover last year, what do I expect this year, and does "
                    "the Kleinunternehmerregelung still apply to me?"
                ),
                fact_ids=[fact.id] if fact else [],
            )
        )

    # ---------------------------------- earning without a tax registration
    if (
        earned_total_minor > 0
        and admin
        and admin.has_freelance_tax_registration is not Tristate.YES
        and admin.has_gewerbe is not Tristate.YES
    ):
        fact = _available(facts, "de_tax_registration_deadline")
        found.append(
            Leak(
                id="registration_not_confirmed",
                title="You have recorded earnings but not confirmed a registration",
                why_this_applies=(
                    "You have recorded money actually received, and your profile does not "
                    "say you are registered. There is a deadline attached to starting an "
                    "activity, and it is short."
                ),
                what_to_check=(
                    "Does the work I have been paid for require me to notify the tax "
                    "office, and by when?"
                ),
                fact_ids=[fact.id] if fact else [],
            )
        )

    # -------------------------------------------------- benefits, disclosed
    if admin and admin.receives_employment_benefits is BenefitDisclosure.YES:
        hours = _available(facts, "de_alg_hours_limit")
        allowance = _available(facts, "de_alg_nebeneinkommen_freibetrag")
        found.append(
            Leak(
                id="benefit_limits",
                title="You have told us you receive benefits",
                why_this_applies=(
                    "You disclosed this yourself - it is never inferred. Secondary income "
                    "and working hours both interact with the benefit, and the interaction "
                    "runs in the other direction from everything else on this page: "
                    "earning more can reduce what you receive."
                ),
                what_to_check=(
                    "How many hours a week may I work, and how much may I earn, before my "
                    "benefit is affected? Do I have to notify anyone in advance?"
                ),
                fact_ids=[fact.id for fact in (hours, allowance) if fact],
            )
        )
    elif admin and admin.receives_employment_benefits is BenefitDisclosure.UNKNOWN:
        # Not a finding about the law - a prompt to tell us, because the rules
        # above cannot be raised for someone who has not said either way.
        found.append(
            Leak(
                id="benefit_status_unknown",
                title="Benefits are the one thing that can work against you",
                why_this_applies=(
                    "You have not said whether you receive any, and we never infer it. "
                    "If you do, some of the advice on this page runs backwards."
                ),
                what_to_check=(
                    "If you receive Arbeitslosengeld or similar, say so in your profile "
                    "and this page will raise the limits that apply."
                ),
            )
        )

    # ------------------------------------------------- children, disclosed
    if household.has_children is Tristate.YES:
        fact = _available(facts, "de_kinderfreibetrag")
        found.append(
            Leak(
                id="child_allowances",
                title="You have told us you have children",
                why_this_applies=(
                    "Children are taken into account at assessment. Which of the two "
                    "routes works out better for you is decided there, not here."
                ),
                what_to_check=(
                    "Is the Kinderfreibetrag or the Kindergeld more favourable in my "
                    "assessment, and do I need to do anything to claim it?"
                ),
                fact_ids=[fact.id] if fact else [],
            )
        )

    # ------------------------------------- employed and earning on the side
    if (
        profile
        and profile.work_status in EMPLOYED_STATUSES
        and earned_total_minor > 0
        and admin
        and admin.knows_employer_nebentaetigkeit_rules is not Tristate.YES
    ):
        found.append(
            Leak(
                id="employer_rules_unchecked",
                title="You are employed and have not checked your contract",
                why_this_applies=(
                    "You are in employment and have recorded side income, and your profile "
                    "does not say you have checked what your contract requires."
                ),
                what_to_check=(
                    "Does my employment contract require me to notify or seek approval for "
                    "secondary activity, and does this work fall under it?"
                ),
            )
        )

    return found


def summarise_leaks(leaks: list[Leak]) -> dict[str, int]:
    """Counts for the dashboard band. Deliberately not a euro figure.

    There is no "total you could save" here and there will not be one: adding
    up statutory ceilings a person may not qualify for would produce exactly
    the confident, wrong number this product exists to avoid.
    """
    return {
        "total": len(leaks),
        "with_sources": sum(1 for leak in leaks if leak.fact_ids),
    }
