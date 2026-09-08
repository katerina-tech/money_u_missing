"""What the user already earns, what it costs them, and who is in the household.

Pure data and pure functions. No I/O, no model calls, and - the point of this
module - no tax arithmetic.

Three things live here, and each exists because the product could not answer an
obvious question without it:

**BaselineIncome.** The product knew what a person *wanted* to earn extra and
what they had *actually* earned through it, but never what they already earn.
That made "an extra 500 a month" a number without a denominator: it could be a
rounding error or a fifty per cent rise, and the difference changes which
opportunities are worth anyone's evening.

**DeductibleExpense.** Earning on the side produces costs, and a person tracking
a side income wants them in the same place as the income. Recording a cost is
bookkeeping. Deciding it reduces someone's tax is Steuerberatung. This module
does the first and refuses the second, and the refusal is structural rather
than a matter of wording - see ``ExpenseSummary``.

**HouseholdContext.** Children can matter to a person's tax position. What the
product does with that is cite Section 32 EStG and produce a question. What it
must never do is infer that someone has children, or compute their Freibetrag.

The rule that shapes all three: **GROSS and NET are never converted into one
another.** That conversion needs the Steuerklasse, church tax status, the
federal state, insurance rates and any Freibetraege. Performing it for an
individual is the regulated act. So a figure is stored with the basis the user
chose, rendered with that basis attached, and never quietly restated as the
other one.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import (
    MIXED_USE_PRONE_CATEGORIES,
    AmountBasis,
    CompensationPeriod,
    ExpenseCategory,
    Tristate,
)

# --------------------------------------------------------------- baseline


class BaselineIncome(BaseModel):
    """Income the user already has, as they described it.

    Never inferred from a CV, never derived from an opportunity, and never
    converted between gross and net.
    """

    model_config = ConfigDict(extra="forbid")

    #: What this income is, in the user's words. "Main job", "Agency retainer".
    label: str = Field(min_length=1, max_length=160)
    #: Integer cents, like every other figure in this product.
    amount_minor: int = Field(ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    #: Whether the amount above is before or after deductions. Required in
    #: practice: an unlabelled income figure is two different numbers.
    basis: AmountBasis = AmountBasis.UNKNOWN
    period: CompensationPeriod = CompensationPeriod.RECURRING
    #: True for the income the user considers their main one. At most one.
    is_primary: bool = False
    started_on: date | None = None

    @property
    def is_labelled(self) -> bool:
        """Whether we know what this figure actually represents."""
        return self.basis is not AmountBasis.UNKNOWN

    def monthly_minor(self) -> int | None:
        """The monthly figure, or ``None`` when the period does not imply one.

        A one-off payment has no monthly equivalent, and spreading it across
        twelve months would invent a regularity the user never claimed.
        """
        if self.period is CompensationPeriod.RECURRING:
            return self.amount_minor
        return None


class BaselinePicture(BaseModel):
    """Every baseline income, summarised without mixing incompatible figures.

    Gross and net are totalled separately and never added together. A person
    with a net salary and a gross retainer has two numbers, not one, and any
    single "total income" figure this product printed would be wrong for both.
    """

    model_config = ConfigDict(extra="forbid")

    entries: list[BaselineIncome] = Field(default_factory=list)
    currency: str = "EUR"

    @property
    def net_monthly_minor(self) -> int:
        return sum(
            entry.monthly_minor() or 0 for entry in self.entries if entry.basis is AmountBasis.NET
        )

    @property
    def gross_monthly_minor(self) -> int:
        return sum(
            entry.monthly_minor() or 0 for entry in self.entries if entry.basis is AmountBasis.GROSS
        )

    @property
    def unlabelled_monthly_minor(self) -> int:
        """Recurring money whose basis the user has not stated.

        Surfaced rather than silently folded into either total, because the
        honest answer to "is this gross or net?" is sometimes "you have not
        told us", and that is a prompt, not a number to guess at.
        """
        return sum(
            entry.monthly_minor() or 0
            for entry in self.entries
            if entry.basis is AmountBasis.UNKNOWN
        )

    @property
    def one_off_minor(self) -> int:
        """Money with no monthly equivalent, kept out of every monthly total."""
        return sum(entry.amount_minor for entry in self.entries if entry.monthly_minor() is None)

    def notes(self) -> list[str]:
        """What a reader has to know before comparing these figures."""
        lines: list[str] = []
        if self.net_monthly_minor and self.gross_monthly_minor:
            lines.append(
                "Gross and net figures are listed separately and are not added together. "
                "Converting between them depends on your Steuerklasse, insurance and "
                "federal state, which this product does not calculate."
            )
        if self.unlabelled_monthly_minor:
            lines.append(
                "Some income is not marked as gross or net, so it is counted on its own "
                "rather than added to either total."
            )
        if self.one_off_minor:
            lines.append(
                "One-off amounts are excluded from the monthly totals, because a single "
                "payment does not imply a monthly figure."
            )
        return lines

    def uplift_ratio(self, additional_monthly_minor: int | None) -> float | None:
        """Additional income as a fraction of the recurring baseline.

        The denominator is whichever basis the user actually uses, and both are
        never mixed. Returns ``None`` when there is no baseline to compare with
        - "an extra 500" against nothing known is not a percentage.
        """
        if not additional_monthly_minor:
            return None
        base = self.net_monthly_minor or self.gross_monthly_minor
        if base <= 0:
            return None
        return round(additional_monthly_minor / base, 4)


# --------------------------------------------------------------- expenses


class DeductibleExpense(BaseModel):
    """A cost the user recorded. Not a claim that it is deductible.

    The field is called ``category`` and not ``deduction_type`` on purpose. This
    product records; a Steuerberater decides.
    """

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=200)
    amount_minor: int = Field(ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    category: ExpenseCategory = ExpenseCategory.OTHER
    incurred_on: date
    #: Whether the user says they hold a receipt. Recorded because the question
    #: "can you evidence it?" is the one that actually decides most disputes,
    #: and because a product that never asked would be encouraging bad records.
    has_receipt: Tristate = Tristate.UNKNOWN
    #: Optional link to the income this cost was incurred for. The connection is
    #: what keeps this a side-income product rather than a bookkeeping app.
    income_stream_id: str | None = None
    application_id: str | None = None
    notes: str | None = Field(default=None, max_length=2000)
    #: The user's own note that the cost was partly private. Recorded verbatim;
    #: never turned into a percentage by this product.
    partly_private: Tristate = Tristate.UNKNOWN

    @model_validator(mode="after")
    def _check_links(self) -> Self:
        if self.income_stream_id and self.application_id:
            raise ValueError("An expense belongs to an income stream or an application, not both.")
        return self


class CategoryTotal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ExpenseCategory
    total_minor: int
    count: int
    #: How many in this category the user has not confirmed a receipt for.
    without_receipt: int
    #: How many the user marked as partly private.
    partly_private: int


class ExpenseSummary(BaseModel):
    """Totals of the user's own figures, and questions - never a tax effect.

    There is no field on this model for tax saved, tax rate, or deductible
    amount, and that absence is the design. Somebody adding one would have to
    add it here, in a module whose docstring says why not, which is the closest
    a type can come to enforcing a regulatory boundary.
    """

    model_config = ConfigDict(extra="forbid")

    currency: str = "EUR"
    total_minor: int = 0
    count: int = 0
    by_category: list[CategoryTotal] = Field(default_factory=list)
    without_receipt_count: int = 0
    #: Specific things to put to a Finanzamt or Steuerberater, in the same
    #: register as the Germany check: precise, answerable, and not advice.
    questions_to_check: list[str] = Field(default_factory=list)
    #: Stated on every rendering of this object.
    disclaimer: str = (
        "These are your own recorded figures, added up. Whether any of them reduces "
        "your tax depends on facts this product cannot assess, so it does not say. "
        "This is not Steuerberatung."
    )


def summarise_expenses(
    expenses: list[DeductibleExpense], *, currency: str = "EUR"
) -> ExpenseSummary:
    """Add up what the user recorded, and say what is worth asking about.

    Deterministic and total: the same expenses always produce the same summary,
    and no model is reachable from here.
    """
    if not expenses:
        return ExpenseSummary(currency=currency)

    totals: dict[ExpenseCategory, list[DeductibleExpense]] = defaultdict(list)
    for expense in expenses:
        totals[expense.category].append(expense)

    by_category = [
        CategoryTotal(
            category=category,
            total_minor=sum(item.amount_minor for item in items),
            count=len(items),
            without_receipt=sum(1 for item in items if item.has_receipt is not Tristate.YES),
            partly_private=sum(1 for item in items if item.partly_private is Tristate.YES),
        )
        for category, items in totals.items()
    ]
    # Largest first: the question worth asking is usually about the biggest
    # number, and a stable order keeps the rendered page from reshuffling.
    by_category.sort(key=lambda row: (-row.total_minor, row.category.value))

    return ExpenseSummary(
        currency=currency,
        total_minor=sum(expense.amount_minor for expense in expenses),
        count=len(expenses),
        by_category=by_category,
        without_receipt_count=sum(
            1 for expense in expenses if expense.has_receipt is not Tristate.YES
        ),
        questions_to_check=_expense_questions(by_category, expenses),
    )


def _expense_questions(
    by_category: list[CategoryTotal], expenses: list[DeductibleExpense]
) -> list[str]:
    """The questions these particular records raise. Rules, not a model.

    Each one is answerable by a person with the authority to answer it, which
    is the difference between a useful question and "consult a professional".
    """
    questions: list[str] = []

    missing = sum(1 for expense in expenses if expense.has_receipt is not Tristate.YES)
    if missing:
        questions.append(
            f"{missing} of {len(expenses)} recorded costs have no confirmed receipt. "
            "What evidence does my Finanzamt expect me to keep, and for how long?"
        )

    mixed = [row for row in by_category if row.partly_private]
    if mixed:
        names = ", ".join(_readable(row.category) for row in mixed)
        questions.append(
            f"I have marked some costs as partly private ({names}). How should the "
            "private share be determined and documented in my case?"
        )

    prone = [
        row
        for row in by_category
        if row.category in MIXED_USE_PRONE_CATEGORIES and not row.partly_private
    ]
    if prone:
        names = ", ".join(_readable(row.category) for row in prone)
        questions.append(
            f"Costs in {names} are often used privately as well. Does my Finanzamt "
            "expect a private share to be shown for any of mine?"
        )

    if any(row.category is ExpenseCategory.EQUIPMENT for row in by_category):
        questions.append(
            "For equipment, is each item treated as a cost in the year of purchase, "
            "or written off over several years in my situation?"
        )

    if any(row.category is ExpenseCategory.WORKSPACE for row in by_category):
        questions.append(
            "For workspace costs, which of the arrangements in my situation does the "
            "Finanzamt accept, and what would I need to show?"
        )

    questions.append(
        "Are these the right categories for my activity, and is anything I am paying "
        "for missing from this list?"
    )
    return questions


def _readable(category: ExpenseCategory) -> str:
    return category.value.replace("_AND_", " and ").replace("_", " ").lower()


# -------------------------------------------------------------- household


class Child(BaseModel):
    """A child in the household, as disclosed by the user.

    Deliberately minimal. An age in years rather than a date of birth, and a
    label the parent chooses rather than a name: the product's questions do not
    need more, and collecting more personal data about a child than a feature
    requires is not a trade this product makes.
    """

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=80)
    age_years: int = Field(ge=0, le=30)
    #: Whether the user says the child is in education or training. Relevant to
    #: which questions are worth raising once a child is over 18, and asked
    #: rather than assumed.
    in_education_or_training: Tristate = Tristate.UNKNOWN


class HouseholdContext(BaseModel):
    """Household facts that change which questions are worth raising.

    Every field is explicit disclosure. Nothing here is ever inferred from a
    CV, a name, an age, a career gap or anything else - inferring somebody's
    family circumstances from their work history is exactly the behaviour this
    product's rules forbid.
    """

    model_config = ConfigDict(extra="forbid")

    has_children: Tristate = Tristate.UNKNOWN
    children: list[Child] = Field(default_factory=list)
    #: Whether the user says they are jointly assessed. It changes which of the
    #: Section 32 questions apply, and it is not derivable from anything else
    #: the product holds.
    jointly_assessed: Tristate = Tristate.UNKNOWN

    @model_validator(mode="after")
    def _children_imply_disclosure(self) -> Self:
        if self.children and self.has_children is Tristate.NO:
            raise ValueError(
                "has_children is NO but children were recorded. The disclosure and "
                "the records must agree."
            )
        return self

    @property
    def disclosed(self) -> bool:
        """Whether the user has actually told us either way."""
        return self.has_children is not Tristate.UNKNOWN
