"""Persistence and assembly for the personal money picture.

The arithmetic lives in ``app.domain.finances``; this module reads and writes
rows and hands the domain the data. Nothing here computes a tax effect, and
nothing here converts between gross and net - see the domain module's docstring
for why that is a boundary rather than a missing feature.

The one piece of real judgement in this file is ``deduction_questions``, which
attaches the German legal context to the expense records. It follows the same
pattern as the Germany check: every statement comes from a stored ``LegalFact``
with a source URL and a retrieval date, the questions are specific enough for a
Finanzamt to answer, and when a fact is unavailable the topic is dropped rather
than filled in from memory.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BaselineIncomeRow, ExpenseRow, Profile
from app.domain.enums import Tristate
from app.domain.finances import (
    BaselineIncome,
    BaselinePicture,
    Child,
    DeductibleExpense,
    ExpenseSummary,
    HouseholdContext,
    summarise_expenses,
)
from app.domain.legal import LegalFact

# ------------------------------------------------------------- baseline


def load_baseline(session: Session, user_id: str) -> BaselinePicture:
    rows = session.scalars(
        select(BaselineIncomeRow)
        .where(BaselineIncomeRow.user_id == user_id)
        .order_by(BaselineIncomeRow.is_primary.desc(), BaselineIncomeRow.label)
    ).all()
    return BaselinePicture(
        entries=[
            BaselineIncome(
                label=row.label,
                amount_minor=row.amount_minor,
                currency=row.currency,
                basis=row.basis,  # type: ignore[arg-type]
                period=row.period,  # type: ignore[arg-type]
                is_primary=row.is_primary,
                started_on=row.started_on,
            )
            for row in rows
        ],
        currency=rows[0].currency if rows else "EUR",
    )


def demote_other_primaries(session: Session, user_id: str, keep_id: str | None) -> None:
    """At most one baseline income is the primary one.

    Enforced here rather than by a unique index: "exactly one primary" is not
    true while a user has none, and a partial index that means "at most one"
    is not portable across the two databases this product supports.
    """
    for row in session.scalars(
        select(BaselineIncomeRow).where(
            BaselineIncomeRow.user_id == user_id,
            BaselineIncomeRow.is_primary.is_(True),
        )
    ).all():
        if row.id != keep_id:
            row.is_primary = False


# ------------------------------------------------------------- expenses


def load_expenses(
    session: Session, user_id: str, *, year: int | None = None
) -> list[DeductibleExpense]:
    statement = select(ExpenseRow).where(ExpenseRow.user_id == user_id)
    rows = session.scalars(statement.order_by(ExpenseRow.incurred_on.desc())).all()
    return [
        DeductibleExpense(
            label=row.label,
            amount_minor=row.amount_minor,
            currency=row.currency,
            category=row.category,  # type: ignore[arg-type]
            incurred_on=row.incurred_on,
            has_receipt=row.has_receipt,  # type: ignore[arg-type]
            partly_private=row.partly_private,  # type: ignore[arg-type]
            income_stream_id=row.income_stream_id,
            application_id=row.application_id,
            notes=row.notes,
        )
        for row in rows
        if year is None or row.incurred_on.year == year
    ]


def expense_summary(session: Session, user_id: str, *, year: int | None = None) -> ExpenseSummary:
    return summarise_expenses(load_expenses(session, user_id, year=year))


# ------------------------------------------------------------ household


def load_household(profile: Profile | None) -> HouseholdContext:
    """Read the household context off the profile row.

    A malformed ``children`` document degrades to "no children recorded"
    rather than raising: a bad JSON blob should cost the user the list, not
    the whole personal page.
    """
    if profile is None:
        return HouseholdContext()

    raw = profile.children if isinstance(profile.children, dict) else {}
    entries = raw.get("entries", []) if isinstance(raw.get("entries"), list) else []
    children: list[Child] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            children.append(Child.model_validate(entry))
        except ValueError:
            continue

    has_children = profile.has_children
    # A recorded child with a stale NO would fail the domain validator, and a
    # page that cannot render is worse than a corrected flag.
    if children and has_children == Tristate.NO.value:
        has_children = Tristate.YES.value

    return HouseholdContext(
        has_children=has_children,  # type: ignore[arg-type]
        jointly_assessed=profile.jointly_assessed,  # type: ignore[arg-type]
        children=children,
    )


def store_household(profile: Profile, household: HouseholdContext) -> None:
    profile.has_children = household.has_children.value
    profile.jointly_assessed = household.jointly_assessed.value
    profile.children = {"entries": [child.model_dump(mode="json") for child in household.children]}


# ------------------------------------------------- the German context


#: Legal facts this module will cite, by the topic they support. A fact that is
#: missing or unavailable simply removes its topic; nothing is written from
#: memory to fill the gap.
EXPENSE_FACT_IDS: tuple[str, ...] = ("de_euer_eligibility", "de_invoice_requirements")
CHILD_FACT_IDS: tuple[str, ...] = ("de_kinderfreibetrag",)


def deduction_context(
    facts: list[LegalFact], household: HouseholdContext
) -> tuple[list[LegalFact], list[str]]:
    """The citable facts for the personal page, and the questions they raise.

    Returns ``(facts_to_show, questions)``. The questions are deliberately about
    the user's *situation* rather than about amounts: this product does not know
    what anyone is entitled to, and asking the right question is the useful
    thing it can honestly do.
    """
    wanted = set(EXPENSE_FACT_IDS)
    if household.has_children is Tristate.YES:
        wanted |= set(CHILD_FACT_IDS)

    usable = [
        fact for fact in facts if fact.id in wanted and fact.content_available and fact.summary
    ]

    questions: list[str] = []
    if any(fact.id == "de_euer_eligibility" for fact in usable):
        questions.append(
            "Am I able to determine my profit as an Einnahmenueberschussrechnung, or "
            "am I required to keep books for this activity?"
        )
    if household.has_children is Tristate.YES:
        if any(fact.id == "de_kinderfreibetrag" for fact in usable):
            questions.append(
                "For my children, does the Kinderfreibetrag or the Kindergeld work out "
                "more favourably in my assessment, and which applies automatically?"
            )
        else:
            # The fact is not in the corpus, so the amounts are not quoted - but
            # the question is still worth putting, and costs nothing to state.
            questions.append(
                "How are children taken into account in my assessment, and is there "
                "anything I need to do to claim it?"
            )
        if household.jointly_assessed is Tristate.UNKNOWN:
            questions.append(
                "Are we assessed jointly or separately, and does that change how the "
                "child allowances are split?"
            )
    if household.has_children is Tristate.UNKNOWN:
        # Not a question for the Finanzamt: a prompt to tell us, so the page can
        # raise the right questions. The product never assumes either way.
        questions.append(
            "If you have children, saying so on this page adds the questions that "
            "raises. Nothing here is assumed from your profile."
        )

    return usable, questions
