"""GROW and FAMILY: goals and deterministic projections.

Everything here is arithmetic. No model is consulted, because a compound-growth
figure produced by a language model is a plausible-looking number rather than a
calculated one, and users treat both identically.

The regulatory line this module holds (see docs/REGULATORY_BOUNDARIES.md): the
user supplies the assumed return, the horizon and the contribution. The product
computes what those inputs imply and labels the output illustrative. It does not
suggest a rate, rank instruments, or tell anyone what to buy - that would be a
personal recommendation concerning financial instruments.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import AccountOwnership, FinancialGoalType
from app.domain.evidence import utcnow

#: Guard rails on the user-supplied return assumption. Not advice about what is
#: reasonable - just a refusal to render an arithmetic fantasy.
MIN_ANNUAL_RETURN = -0.20
MAX_ANNUAL_RETURN = 0.20
MAX_HORIZON_YEARS = 60


class FinancialGoal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    user_id: str
    goal_type: FinancialGoalType
    name: str
    target_minor: int = Field(ge=0)
    target_date: date | None = None
    current_minor: int = Field(default=0, ge=0)
    monthly_contribution_minor: int = Field(default=0, ge=0)
    currency: str = "EUR"
    created_at: datetime = Field(default_factory=utcnow)

    @property
    def remaining_minor(self) -> int:
        return max(0, self.target_minor - self.current_minor)

    @property
    def progress_ratio(self) -> float:
        if self.target_minor <= 0:
            return 0.0
        return round(min(1.0, self.current_minor / self.target_minor), 4)

    def months_at_current_contribution(self) -> int | None:
        """Months to reach the target ignoring growth. ``None`` if never.

        Growth is deliberately excluded from this particular figure: it is the
        answer to "if I just keep paying in", and mixing an assumed return into
        it would make the most-quoted number on the page the least certain one.
        """
        if self.remaining_minor == 0:
            return 0
        if self.monthly_contribution_minor <= 0:
            return None
        return -(-self.remaining_minor // self.monthly_contribution_minor)


class ProjectionPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: int
    contributed_minor: int
    #: Nominal balance under the assumed return.
    balance_minor: int
    #: Same balance expressed in today's money when an inflation assumption was
    #: supplied. ``None`` when it was not - not silently equal to nominal.
    real_balance_minor: int | None = None


class ProjectionResult(BaseModel):
    """The output of :func:`app.services.calculators.project`.

    Carries its own inputs so a chart can never be shown without the
    assumptions that produced it.
    """

    model_config = ConfigDict(extra="forbid")

    initial_minor: int
    monthly_contribution_minor: int
    annual_return: float
    annual_inflation: float | None = None
    months: int
    currency: str = "EUR"

    total_contributed_minor: int
    final_balance_minor: int
    final_real_balance_minor: int | None = None
    growth_minor: int
    points: list[ProjectionPoint] = Field(default_factory=list)

    #: Rendered verbatim next to every figure. Not a footnote.
    disclaimer: str = (
        "Illustrative assumption - not a forecast. This calculation applies the "
        "return you entered to the contributions you entered. Real investment "
        "returns vary and can be negative."
    )


class ChildGoal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    user_id: str
    child_label: str = Field(description="A first name or nickname; never required to be legal.")
    child_age_years: int = Field(ge=0, le=25)
    target_age_years: int = Field(ge=1, le=30)
    target_minor: int = Field(default=0, ge=0)
    current_minor: int = Field(default=0, ge=0)
    monthly_contribution_minor: int = Field(default=0, ge=0)
    currency: str = "EUR"
    created_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _ages_ordered(self) -> ChildGoal:
        if self.target_age_years <= self.child_age_years:
            raise ValueError("target_age_years must be greater than child_age_years")
        return self

    @property
    def years_remaining(self) -> int:
        return self.target_age_years - self.child_age_years


class OwnershipConsideration(BaseModel):
    """One neutral point of comparison between parent- and child-held savings."""

    model_config = ConfigDict(extra="forbid")

    topic: str
    parent_account: str
    child_account: str
    #: Where this comparison comes from, when it rests on a legal fact.
    fact_id: str | None = None


class OwnershipComparison(BaseModel):
    """The FAMILY module's account-ownership card.

    Explicitly has no recommended option. Ownership, control at 18, tax
    allowances and interaction with means-tested support pull in different
    directions, and which matters depends on circumstances the product does not
    know. Presenting a winner here would be advice.
    """

    model_config = ConfigDict(extra="forbid")

    considerations: list[OwnershipConsideration] = Field(default_factory=list)
    questions_to_check: list[str] = Field(default_factory=list)
    #: Always None. Present as a field so the absence is explicit in the API
    #: contract rather than merely unimplemented.
    recommended: AccountOwnership | None = None
    note: str = (
        "There is no generally correct answer. Which account ownership suits a "
        "family depends on circumstances this product cannot assess."
    )
