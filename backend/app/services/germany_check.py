"""The Germany Check: what an opportunity may mean administratively.

This is the product's most distinctive feature and its most dangerous one, so
the rules are strict and deterministic:

* **Considerations, never determinations.** Every line is "this may", "this
  depends on", or a question. The module never says the user is freiberuflich
  or gewerblich - that classification turns on facts we cannot see and is
  contested even between Finanzämter - and it never produces a tax figure.
* **Nothing is inferred about the person.** Benefit guidance appears only when
  the user has explicitly disclosed benefit receipt. Employer guidance appears
  only when they have told us they are employed. UNKNOWN produces a question,
  not an assumption.
* **Rules come from :class:`~app.domain.legal.LegalFact` rows**, not from
  prompts, and a fact past its review horizon flags the whole check as needing
  verification rather than being quoted confidently.

The output is built by ordinary Python from the opportunity's category and the
user's declared status. No model is involved, because a model asked to reason
about someone's tax position will produce a fluent, specific, and unaccountable
answer - which is the opposite of what this needs to be.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.domain.enums import (
    BenefitDisclosure,
    EmploymentType,
    IncomeStreamCategory,
    LegalCategory,
    LegalVerificationStatus,
    Tristate,
    WorkStatus,
)
from app.domain.legal import Citation, GermanyCheck
from app.domain.opportunity import Opportunity
from app.domain.profile import UserProfile
from app.services.legal_facts import LegalFactRepository

#: Categories that typically constitute self-employed activity in Germany. The
#: word "typically" is doing real work: the classification depends on how the
#: engagement is actually structured, which is why the output is a question.
SELF_EMPLOYED_CATEGORIES = frozenset(
    {
        IncomeStreamCategory.FREELANCE_PROJECT,
        IncomeStreamCategory.CONSULTING,
        IncomeStreamCategory.EXPERT_CALL,
        IncomeStreamCategory.ADVISORY,
        IncomeStreamCategory.WORKSHOP,
        IncomeStreamCategory.SPEAKING,
        IncomeStreamCategory.MENTORING,
        IncomeStreamCategory.TEACHING,
        IncomeStreamCategory.TUTORING,
        IncomeStreamCategory.CREATOR_OPPORTUNITY,
        IncomeStreamCategory.DIGITAL_PRODUCT,
    }
)

EMPLOYMENT_CATEGORIES = frozenset(
    {
        IncomeStreamCategory.FULL_TIME_JOB,
        IncomeStreamCategory.PART_TIME_JOB,
        IncomeStreamCategory.MINIJOB,
    }
)

GRANT_CATEGORIES = frozenset(
    {
        IncomeStreamCategory.GRANT,
        IncomeStreamCategory.FELLOWSHIP,
        IncomeStreamCategory.PAID_PROGRAM,
        IncomeStreamCategory.FOUNDER_PROGRAM,
        IncomeStreamCategory.COMPETITION,
        IncomeStreamCategory.PRIZE,
    }
)

#: Which legal-fact topics each opportunity shape needs.
_TOPICS: dict[str, tuple[LegalCategory, ...]] = {
    "self_employed": (
        LegalCategory.SELF_EMPLOYMENT,
        LegalCategory.TRADE_REGISTRATION,
        LegalCategory.VAT,
        LegalCategory.INVOICING,
        LegalCategory.INCOME_TAX,
    ),
    "employment": (
        LegalCategory.EMPLOYMENT,
        LegalCategory.MINIJOB,
        LegalCategory.SOCIAL_INSURANCE,
        LegalCategory.INCOME_TAX,
    ),
    "grant": (LegalCategory.INCOME_TAX, LegalCategory.SELF_EMPLOYMENT),
}


class GermanyCheckService:
    def __init__(self, facts: LegalFactRepository, settings: Settings | None = None) -> None:
        self._facts = facts
        self._settings = settings or get_settings()

    def check(
        self, session: Session, profile: UserProfile, opportunity: Opportunity
    ) -> GermanyCheck:
        shape = self._shape(opportunity)
        considerations: list[str] = []
        questions: list[str] = []
        employment_notes: list[str] = []
        benefit_notes: list[str] = []

        if shape == "self_employed":
            considerations.extend(
                [
                    "This may constitute self-employed activity (selbststaendige Taetigkeit) "
                    "rather than employment.",
                    "Whether it counts as freiberuflich or gewerblich depends on the nature "
                    "of the work and how the engagement is structured. This product does not "
                    "make that classification.",
                    "Tax registration may be required before you invoice for the first time.",
                    "VAT treatment depends on your total turnover and on whether the "
                    "Kleinunternehmerregelung applies to you.",
                    "You will need to issue invoices that meet the statutory content "
                    "requirements.",
                ]
            )
            questions.extend(
                [
                    "Is this activity freiberuflich or gewerblich in my specific case?",
                    "Do I need to submit a Fragebogen zur steuerlichen Erfassung, and by when?",
                    "Does the Kleinunternehmerregelung apply to my expected turnover?",
                    "What must appear on my invoices for this work?",
                ]
            )
            if profile.admin.has_gewerbe is Tristate.UNKNOWN:
                questions.append("Do I already have a Gewerbe, and does this work fall under it?")
            if profile.admin.has_freelance_tax_registration is Tristate.NO:
                considerations.append(
                    "You have said you are not yet registered for tax as a freelancer. "
                    "That registration is normally the first step, before invoicing."
                )

        elif shape == "employment":
            considerations.extend(
                [
                    "This looks like employment rather than self-employment, so tax and "
                    "social insurance are normally handled through payroll.",
                    "A second employment alongside an existing one can change your tax "
                    "class and your social insurance position.",
                ]
            )
            questions.extend(
                [
                    "How does a second employment affect my Steuerklasse?",
                    "What are the social insurance consequences of adding this alongside "
                    "my main job?",
                ]
            )
            if opportunity.category is IncomeStreamCategory.MINIJOB:
                considerations.append(
                    "Minijob earnings are subject to a monthly ceiling, and exceeding it "
                    "changes how the employment is treated."
                )

        else:  # grant, prize, programme
            considerations.extend(
                [
                    "Grant, stipend and prize income is not automatically tax-free in "
                    "Germany; the treatment depends on the programme's legal basis and on "
                    "what the money is for.",
                    "Some programmes require you to be registered as self-employed or to "
                    "have a company before funds can be paid out.",
                ]
            )
            questions.extend(
                [
                    "Is this payment taxable income in my circumstances?",
                    "Does the programme require a particular legal form before payout?",
                    "Does accepting this affect any other funding or support I receive?",
                ]
            )

        # --- employment-contract considerations, only when they told us
        if profile.work_status in {
            WorkStatus.EMPLOYEE,
            WorkStatus.EMPLOYEE_AND_SELF_EMPLOYED,
        }:
            employment_notes.append(
                "You have told us you are employed. Employment contracts in Germany "
                "commonly require a Nebentaetigkeit to be notified to, or approved by, "
                "the employer - and may restrict work for competitors."
            )
            if profile.admin.knows_employer_nebentaetigkeit_rules is not Tristate.YES:
                questions.insert(
                    0,
                    "What does my employment contract say about Nebentaetigkeit, and do I "
                    "need to notify or obtain approval from my employer?",
                )

        # --- benefit considerations, ONLY on explicit disclosure
        if profile.admin.receives_employment_benefits is BenefitDisclosure.YES:
            benefit_notes.extend(
                [
                    "You have told us you receive employment-related benefits. Additional "
                    "earnings normally have to be reported to the paying authority, and "
                    "they may reduce your entitlement.",
                    "Reporting obligations usually apply from the point the work is taken "
                    "on, not from when you are paid.",
                ]
            )
            questions.append(
                "How and when must I report this activity and its income to the "
                "authority paying my benefits?"
            )

        # --- source-backed facts and freshness
        topics = list(_TOPICS[shape])
        facts = self._facts.for_topics(session, topics)
        max_age = timedelta(days=self._settings.legal_fact_max_age_days)
        needs_verification = False
        citations: list[Citation] = []

        for fact in facts:
            status = fact.effective_status(max_age=max_age)
            if status is not LegalVerificationStatus.VERIFIED:
                needs_verification = True
            if fact.source_url:
                citations.append(
                    Citation(
                        source_name=fact.source_name,
                        source_url=fact.source_url,
                        title=fact.title,
                        chunk_id=f"fact:{fact.id}",
                        effective_year=fact.effective_from.year if fact.effective_from else None,
                        retrieved_at=fact.last_verified_at or fact.retrieved_at,
                        excerpt=fact.summary[:600],
                    )
                )

        if not facts:
            # Say so rather than presenting an unsourced list as authoritative.
            needs_verification = True

        if opportunity.is_demo:
            considerations.insert(
                0,
                "This is a demo opportunity. The considerations below are real, but this "
                "particular listing is not.",
            )

        return GermanyCheck(
            opportunity_id=opportunity.id,
            considerations=considerations,
            questions_to_check=questions,
            benefit_notes=benefit_notes,
            employment_notes=employment_notes,
            official_sources=citations,
            facts_referenced=[fact.id for fact in facts],
            needs_verification=needs_verification,
        )

    @staticmethod
    def _shape(opportunity: Opportunity) -> str:
        if opportunity.employment_type is EmploymentType.EMPLOYEE:
            return "employment"
        if opportunity.category in EMPLOYMENT_CATEGORIES:
            return "employment"
        if opportunity.category in GRANT_CATEGORIES:
            return "grant"
        if opportunity.category in SELF_EMPLOYED_CATEGORIES:
            return "self_employed"
        return "self_employed"
