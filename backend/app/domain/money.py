"""Money as a typed quantity, not a number.

Every amount in this system knows four things about itself: how much, how real
(:class:`~app.domain.enums.MoneyState`), how often
(:class:`~app.domain.enums.CompensationPeriod`) and whether it is before or
after tax (:class:`~app.domain.enums.TaxTreatment`). Amounts that disagree on
any of those cannot be added, and :class:`MoneySummary` is built so that trying
produces separate buckets rather than one misleading total.

Money is stored in integer cents. Floating-point euros in a product that shows
people their income is an avoidable class of bug.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import (
    COMMITTED_STATES,
    CompensationBasis,
    CompensationPeriod,
    MoneyState,
    TaxTreatment,
)

#: Used only to express a per-hour or per-day rate as a monthly figure when the
#: user has told us their availability. It is an arithmetic convenience applied
#: to the user's OWN stated hours - never an assumption about a full-time month.
WEEKS_PER_MONTH = 4.33


class MoneyRange(BaseModel):
    """An amount or a band, in integer cents of ``currency``.

    A single figure is expressed as ``minor_min == minor_max``. A published
    range stays a range: collapsing "1,000-5,000 EUR" to its midpoint invents a
    precision the source never offered.
    """

    model_config = ConfigDict(extra="forbid")

    minor_min: int | None = Field(default=None, ge=0, description="Lower bound, in cents.")
    minor_max: int | None = Field(default=None, ge=0, description="Upper bound, in cents.")
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    basis: CompensationBasis = CompensationBasis.UNKNOWN
    period: CompensationPeriod = CompensationPeriod.UNKNOWN
    tax_treatment: TaxTreatment = TaxTreatment.UNKNOWN

    @model_validator(mode="after")
    def _ordered(self) -> MoneyRange:
        both_known = self.minor_min is not None and self.minor_max is not None
        if both_known and self.minor_min > self.minor_max:  # type: ignore[operator]
            raise ValueError("minor_min must not exceed minor_max")
        return self

    @property
    def known(self) -> bool:
        return self.minor_min is not None or self.minor_max is not None

    @property
    def conservative_minor(self) -> int | None:
        """The lower bound, or the single figure. Used wherever a total is shown.

        Deliberately pessimistic: a Money Map that leans on the top of every
        published band is the same failure as inventing the number.
        """
        if self.minor_min is not None:
            return self.minor_min
        return self.minor_max

    def monthly_equivalent_minor(self, hours_per_week: float | None) -> int | None:
        """Express as a monthly figure, or ``None`` when that is not honest.

        Returns ``None`` rather than a guess whenever the conversion would need
        a fact we do not have - most importantly, an hourly rate with no stated
        availability, and anything whose period is ONE_TIME or UNKNOWN. The
        caller is expected to report those separately, which is what
        :class:`MoneySummary` does.
        """
        amount = self.conservative_minor
        if amount is None or self.period is not CompensationPeriod.RECURRING:
            return None
        match self.basis:
            case CompensationBasis.PER_MONTH:
                return amount
            case CompensationBasis.PER_YEAR:
                return round(amount / 12)
            case CompensationBasis.PER_HOUR:
                if hours_per_week is None:
                    return None
                return round(amount * hours_per_week * WEEKS_PER_MONTH)
            case CompensationBasis.PER_DAY:
                if hours_per_week is None:
                    return None
                # A "day" of freelance work is 8 hours by near-universal
                # convention in German day-rate contracting; the user's weekly
                # availability then caps how many such days fit in a month.
                return round(amount * (hours_per_week / 8.0) * WEEKS_PER_MONTH)
            case _:
                return None


class MoneyEntry(BaseModel):
    """One amount attached to one opportunity or income stream, in one state."""

    model_config = ConfigDict(extra="forbid")

    label: str
    amount: MoneyRange
    state: MoneyState
    #: True once the user has confirmed a real figure from an offer or payment,
    #: as opposed to a figure a listing published.
    user_confirmed: bool = False


class MoneyBucket(BaseModel):
    """A total that is only ever a total of like things."""

    model_config = ConfigDict(extra="forbid")

    minor_total: int = 0
    currency: str = "EUR"
    count: int = 0

    def add(self, minor: int) -> None:
        self.minor_total += minor
        self.count += 1


class MoneySummary(BaseModel):
    """What the Money Map is allowed to display.

    Four separate figures, never one. The separation is the product promise:
    recurring potential is not one-time potential, potential is not secured,
    and an opportunity whose compensation was never published is counted as a
    number of opportunities rather than folded in at zero - because zero is a
    claim, and we do not have one.
    """

    model_config = ConfigDict(extra="forbid")

    currency: str = "EUR"

    recurring_potential_monthly_minor: int = 0
    recurring_potential_count: int = 0

    one_time_potential_minor: int = 0
    one_time_potential_count: int = 0

    #: Committed: the user marked an application WON and entered a real figure.
    secured_monthly_minor: int = 0
    secured_one_time_minor: int = 0
    secured_count: int = 0

    #: Money actually received, recorded as income events.
    earned_total_minor: int = 0
    earned_count: int = 0

    #: Opportunities whose compensation the source never published. Shown as a
    #: count with an explanation, never estimated.
    unknown_value_count: int = 0

    #: Opportunities with a published amount we could not convert to a monthly
    #: figure without inventing the user's availability.
    unconvertible_count: int = 0

    @property
    def goal_progress_ratio(self) -> float | None:
        """Progress against a monthly goal - secured and earned only.

        Potential is excluded on purpose. A progress bar that fills up with
        opportunities the user has not applied to would be the single most
        dishonest element the product could ship.
        """
        return None


def summarise_committed(entries: list[MoneyEntry]) -> tuple[int, int, int]:
    """(monthly_secured, one_time_secured, count) over committed entries only."""
    monthly = one_time = count = 0
    for entry in entries:
        if entry.state not in COMMITTED_STATES:
            continue
        amount = entry.amount.conservative_minor
        if amount is None:
            continue
        count += 1
        if entry.amount.period is CompensationPeriod.RECURRING:
            monthly_value = entry.amount.monthly_equivalent_minor(None)
            if monthly_value is not None:
                monthly += monthly_value
                continue
        one_time += amount
    return monthly, one_time, count


def format_minor(minor: int | None, currency: str = "EUR") -> str:
    """Render cents for logs and tests. The UI formats with the user's locale."""
    if minor is None:
        return "unknown"
    return f"{minor / 100:,.0f} {currency}"
